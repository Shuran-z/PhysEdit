import collections,gzip,hashlib,json,os
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';pending=list(map(json.loads,gzip.open(R/'remaining6767/REMAINING.jsonl.gz','rt')));ids={x['canonical_video_id'] for x in pending};tasks=[x for x in map(json.loads,gzip.open(R/'TASKS.jsonl.gz','rt')) if x['canonical_video_id'] in ids];names={x['native_sample_id'] for x in tasks};found=[];scanned=0
for repo in ['datasets--phy2--phydataset','datasets--phyeditingvideo--Phyediting']:
 root=Path.home()/'.cache/huggingface/hub'/repo/'blobs'
 for p in root.glob('*'):
  if not p.is_file() or not 100<p.stat().st_size<1500000:continue
  scanned+=1;raw=p.read_bytes()
  if not raw.lstrip().startswith(b'{') or b'"dynamic_objects"' not in raw:continue
  try:c=json.loads(raw)
  except Exception:continue
  if 'frames' in c or not isinstance(c.get('render'),dict) or not c.get('dynamic_objects'):continue
  exp=c.get('experiment') or {};native=exp.get('trajectory_id') or exp.get('sample_id')
  if native not in names:
   save=c['render'].get('save_video','');native=Path(save).name.removesuffix('.mp4');native=native.rsplit('__cam',1)[0]
  if native not in names:continue
  h=hashlib.sha256(raw).hexdigest();dest=O/'cache_config_bytes';dest.mkdir(exist_ok=True);(dest/(h+'.json')).write_bytes(raw);found.append(dict(native_sample_id=native,path=str(p),sha256=h,local_path=str(dest/(h+'.json')),dataset_version=c.get('dataset_version'),source_provenance=c.get('source_provenance')))
print(json.dumps({'blobs_scanned':scanned,'candidate_files':len(found),'by_native':dict(collections.Counter(x['native_sample_id'] for x in found))})[:4500]);(O/'CACHE_CONFIG_CANDIDATES.json').write_text(json.dumps(found,indent=2))
