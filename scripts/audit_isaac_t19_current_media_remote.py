"""Read-only compare of all selected Isaac T19 bytes with the current HF tree."""
import fcntl
import gzip
import json
import logging
import os
from pathlib import Path
import time

os.environ['NO_PROXY']='.amazonaws.com';logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,get_token

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029')
lock=open(ROOT/'current960_audit.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
api=HfApi(token=get_token());repo='phy2/phydataset';revision='16cfc2b67fdfe1de274b088d830a06a3095d23fb'
source=ROOT/'isaac_admission/metadata/releases/72000_release_candidate_20261029/videos.jsonl.gz'
rows=[r for r in map(json.loads,gzip.open(source,'rt')) if r['scene']=='T19' and r['engine']=='isaac']
assert len(rows)==960
checks=[]
for start in range(0,len(rows),200):
    batch=rows[start:start+200]
    paths=['data/T19/isaac_44_480p_20260924/videos/'+r['native_sample_id']+'/'+r['camera']+'.mp4' for r in batch]
    for attempt in range(6):
        try:info={r.path:r for r in api.get_paths_info(repo,paths,repo_type='dataset',revision=revision)};break
        except Exception as exc:
            (ROOT/'current960_audit_progress.json').write_text(json.dumps({'completed':start,'attempt':attempt,'error':type(exc).__name__}))
            if attempt==5:raise
            time.sleep(2)
    for r,p in zip(batch,paths):
        actual=info[p].lfs.sha256 if p in info and info[p].lfs else None
        checks.append({'video_id':r['video_id'],'path':p,'inventory_sha256':r['sha256'],'current_sha256':actual,'same_bytes':actual==r['sha256']})
    result={'revision':revision,'records_checked':len(checks),'same_bytes':sum(r['same_bytes'] for r in checks),'different_or_missing':sum(not r['same_bytes'] for r in checks),'checks':checks}
    (ROOT/'current960_media_comparison.json').write_text(json.dumps(result,indent=2))
    (ROOT/'current960_audit_progress.json').write_text(json.dumps({k:v for k,v in result.items() if k!='checks'}));print(json.dumps({k:v for k,v in result.items() if k!='checks'}),flush=True)
