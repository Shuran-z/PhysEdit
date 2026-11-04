"""Bind fresh H3 inputs to the verified HF fix; reuse only provably identical frozen features."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.h3_prompt_sg_transport import run,copy,PY
OUT=ROOT/'review/prompt_semantic_repair_20261102';PRIOR='/data/yangkaiyuan/h3_prompt_retrain_7af77078_20261102';NEW='/data/yangkaiyuan/h3_prompt_retrain_semantic_v2_20261102'
ENCODER_PY='/data/yangkaiyuan/phyediting_eval_render_20261028/envs/qwen/bin/python'
def main():
 pub=json.loads((OUT/'PUBLISHED.json').read_text());verified=json.loads((OUT/'FRESH_VERIFIED.json').read_text());assert verified['status']=='PASS' and verified['revision']==pub['commit']
 report=json.loads((OUT/'INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'));assert report['status']=='PASS'
 bundle=OUT/'h3_bundle';bundle.mkdir(exist_ok=True)
 for name in ['h3_new_prompt_common.py','h3_new_prompt_features.py','h3_new_prompt_train.py','h3_new_prompt_queue.py']:
  text=(ROOT/'scripts'/name).read_text(encoding='utf8').replace(PRIOR,NEW)
  if name=='h3_new_prompt_common.py':
   text=text.replace("REV='7af77078d39270a3c6ca7633bd373f357483b5f0'",'REV='+repr(pub['commit']))
   begin=text.index('def caption(');end=text.index('def media(',begin)
   caption="""def caption(row,fps):
 variant=int(hashlib.sha256(row['canonical_video_id'].encode()).hexdigest()[:8],16)%3
 text=row['prompt_variants_en'][variant]
 assert hashlib.sha256(text.encode()).hexdigest()==row['prompt_variant_sha256'][variant]
 if re.search(r'\\bframes?\\s+\\d',text,re.I):
  assert re.search(r'\\b(?:fps|Hz)\\b|\\b(?:Frame|Controller) step\\s+[-+0-9.eE/]+\\s*s\\b',text,re.I),'Published frame-index control lacks an explicit clock'
 return variant+1,text

