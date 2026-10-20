"""Recover all selected T03 annotations at their immutable published revision.

Verify Git/LFS identity before parsing. Preserve solver repairs, runtime specs,
full per-frame contact evidence and actor poses; do not equate old semantic IDs
with identical solver settings. Credentials remain on the existing server.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT=Path('review/scene_family_completion_20261018')

REMOTE=r'''
import os,json,gzip,hashlib,pathlib,concurrent.futures,shutil
from huggingface_hub import HfApi,hf_hub_download,get_token
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t03_current_recovery_20261019');root.mkdir(exist_ok=True)
rows=ROWS;revision=REVISION;repo='phy2/phydataset'
api=HfApi(token=get_token());paths=[r['release_prefix']+'/metadata/'+r['sample_id']+'/'+r['sample_id']+'__cam01.json.gz' for r in rows]
identities={}
for i in range(0,len(paths),50):
 for e in api.get_paths_info(repo,paths[i:i+50],repo_type='dataset',revision=revision):
  identities[e.path]=dict(size=e.size,blob_id=e.blob_id,lfs_sha256=getattr(getattr(e,'lfs',None),'sha256',None))
assert len(identities)==len(rows)
def recover(pair):
 row,path=pair;sid=row['sample_id'];out=root/(sid+'.json.gz');receipt=root/(sid+'.receipt.json')
 try:
  if receipt.exists():
   old=json.loads(receipt.read_text())
   if old.get('revision')==revision and old.get('published_identity')==identities[path] and old.get('extraction_schema_version')==2 and out.exists():return old
  if shutil.disk_usage(root).free<30*1024**3:raise RuntimeError('disk below 30GiB free')
  local=pathlib.Path(hf_hub_download(repo_id=repo,filename=path,repo_type='dataset',revision=revision,cache_dir=str(root/'hf_cache')))
  raw=local.read_bytes();identity=identities[path]
  digest=hashlib.sha256(raw).hexdigest()
  assert len(raw)==identity['size']
  if identity['lfs_sha256']:assert digest==identity['lfs_sha256']
  else:assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==identity['blob_id']
  data=json.loads(gzip.decompress(raw));frames=data.pop('frames')
  with gzip.open(out,'wt',encoding='utf-8') as stream:json.dump(dict(sample_id=sid,header=data,frames=frames),stream)
  result=dict(sample_id=sid,repo_id=repo,revision=revision,published_path=path,published_identity=identity,published_sha256=digest,local_original_path=str(local),
   extracted_path=str(out),extracted_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),extraction_schema_version=2,frames=len(frames),published_recovery=row.get('recovery'),status='verified_published_state')
  receipt.write_text(json.dumps(result));return result
 except Exception as exc:return dict(sample_id=sid,status='failed',error_type=type(exc).__name__)
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(recover,zip(rows,paths)):
  results.append(result)
  temp=root/'status.tmp';temp.write_text(json.dumps(results));temp.replace(root/'status.json')
  print(json.dumps(dict(completed=len(results),verified=sum(r['status']=='verified_published_state' for r in results),failed=sum(r['status']=='failed' for r in results))),flush=True)
print(json.dumps(dict(root=str(root),total=len(results))),flush=True)
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',default=str(ROOT/'t03_current_selection_20261019.json'));args=p.parse_args()
    release=json.loads(Path(args.selection).read_text(encoding='utf-8'))[0]
    file=next(f for f in release['files'] if f['path']=='catalog/t03_880_selection.jsonl')
    rows=[json.loads(line) for line in file['text'].splitlines() if line.strip()]
    if len(rows)!=880 or len({r['sample_id'] for r in rows})!=880:raise ValueError('expected 880 unique selected trajectories')
    proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ExitOnForwardFailure=yes','-R','127.0.0.1:0:127.0.0.1:7897','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        match=re.search(rb'Allocated port (\d+)',proc.stderr.readline())
        if not match:raise RuntimeError('proxy forwarding failed')
        prefix="import os\nos.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n"%int(match[1])
        code=REMOTE.replace('ROWS',repr(rows)).replace('REVISION',repr(release['revision']))
        proc.stdin.write((prefix+code).encode());proc.stdin.close()
        for line in proc.stdout:print(line.decode('utf-8').strip(),flush=True)
        if proc.wait():raise RuntimeError('remote recovery failed; credentials and URLs suppressed')
    finally:
        if proc.poll() is None:proc.kill();proc.wait()


if __name__=='__main__':main()
