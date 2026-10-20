"""Read current HF release layout through existing server credentials and local proxy.

Credentials and signed download URLs never leave the server process or appear in receipts.
This inventory inspects release identities only; it does not certify boundaries.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


REMOTE = '''
import json
from huggingface_hub import HfApi,get_token
api=HfApi(token=get_token())
def entry(e):
 return dict(path=e.path,kind=type(e).__name__,size=getattr(e,'size',None),blob_id=getattr(e,'blob_id',None),lfs_sha256=getattr(getattr(e,'lfs',None),'sha256',None))
for repo in REPOS:
 try:
  info=api.dataset_info(repo,files_metadata=False)
  directories=[]
  for path in ['', 'data'] + EXTRA_PATHS:
   try:
    entries=list(api.list_repo_tree(repo,path_in_repo=path,repo_type='dataset',revision=info.sha))
    directories.append(dict(path=path,entries=[entry(e) for e in entries]))
   except Exception as e: directories.append(dict(path=path,error=type(e).__name__))
  files=[]
  for name in FILES:
   try:
    from huggingface_hub import hf_hub_download
    import pathlib,hashlib,gzip
    file=pathlib.Path(hf_hub_download(repo_id=repo,filename=name,repo_type='dataset',revision=info.sha))
    raw=file.read_bytes()
    text=(gzip.decompress(raw) if name.endswith('.gz') else raw).decode('utf-8')
    files.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),text=text))
   except Exception as e: files.append(dict(path=name,error=type(e).__name__))
  for scene in SCENES:
   path='data/'+scene
   try:
    entries=list(api.list_repo_tree(repo,path_in_repo=path,repo_type='dataset',revision=info.sha))
    directories.append(dict(path=path,entries=[entry(e) for e in entries]))
   except Exception as e: directories.append(dict(path=path,error=type(e).__name__))
  print(json.dumps(dict(repo=repo,revision=info.sha,last_modified=str(info.last_modified),directories=directories,files=files)),flush=True)
 except Exception as e: print(json.dumps(dict(repo=repo,error=type(e).__name__)),flush=True)
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repos',nargs='+',default=['phy2/phydataset','phyeditingvideo/Phyediting'])
    parser.add_argument('--scenes',nargs='+',default=[f'T{i:02}' for i in range(1,21)])
    parser.add_argument('--paths',nargs='*',default=[])
    parser.add_argument('--files',nargs='*',default=[])
    parser.add_argument('--out',default='review/scene_family_completion_20261018/live_release_layout_20261019.json')
    args=parser.parse_args()
    proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ExitOnForwardFailure=yes',
        '-R','127.0.0.1:0:127.0.0.1:7897','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        match=re.search(rb'Allocated port (\d+)',proc.stderr.readline())
        if not match: raise RuntimeError('dynamic SSH proxy forwarding unavailable')
        prefix="import os\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n"%int(match[1])
        code=REMOTE.replace('REPOS',repr(args.repos)).replace('SCENES',repr(args.scenes)).replace('EXTRA_PATHS',repr(args.paths)).replace('FILES',repr(args.files))
        stdout,_=proc.communicate((prefix+code).encode(),timeout=360)
        if proc.returncode: raise RuntimeError('remote release lookup failed')
        rows=[json.loads(line) for line in stdout.splitlines() if line.strip()]
        target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        for row in rows:
            print(json.dumps({k:v for k,v in row.items() if k not in ['directories','files']}),flush=True)
    finally:
        if proc.poll() is None: proc.kill();proc.communicate()


if __name__=='__main__':main()
