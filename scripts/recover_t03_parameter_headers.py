"""Read T03 published parameter metadata without waiting for full trajectories.

Read only the gzip prefix needed to parse the complete experiment object, at a
fixed HF revision. Record immutable path/LFS identity and prefix hash separately
from full-file verification. No video processing or simulation is involved.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,hashlib,zlib,concurrent.futures,time,requests,os
from huggingface_hub import HfApi,get_token,hf_hub_url
repo='phy2/phydataset';revision=REVISION;rows=ROWS
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t03_parameter_headers_20261019');root.mkdir(exist_ok=True)
token=get_token();api=HfApi(token=token)
paths=[r['release_prefix']+'/metadata/'+r['sample_id']+'/'+r['sample_id']+'__cam01.json.gz' for r in rows]
identities={}
for i in range(0,len(paths),50):
 for e in api.get_paths_info(repo,paths[i:i+50],repo_type='dataset',revision=revision):identities[e.path]=dict(size=e.size,blob_id=e.blob_id,lfs_sha256=getattr(getattr(e,'lfs',None),'sha256',None))
assert len(identities)==880
def parse_experiment(text):
 marker='"experiment"';start=text.find(marker)
 if start<0:return None
 colon=text.find(':',start+len(marker));part=text[colon+1:].lstrip()
 try:experiment,end=json.JSONDecoder().raw_decode(part)
 except json.JSONDecodeError:return None
 if not isinstance(experiment,dict):raise ValueError('invalid experiment header')
 return experiment
def fetch(pair):
 row,path=pair;sid=row['sample_id'];out=root/(sid+'.json')
 if out.exists():
  r=json.loads(out.read_text(encoding='utf-8'))
  if r.get('revision')==revision and r.get('published_identity')==identities[path]:return r
 for attempt in range(3):
  try:
   headers={'Authorization':'Bearer '+token,'Range':'bytes=0-262143','Accept-Encoding':'identity'}
   raw=b'';text=b'';decoder=zlib.decompressobj(16+zlib.MAX_WBITS);experiment=None
   with requests.get(hf_hub_url(repo,path,repo_type='dataset',revision=revision),headers=headers,stream=True,timeout=(15,30)) as response:
    response.raise_for_status()
    for block in response.iter_content(8192):
     raw+=block;text+=decoder.decompress(block);experiment=parse_experiment(text.decode('utf-8',errors='ignore'))
     if experiment is not None:break
     if len(raw)>=262144:raise ValueError('experiment not found in bounded prefix')
   if experiment is None:raise ValueError('incomplete experiment prefix')
   if experiment.get('trajectory_id')!=sid:raise ValueError('published sample identity differs')
   r=dict(sample_id=sid,repo_id=repo,revision=revision,published_path=path,published_identity=identities[path],compressed_prefix_bytes=len(raw),compressed_prefix_sha256=hashlib.sha256(raw).hexdigest(),
       experiment=experiment,publication_recovery=row.get('recovery'),status='published_parameter_header_read',verification_scope='immutable HF revision and file identity; prefix read, not full-file checksum')
   out.write_text(json.dumps(r));return r
  except Exception as exc:
   error=type(exc).__name__
   if attempt<2:time.sleep(1)
 return dict(sample_id=sid,status='failed',error_type=error)
result=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for row in pool.map(fetch,zip(rows,paths)):
  result.append(row)
  if len(result)%40==0:print('PROGRESS '+json.dumps(dict(read=len(result),failed=sum(r['status']=='failed' for r in result))),flush=True)
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
        code=REMOTE.replace('REVISION',repr(release['revision'])).replace('ROWS',repr(rows));p.stdin.write((prefix+code).encode());p.stdin.close()
        for line in p.stdout:
            if line.startswith(b'RESULT '):(ROOT/'t03_current_parameter_headers_20261019.json').write_bytes(line[len(b'RESULT '):])
            else:print(line.decode().strip(),flush=True)
        if p.wait():raise RuntimeError('T03 parameter header read failed; remote secrets suppressed')
    finally:
        if p.poll() is None:p.kill();p.wait()


if __name__=='__main__':main()
