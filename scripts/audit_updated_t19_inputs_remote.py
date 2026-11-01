"""Verify original input identity for individually updated HF T19 video files."""
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import time

os.environ['NO_PROXY']='.amazonaws.com';logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,get_token

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029');out=ROOT/'updated_media_review';out.mkdir(exist_ok=True)
source=ROOT/'isaac_admission/metadata/releases/72000_release_candidate_20261029/videos.jsonl.gz'
rows={r['video_id']:r for r in map(json.loads,gzip.open(source,'rt'))}
comparison=json.loads((ROOT/'current960_media_comparison.json').read_text());changed=[r for r in comparison['checks'] if not r['same_bytes']]
paths=sorted({r['path'].rsplit('/',1)[0]+'/config.json' for r in changed})
api=HfApi(token=get_token())
for attempt in range(6):
    try:info={r.path:r for r in api.get_paths_info('phy2/phydataset',paths,repo_type='dataset',revision=comparison['revision'])};break
    except Exception:
        if attempt==5:raise
        time.sleep(2)
results=[]
for r in changed:
    path=r['path'].rsplit('/',1)[0]+'/config.json';local=Path(rows[r['video_id']]['local_source']).parent/'config.json';b=local.read_bytes()
    git=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    results.append({'video_id':r['video_id'],'config_path':path,'local_original_config':str(local),'config_sha256':hashlib.sha256(b).hexdigest(),'same_config_bytes':path in info and info[path].blob_id==git,'current_config_blob_id':info[path].blob_id if path in info else None,'original_config_blob_id':git})
(out/'input_checks.json').write_text(json.dumps(results,indent=2))
summary={'updated_videos':len(results),'unique_configurations':len(paths),'config_identical':sum(r['same_config_bytes'] for r in results),'config_different_or_missing':sum(not r['same_config_bytes'] for r in results)}
(out/'input_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
