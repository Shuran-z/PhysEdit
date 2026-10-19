"""Recover exact release config sidecars on the authenticated host, in resumable batches."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import json,hashlib,gzip,base64,pathlib,concurrent.futures
from huggingface_hub import hf_hub_download, hf_hub_url, get_token
import requests
def fetch(row):
 try:
  cache=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/critical_sidecar_recovery_20261018');cache.mkdir(exist_ok=True)
  key=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
  p=cache/(key+('.json.gz' if row['sidecar'].endswith('.gz') else '.json'))
  if not p.exists():
   response=requests.get(hf_hub_url(row['repo_id'],row['sidecar'],repo_type='dataset',revision=row['revision']),headers={'Authorization':'Bearer '+get_token()},timeout=(10,35))
   response.raise_for_status();p.write_bytes(response.content)
  b=p.read_bytes();c=json.loads(gzip.decompress(b) if p.name.endswith('.gz') else b)
  kind='original_config'
  if p.name.endswith('.gz'):
   kind='published_metadata_projection'
   c={k:v for k,v in c.items() if k in ['experiment','manifest','scene_overrides','dynamic_objects','runtime_forces','render','time_diagnostic']}
   c['dynamic_objects']=[o.get('spec',o) for o in c.get('dynamic_objects',[])]
  return {**row,'sha256':hashlib.sha256(b).hexdigest(),'config':c,'path':str(p),'evidence_kind':kind}
 except Exception as e:return {**row,'error':type(e).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,ROWS))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
def main():
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 registry=[json.loads(l) for l in (OUT/'all_scene_family_registry.jsonl').read_text(encoding='utf-8').splitlines()]
 missing={r['sample_id'] for r in registry if not r['candidates']}
 rows=[]
 recovered={r['sample_id']:r for r in [json.loads(l) for l in Path('docs/joint_split_v3/recovered_sidecar_references.jsonl').read_text(encoding='utf-8').splitlines()] if r['engine']=='genesis'}
 for r in inventory:
  if r['engine']!='genesis' or r['sample_id'] not in missing:continue
  paths=r.get('sidecar_paths',[])+recovered.get(r['sample_id'],{}).get('sidecar_candidates',[])
  path=next((p for p in paths if '/configs/' in p and 'cam01' in p),None)
  if not path:path=next((p for p in paths if '/metadata/' in p and 'cam01' in p and p.endswith('.json.gz')),None)
  if path:rows.append(dict(sample_id=r['sample_id'],scene_id=r['event_id'],repo_id=r['repo_id'],revision=r['revision'],sidecar=path))
 plan=OUT/'remaining_sidecar_download_plan.json'
 if plan.exists():rows=json.loads(plan.read_text(encoding='utf-8'))
 else:plan.write_text(json.dumps(rows,indent=2),encoding='utf-8')
 for i in range(0,len(rows),4):
  dest=OUT/f'recovered_sidecar_batch_{i//4:03}.json'
  if dest.exists():continue
  code=REMOTE.replace('ROWS',repr(rows[i:i+4]))
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes','-R','127.0.0.1:39727:127.0.0.1:7897','p25','timeout 280 env HTTPS_PROXY=http://127.0.0.1:39727 HF_HUB_ETAG_TIMEOUT=8 HF_HUB_DOWNLOAD_TIMEOUT=10 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=300)
  if p.returncode:(OUT/'recovered_download_error.txt').write_bytes(p.stderr)
  p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));dest.write_bytes(raw)
  result=json.loads(raw);print(json.dumps(dict(batch=i//4,total=len(rows),found=sum('config' in r for r in result),errors=sum('error' in r for r in result))),flush=True)
if __name__=='__main__':main()

