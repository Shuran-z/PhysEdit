import json,gzip,hashlib,collections
from pathlib import Path
from huggingface_hub import hf_hub_download
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining6767'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def sha(b):return hashlib.sha256(b).hexdigest()
repo='phyeditingvideo/Phyediting';rev='3856c258368789c942dbc16d4983e756881ad986';prefix='staging/t04_t05/formal_880_v1_480p_20260903T1310CST'
manifestpath=Path(hf_hub_download(repo,prefix+'/SNAPSHOT_MANIFEST.json',repo_type='dataset',revision=rev))
m=json.loads(manifestpath.read_bytes());print('manifest',list(m),str(type(m['samples'])),flush=True)
print(json.dumps(m['samples'][:1])[:2000],flush=True)
tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')};snap={x['sample_id']:x for x in m['samples']}
new=load(O/'NEW_RECOVERIES.jsonl.gz');already={x['canonical_video_id'] for x in new};pending=load(O/'ambiguous_probe/REMAINING.jsonl.gz');fixed=set();fail=[];receiptcache={}
for row in pending:
 cid=row['canonical_video_id'];
 if cid in already:continue
 t=tasks[cid];candidates={x['sha256']:x for x in row['compatible_config_candidates']};docs={h:json.loads(Path(x['path']).read_bytes()) for h,x in candidates.items()}
 originals={h:x for h,x in candidates.items() if not docs[h].get('source_provenance')};selected=None;evidence={}
 for h,c in docs.items():
  p=c.get('source_provenance') or {};parent=p.get('source_sha256','').lower()
  if parent in originals:
   assert sha(Path(candidates[h]['path']).read_bytes())==h
   selected=originals[parent];evidence={'derived_config_sha256':h,'explicit_parent_provenance':p,'original_config_sha256':parent};break
 if selected is None and t['scene']=='T05' and len(originals)==1:
  h,x=next(iter(originals.items()));native=t['native_sample_id'];s=snap.get(native)
  if s is None:
   sourcepath=x['metadata_source_key'].split(':',1)[1];newprefix=sourcepath.split('/T05/')[0]
   mp=Path(hf_hub_download(repo,newprefix+'/SNAPSHOT_MANIFEST.json',repo_type='dataset',revision=rev));mm=json.loads(mp.read_bytes());s=next((v for v in mm['samples'] if v['sample_id']==native),None)
   if s:manifestpath=mp
  if s:
   if native not in receiptcache:
    p=Path(s['source_dir'])/'FORMAL_COMPLETED.json';raw=p.read_bytes() if p.is_file() else b''
    if sha(raw)!=s['marker_sha256']:p=Path(hf_hub_download(repo,s['remote_dir']+'/FORMAL_COMPLETED.json',repo_type='dataset',revision=rev));raw=p.read_bytes()
    assert sha(raw)==s['marker_sha256'];receiptcache[native]=(json.loads(raw),sha(raw))
   receipt,rh=receiptcache[native];cmd=receipt.get('command',[])
   if receipt.get('status')=='PASS' and x['path'] in cmd:
    selected=x;evidence={'execution_receipt_sha256':rh,'execution_receipt_source':{'repo':repo,'revision':rev,'path':s['remote_dir']+'/FORMAL_COMPLETED.json'},'snapshot_manifest_sha256':sha(manifestpath.read_bytes()),'executed_config_path':x['path'],'historical_config_byte_digest_logged':False}
 if selected:
  raw=Path(selected['path']).read_bytes();assert sha(raw)==selected['sha256'];assert selected['method'].startswith(('source_video_sha','shared_trajectory'))
  evidence.update(video_sha256=t['video_sha256'],metadata_source_key=selected['metadata_source_key'],config_byte_sha256=selected['sha256'],full_input_match_method=selected['method'])
  new.append(dict(canonical_video_id=cid,status='RECOVERED',local_path=selected['path'],sha256=selected['sha256'],method='original_config_execution_and_parent_provenance_disambiguation',evidence=evidence));fixed.add(cid)
 else:fail.append(cid)
for filename,rows in [('NEW_RECOVERIES.jsonl.gz',new),('REMAINING.jsonl.gz',[x for x in load(O/'REMAINING.jsonl.gz') if x['canonical_video_id'] not in fixed])]:
 with gzip.open(O/filename,'wt') as f:
  for x in rows:f.write(json.dumps(x)+'\n')
summary={'new_disambiguated':len(fixed),'failures':fail,'total_new_recoveries':len(new),'by_scene':dict(collections.Counter(tasks[c]['scene'] for c in fixed))};(O/'PARENT_PROVENANCE_RECEIPT.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
