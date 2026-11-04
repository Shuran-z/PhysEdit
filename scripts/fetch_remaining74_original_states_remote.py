"""Recover exact released sidecars, without guessing a simulation configuration."""
import gzip
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
os.environ.update(HTTPS_PROXY='http://127.0.0.1:17891',HTTP_PROXY='http://127.0.0.1:17891')
from huggingface_hub import hf_hub_download
ROOT=Path('/data2/liyuhan/core100_remaining74_admission_20261101')
def fetch(j):
    r=dict(j)
    try:
        p=Path(hf_hub_download(repo_id=j['repo_id'],filename=j['path'],revision=j['revision'],repo_type='dataset'))
        stored=p.read_bytes();raw=gzip.decompress(stored)if p.suffix=='.gz'else stored
        digest=hashlib.sha256(raw).hexdigest()
        if j.get('expected_sha256'):assert j['expected_sha256']in(digest,hashlib.sha256(stored).hexdigest())
        r.update(status='exact_revision_state_recovered',state_path=str(p),state_sha256=digest,stored_state_sha256=hashlib.sha256(stored).hexdigest())
    except Exception as e:r.update(status='failed',error_type=type(e).__name__)
    return r
out=[]
name=os.environ.get('CORE100_STATE_FETCH','STATE_FETCH')
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
    for r in pool.map(fetch,json.loads((ROOT/(name+'.json')).read_text())):
        out.append(r)
        (ROOT/(name+'_RESULT.json')).write_text(json.dumps(out,indent=2))
print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'])for r in out]))
