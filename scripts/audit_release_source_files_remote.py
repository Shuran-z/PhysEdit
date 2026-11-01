"""Check every distinct pinned source path; keep transport failures distinct from missing files."""
import collections
import concurrent.futures
import gzip
import json
import logging
import os
from pathlib import Path
import time

logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,get_token

ROOT=Path('/data_cached/wangzijun_p25/publication_audit_20261029')
with gzip.open(ROOT/'source_requests.jsonl.gz','rt') as f:rows=list(map(json.loads,f))
groups=collections.defaultdict(list)
for r in rows:groups[r['repo'],r['revision']].append(r)
jobs=[]
for (repo,rev),items in groups.items():
    for i in range(0,len(items),500):jobs.append((repo,rev,items[i:i+500]))
api=HfApi(token=get_token());repos={}
for repo in {r['repo'] for r in rows}:
    for attempt in range(4):
        try:
            info=api.repo_info(repo,repo_type='dataset')
            repos[repo]={'private':info.private,'revision':info.sha};break
        except Exception:
            if attempt==3:raise
            time.sleep(1)


def check(job):
    repo,rev,items=job
    for attempt in range(4):
        try:
            infos={x.path:x for x in api.get_paths_info(repo,[r['path'] for r in items],repo_type='dataset',revision=rev)}
            result=[]
            for r in items:
                x=infos.get(r['path']);status='MISSING'
                if x is not None:
                    if r['archive']:status='ARCHIVE_EXISTS_AT_PINNED_REVISION'
                    elif not x.lfs:status='NON_LFS_REQUIRES_CONTENT_HASH_CHECK'
                    elif x.lfs.sha256!=r['expected_sha256']:status='VIDEO_HASH_MISMATCH'
                    else:status='VIDEO_LFS_HASH_MATCH'
                result.append({**r,'status':status,'remote_bytes':x.size if x else None,
                               'remote_lfs_sha256':x.lfs.sha256 if x and x.lfs else None})
            return result
        except Exception as exc:
            if attempt==3:return [{**r,'status':'TRANSPORT_UNVERIFIED','error_type':type(exc).__name__} for r in items]
            time.sleep(1+attempt)


results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for i,result in enumerate(pool.map(check,jobs),1):
        results.extend(result)
        (ROOT/'source_audit_progress.json').write_text(json.dumps({'completed_batches':i,'total_batches':len(jobs),'checked_files':len(results)}))
        if i%10==0:print(json.dumps({'completed_batches':i,'total_batches':len(jobs)}),flush=True)
with gzip.open(ROOT/'source_file_results.jsonl.gz','wt') as f:
    for r in results:f.write(json.dumps(r)+'\n')
summary={'distinct_source_files':len(results),'video_entries':sum(r['entries'] for r in results),
         'status_counts':dict(collections.Counter(r['status'] for r in results)),
         'entries_by_status':dict(collections.Counter({status:sum(r['entries'] for r in results if r['status']==status) for status in {r['status'] for r in results}})),
         'repositories':repos,'fresh_video_decode_performed':False,
         'archive_member_content_reverified':False}
(ROOT/'source_file_audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
