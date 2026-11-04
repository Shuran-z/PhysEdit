"""Retrieve only explicit frozen HF paths and accept only the bound video SHA."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
os.environ['HTTPS_PROXY']='http://127.0.0.1:17891'
os.environ['HTTP_PROXY']='http://127.0.0.1:17891'
from huggingface_hub import hf_hub_download

root=Path('/data2/liyuhan/core100_all100_reference_audit_20261101')
jobs=json.loads((root/'JOBS.json').read_text())
previous={r['clip_id']:r for r in json.loads((root/'RESULT.json').read_text())}

def fetch(job):
    if previous[job['clip_id']]['state']!='original_video_not_found_by_hash':return None
    if not job.get('source_repo') or not job.get('revision'):return dict(clip_id=job['clip_id'],state='exact_frozen_hf_locator_missing')
    try:
        p=Path(hf_hub_download(repo_id=job['source_repo'],filename=job['source_video_path'],
                              revision=job['revision'],repo_type='dataset'))
        identity=hashlib.sha256(p.read_bytes()).hexdigest()
        if identity!=job['sha256']:return dict(clip_id=job['clip_id'],state='downloaded_hash_mismatch_not_used',sha256=identity)
        job['extra_video_paths'].append(str(p))
        return dict(clip_id=job['clip_id'],state='exact_frozen_reference_retrieved',path=str(p),sha256=identity)
    except Exception as error:
        # Never print request headers or tokens from provider exceptions.
        return dict(clip_id=job['clip_id'],state='download_failed',error_type=type(error).__name__)

with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:results=[r for r in pool.map(fetch,jobs)if r]
(root/'JOBS.json').write_text(json.dumps(jobs,indent=2))
(root/'EXACT_FETCH.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