"""
   text=text[:begin]+caption+text[end:]
  (bundle/name).write_text(text,encoding='utf8')
 manifest=OUT/'stage/releases/physedit/catalog/train_final.jsonl.gz';assert hashlib.sha256(manifest.read_bytes()).hexdigest()==report['training_manifest_sha256']
 plan=dict(hf_revision=pub['commit'],prompt_policy=report['policy'],training_videos=45165,manifest_sha256=report['training_manifest_sha256'],global_batch=12,total_steps=3764,padding_presentations=3,seed=20261102,prompt_variant_policy='int(sha256(canonical_video_id)[:8],16)%3+1',start_from='original_base_fresh_lora_fresh_optimizer',old_checkpoints_preserved=True,old_cache_preserved=True,prior_prompt_run=PRIOR,semantic_audit_sha256=hashlib.sha256((OUT/'INDEPENDENT_VERIFICATION.json').read_bytes()).hexdigest())
 (bundle/'PLAN.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
 print(run(f"from pathlib import Path;r=Path({NEW!r});r.mkdir(exist_ok=True);(r/'cache').mkdir(exist_ok=True);(r/'training').mkdir(exist_ok=True)"))
 copy(manifest.relative_to(ROOT),NEW+'/train_final.jsonl.gz')
 for p in bundle.iterdir():copy(p.relative_to(ROOT),NEW+'/'+p.name)
 code=f'''from pathlib import Path
import os,sys,json,time,shutil,hashlib,copy,py_compile
r=Path({NEW!r});prior=Path({PRIOR!r});assert not(prior/'TRAINER_LAUNCHED.json').exists();assert(prior/'STOP_QUEUE').exists()and(prior/'STOP_ENCODER').exists()
for name in ['CURRENT_CLOCKS.json','training_order.json']:shutil.copyfile(prior/name,r/name)
link=r/'current_media'
if not link.exists():link.symlink_to(prior/'current_media',target_is_directory=True)
assert link.resolve()==(prior/'current_media').resolve()
mode=json.loads((prior/'RESOURCE_MODE.json').read_text());assert mode['mode']=='wait_existing_validation'and mode['user_confirmed'];mode['instruction']='Continue existing CogVideo verification; automatically start H3 with corrected prompt revision '+{pub['commit']!r}+' after independently verified native600 completion and GPU release.';(r/'RESOURCE_MODE.json').write_text(json.dumps(mode,indent=2))
for p in r.glob('h3_new_prompt_*.py'):py_compile.compile(str(p),doraise=True)
sys.path.insert(0,str(r));from h3_new_prompt_common import *
sys.path.insert(0,str(OLD));import torch,gzip
plan,data=rows();old={{x['canonical_video_id']:x for x in map(json.loads,gzip.open(OLD/'train_manifest_runtime.jsonl.gz','rt'))}};clocks=json.loads((OLD/'verified_clocks.json').read_text());prior_plan=json.loads((prior/'PLAN.json').read_text())
reuse={{}};stats={{'same_condition_features_reused':0,'video_latents_reusable':0,'video_latents_missing':0,'training_videos':len(data)}};records=[]
for vid,row in data.items():
 fps,evidence=clock(row,old,clocks);candidates=[prior/'cache'/(vid+'.pt'),OLD/'h3_cache'/(vid+'.pt')];chosen=None
 for p in candidates:
  if not p.exists():continue
  d=torch.load(p,map_location='cpu',weights_only=True,mmap=True);rec=d['full_window_receipt']
  if d['source_sha256']!=row['sha256'] or abs(rec['fps']-fps)>1e-8:continue
  n=d['frames'];assert rec['model_sample_indices']==[min(rec['frames']-1,round(i*fps/24))for i in range(n)]and tuple(d['first'].shape)==(1,24,1,18,32)
  assert tuple(d['latent'].shape)==(1,24,((n+16)//17)*5-3,18,32)
  chosen=p;reuse[vid]=dict(path=str(p),source_sha256=row['sha256'],physical_fps=fps,frames=n);stats['video_latents_reusable']+=1
  variant,text=caption(row,fps);h=hashlib.sha256(text.encode()).hexdigest()
  if p.parent==prior/'cache'and d.get('hf_revision')==prior_plan['hf_revision']and d['manifest_sha256']==prior_plan['manifest_sha256']and rec['model_input_prompt']==text and d['prompt_sha256']==rec['model_input_prompt_sha256']==h:
   original_tensors={{k:tensor_sha(d[k])for k in ['latent','first','embeddings','tags']}}
   new={{k:(d[k].clone()if hasattr(d[k],'clone')else copy.deepcopy(d[k]))for k in d}}
   new.update(manifest_sha256=plan['manifest_sha256'],hf_revision=REV,source_prompt_sha256=row['prompt_variant_sha256'][variant-1],prompt_variant=variant,prompt_sha256=h)
   new['full_window_receipt'].update(hf_revision=REV,prompt_sha256=row['prompt_variant_sha256'],model_input_prompt=text,model_input_prompt_sha256=h)
   new['vae_reuse']=dict(reused=True,source_cache=str(p),latent_sha256=original_tensors['latent'],first_sha256=original_tensors['first'],byte_identical_tensors=True)
   new['condition_reuse']=dict(source_cache=str(p),same_source_video=True,model_input_string_byte_identical=True,embedding_sha256=original_tensors['embeddings'],tags_sha256=original_tensors['tags'],source_revision=prior_plan['hf_revision'])
   assert all(torch.isfinite(new[k]).all()and tensor_sha(new[k])==original_tensors[k]for k in original_tensors)
   target=r/'cache'/(vid+'.pt');assert not target.exists();tmp=target.with_suffix('.partial');torch.save(new,tmp);tmp.replace(target);stats['same_condition_features_reused']+=1;records.append(dict(id=vid,prompt_sha256=h,source_sha256=row['sha256'],embeddings_sha256=original_tensors['embeddings']))
  break
 if chosen is None:stats['video_latents_missing']+=1
save(r/'REUSE_INDEX.json',reuse)
for name in ['CURRENT_CLOCKS.json','training_order.json','REUSE_INDEX.json']:plan[name+'_sha256']=sha(r/name)
save(r/'PLAN.json',plan);result=dict(status='PASS',time=time.time(),revision=REV,counts=stats,condition_reuse_records=records,source_media_download_reused=True,old_feature_and_checkpoint_files_modified=False,training_started=False)
save(r/'CACHE_MIGRATION_VERIFIED.json',result);print(json.dumps({{k:v for k,v in result.items()if k!='condition_reuse_records'}}))
'''
 print(run(code,python=PY,timeout=600),flush=True)
 # Launch only the corrected cache and corrected training controller. No Cog task is stopped.
 code=f'''from pathlib import Path
import os,json,time,subprocess
r=Path({NEW!r});assert not(r/'PIPELINE_LAUNCHED.json').exists();assert json.loads((r/'CACHE_MIGRATION_VERIFIED.json').read_text())['status']=='PASS'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='GPU-91b733ec-e331-9b77-e85d-d5982b768967',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='3',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1')
with(r/'encoder.log').open('ab')as log:encoder=subprocess.Popen([{ENCODER_PY!r},'-u',str(r/'h3_new_prompt_features.py')],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
with(r/'queue.log').open('ab')as log:queue=subprocess.Popen([{PY!r},'-u',str(r/'h3_new_prompt_queue.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
proof=dict(time=time.time(),hf_revision={pub['commit']!r},encoder_pid=encoder.pid,queue_pid=queue.pid,cog_validation_unchanged=True,resource_mode=json.loads((r/'RESOURCE_MODE.json').read_text()),old_run_preserved=True)
(r/'PIPELINE_LAUNCHED.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
'''
 print(run(code,timeout=40),flush=True)
 for name in ['PLAN.json','CACHE_MIGRATION_VERIFIED.json','PIPELINE_LAUNCHED.json']:
  d=json.loads(run(f"from pathlib import Path;print(Path({NEW+'/'+name!r}).read_text())",timeout=60));(OUT/('H3_'+name)).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
