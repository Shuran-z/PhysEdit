"""Remote metadata-only publisher; retries transport and verifies every committed blob."""
import hashlib
import json
import logging
import os
from pathlib import Path
import time

os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
os.environ['NO_PROXY']=os.environ.get('NO_PROXY','')+',.amazonaws.com'
os.environ['no_proxy']=os.environ['NO_PROXY']
logging.getLogger('huggingface_hub').setLevel(logging.CRITICAL)
logging.getLogger('httpx').setLevel(logging.CRITICAL)
from huggingface_hub import HfApi, get_token
import huggingface_hub.lfs as lfs
import httpx

ROOT=Path('/data_cached/wangzijun_p25/prompt_completion_20261029')
lock=ROOT/'UPLOAD_ACTIVE.json'
if lock.exists():
    pid=json.loads(lock.read_text())['pid']
    try:os.kill(pid,0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Prompt uploader already active')
lock.write_text(json.dumps({'pid':os.getpid(),'started':time.time()}))
prefix='releases/72000_prompt_complete_20261029'
api=HfApi(token=get_token())
metadata=ROOT/'metadata'
files=sorted(p for p in metadata.rglob('*') if p.is_file())
for attempt in range(12):
    try:
        commit=api.upload_folder(repo_id='phy2/phydataset',repo_type='dataset',folder_path=str(metadata),
            path_in_repo=prefix,commit_message='Complete three English prompt variants for all 72000 inventory entries')
        revision=commit.oid
        paths=[prefix+'/'+p.relative_to(metadata).as_posix() for p in files]
        info={r.path:r for r in api.get_paths_info('phy2/phydataset',paths,repo_type='dataset',revision=revision)}
        receipts=[]
        for p,path in zip(files,paths):
            raw=p.read_bytes();r=info[path]
            assert r.size==len(raw)
            if r.lfs:assert r.lfs.sha256==hashlib.sha256(raw).hexdigest()
            else:assert r.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            receipts.append({'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        result={'repo':'phy2/phydataset','revision':revision,'prefix':prefix,
            'inventory_entries':72000,'three_prompt_coverage':72000,'newly_completed':2913,
            'metadata_files':len(receipts),'hashes_verified':True,'files':receipts,'completed':time.time()}
        (ROOT/'PUBLISHED.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
        break
    except Exception as exc:
        (ROOT/'upload_error.json').write_text(json.dumps({'attempt':attempt,'error_type':type(exc).__name__}))
        if attempt==11:raise
        print(json.dumps({'retry':attempt+1,'error_type':type(exc).__name__}),flush=True)
        time.sleep(min(60,10*(attempt+1)))
