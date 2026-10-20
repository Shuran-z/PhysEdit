"""Recover compact original T03 causal reports at the parameter-header revision."""
import json
from pathlib import Path
import re
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import json,hashlib,pathlib,concurrent.futures,requests,time
from huggingface_hub import HfApi,get_token,hf_hub_url
repo='phy2/phydataset';revision=REVISION;rows=ROWS;token=get_token();api=HfApi(token=token)
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t03_event_reports_20261019');root.mkdir(exist_ok=True)
paths=[r['release_prefix']+'/qa/'+r['sample_id']+'/sample_causal_quality_gate.json' for r in rows];ids={}
for i in range(0,len(paths),50):
 for e in api.get_paths_info(repo,paths[i:i+50],repo_type='dataset',revision=revision):ids[e.path]=dict(size=e.size,blob_id=e.blob_id,lfs_sha256=getattr(getattr(e,'lfs',None),'sha256',None))
def get(pair):
 row,path=pair;sid=row['sample_id'];p=root/(sid+'.json')
 if p.exists():
  r=json.loads(p.read_text(encoding='utf-8'))
  if r.get('revision')==revision and r.get('identity')==ids.get(path):return r
 for attempt in range(3):
  try:
   response=requests.get(hf_hub_url(repo,path,repo_type='dataset',revision=revision),headers={'Authorization':'Bearer '+token},timeout=30);response.raise_for_status();raw=response.content;e=ids[path]
   assert len(raw)==e['size']
   if e['lfs_sha256']:assert hashlib.sha256(raw).hexdigest()==e['lfs_sha256']
   else:assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==e['blob_id']
   r=dict(sample_id=sid,revision=revision,path=path,identity=e,sha256=hashlib.sha256(raw).hexdigest(),data=json.loads(raw));p.write_text(json.dumps(r));return r
  except Exception as exc:
   error=type(exc).__name__
   if attempt<2:time.sleep(1)
 return dict(sample_id=sid,error_type=error)
result=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(get,zip(rows,paths)):
  result.append(r)
  if len(result)%80==0:print('PROGRESS '+json.dumps(dict(read=len(result),failed=sum('error_type' in r for r in result))),flush=True)
print('RESULT '+json.dumps(result),flush=True)
'''


def main():
    release=json.loads((ROOT/'t03_current_selection_20261019.json').read_text(encoding='utf-8'))[0]
    file=next(f for f in release['files'] if f['path']=='catalog/t03_880_selection.jsonl');rows=[json.loads(line) for line in file['text'].splitlines()]
    p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-R','127.0.0.1:0:127.0.0.1:7897','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        m=re.search(rb'Allocated port (\d+)',p.stderr.readline())
        if not m:raise RuntimeError('SSH proxy unavailable')
        prefix="import os\nos.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n"%int(m[1])
        p.stdin.write((prefix+REMOTE.replace('REVISION',repr(release['revision'])).replace('ROWS',repr(rows))).encode());p.stdin.close()
        for line in p.stdout:
            if line.startswith(b'RESULT '):(ROOT/'t03_current_original_event_reports.json').write_bytes(line[len(b'RESULT '):])
            else:print(line.decode().strip(),flush=True)
        if p.wait():raise RuntimeError('original causal report read failed; credentials suppressed')
    finally:
        if p.poll() is None:p.kill();p.wait()


if __name__=='__main__':main()
