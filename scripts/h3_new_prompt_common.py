"""Versioned H3 inputs: current media, exact physical clocks, fresh prompt bindings."""
from pathlib import Path
import gzip,hashlib,json,re,os,time
R=Path('/data/yangkaiyuan/h3_prompt_retrain_7af77078_20261102')
OLD=Path('/data/yangkaiyuan/video_models_lora_20261030/h3_feature_worker_sg')
MEDIA=Path('/data/yangkaiyuan/cogvideox15_full_sft_20261030/media')
WEIGHTS=Path('/data/yangkaiyuan/video_models_lora_20261030/weights')
SCIENTIFIC=Path('/home/yangkaiyuan/phy_nvme/h3_checkpoint110_compat_20261101/scientific_sources')
REV='7af77078d39270a3c6ca7633bd373f357483b5f0'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.partial.'+str(os.getpid()));t.write_text(json.dumps(d,indent=2));t.replace(p)
def rows():
 plan=json.loads((R/'PLAN.json').read_text());assert sha(R/'train_final.jsonl.gz')==plan['manifest_sha256']
 data={r['canonical_video_id']:r for r in map(json.loads,gzip.open(R/'train_final.jsonl.gz','rt'))}
 assert len(data)==45165 and not {'T03','T11','T19','T20','T14S'}&{r['scene'] for r in data.values()}
 return plan,data
def clock(row,oldrows,clocks):
 vid=row['canonical_video_id'];previous=oldrows.get(vid)
 compat=(row.get('current_render') or {}).get('encoding_compatibility',{})
 if previous and (previous['sha256']==row['sha256'] or compat.get('source_sha256')==previous['sha256']):
  return float(1/clocks[vid]['physical_frame_period_s']),dict(kind='original_verified_physical_clock',evidence=clocks[vid],encoding_lineage_used=previous['sha256']!=row['sha256'])
 if not hasattr(clock,'current'):clock.current=json.loads((R/'CURRENT_CLOCKS.json').read_text())
 evidence=clock.current[vid];fps=evidence['physical_fps'];assert fps>0 and evidence['config_sha256']==row['config_download']['sha256']
 return fps,dict(kind='hash_bound_current_executed_render_config',evidence=evidence)
def caption(row,fps):
 variant=int(hashlib.sha256(row['canonical_video_id'].encode()).hexdigest()[:8],16)%3
 raw=row['prompt_variants_en'][variant];assert hashlib.sha256(raw.encode()).hexdigest()==row['prompt_variant_sha256'][variant]
 explicit=[float(x) for x in re.findall(r'\b(\d+(?:\.\d+)?)\s*fps\b',raw,re.I)]
 text=raw
 if re.search(r'\bframes?\s+\d',raw,re.I) and abs(fps-24)>1e-5 and not any(abs(fps-x)<1e-5 for x in explicit):text+=' Frame indices use a %g fps reference clock.'%fps
 return variant+1,text
def media(row,wait=True):
 vid=row['canonical_video_id'];start=time.time()
 while True:
  for p in [R/'current_media'/(vid+'.mp4'),MEDIA/(vid+'.mp4')]:
   if p.exists() and sha(p)==row['sha256']:return p
  save(R/'MEDIA_WAIT.json',dict(time=time.time(),id=vid,expected_sha256=row['sha256']))
  if not wait:raise FileNotFoundError(vid)
  assert not (R/'STOP_ENCODER').exists() and time.time()-start<21600,'Current media unavailable; never substitute stale video'
  time.sleep(5)
def sampled(row,fps):
 import av,numpy as np
 from PIL import Image
 p=media(row)
 with av.open(str(p)) as c:frames=[f.to_image().convert('RGB') for f in c.decode(video=0)]
 available=min(169,int((len(frames)-1)/fps*24)+1);n=(available-5)//17*17+5;assert n>=5
 indices=[min(len(frames)-1,round(i*fps/24)) for i in range(n)]
 sampled=[np.asarray(frames[i].resize((512,288),Image.Resampling.LANCZOS)) for i in indices]
 return np.stack(sampled),dict(source_sha256=row['sha256'],frames=len(frames),fps=fps,model_frames=n,model_fps=24,model_sample_indices=indices,source_path=str(p),lossless_source_decode=True,preprocessing='PIL Lanczos RGB 512x288; preserve physical seconds; H3 17-frame grid tail crop')
def tensor_sha(t):
 import torch
 return hashlib.sha256(t.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
