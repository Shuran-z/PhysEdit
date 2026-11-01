"""Copy pinned source objects server-side into native scene/engine directories."""
import collections
import concurrent.futures
import gzip
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import time

logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,CommitOperationCopy,get_token
from huggingface_hub.hf_api import RepoFile
import huggingface_hub.hf_api as hub_api
from huggingface_hub._commit_api import _CopySource

ROOT=Path('/data_cached/wangzijun_p25/publication_audit_20261029')
lock=ROOT/'MEDIA_COPY_ACTIVE.json'
if lock.exists():
    pid=json.loads(lock.read_text())['pid']
    try:os.kill(pid,0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Existing media consolidation process is active')
lock.write_text(json.dumps({'pid':os.getpid(),'started':time.time()}))
plan_path=ROOT/'media_copy_plan.jsonl.gz'
plan_hash=hashlib.sha256(plan_path.read_bytes()).hexdigest()
with gzip.open(plan_path,'rt') as f:rows=list(map(json.loads,f))
excluded=set(json.loads((ROOT/'excluded_media_destinations.json').read_text()))
api=HfApi(token=get_token());repo='phy2/phydataset'
# Reuse the freshly audited immutable-revision LFS metadata rather than fetching
# the same 56k source objects again for each copy. Destination hashes are still
# verified independently after every commit. Unknown source metadata is fetched.
source_cache={}
with gzip.open(ROOT/'source_file_results.jsonl.gz','rt') as f:
    for raw in f:
        r=json.loads(raw)
        if not r.get('remote_lfs_sha256'):continue
        source_cache[(r['repo'],r['revision'],r['path'])]=RepoFile(path=r['path'],size=r['remote_bytes'],oid=None,
            lfs={'size':r['remote_bytes'],'oid':r['remote_lfs_sha256'],'pointerSize':0})


def fetch_copy_sources(copies,repo_type,repo_id,headers,revision,endpoint=None):
    copies=list(copies);found={};needed=collections.defaultdict(list)
    for op in copies:
        key=(op.src_repo_id or repo_id,op.src_revision or revision,op.src_path_in_repo)
        if op.src_repo_id and (key not in source_cache or not source_cache[key].xet_hash):
            needed[key[0],key[1]].append(key[2])
    for (src,rev),paths in needed.items():
        chunks=[paths[i:i+400] for i in range(0,len(paths),400)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            parts=list(pool.map(lambda chunk:api.get_paths_info(src,chunk,repo_type='dataset',revision=rev),chunks))
        for part in parts:
            for info in part:source_cache[src,rev,info.path]=info
    for op in copies:
        key=(op.src_repo_id or repo_id,op.src_revision or revision,op.src_path_in_repo)
        if key not in source_cache:
            source_cache[key]=api.get_paths_info(key[0],[key[2]],repo_type='dataset',revision=key[1])[0]
        info=source_cache[key];assert info.lfs
        found[_CopySource(op.src_repo_id,op.src_repo_type,op.src_path_in_repo,op.src_revision)]=info
    return found


hub_api._fetch_files_to_copy=fetch_copy_sources


def paths_info(paths,revision):
    chunks=[paths[i:i+400] for i in range(0,len(paths),400)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        parts=list(pool.map(lambda chunk:api.get_paths_info(repo,chunk,repo_type='dataset',revision=revision),chunks))
    return {r.path:r for part in parts for r in part}
progress_path=ROOT/'media_copy_progress.json'
if progress_path.exists():
    state=json.loads(progress_path.read_text());assert state['plan_sha256']==plan_hash
else:
    before=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
    branch='snapshot-before-media-consolidation-20261029'
    api.create_branch(repo,repo_type='dataset',branch=branch,revision=before,exist_ok=True)
    assert api.repo_info(repo,repo_type='dataset',revision=branch,expand=['sha']).sha==before
    state={'plan_sha256':plan_hash,'initial_revision':before,'backup_branch':branch,
           'completed_operations':0,'total_operations':len(rows),'commits':[]}


def save():
    temp=progress_path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));temp.replace(progress_path)


while state['completed_operations']<len(rows):
    start=state['completed_operations'];source_batch=rows[start:start+4000]
    batch=[r for r in source_batch if r['destination_path'] not in excluded]
    for r in batch:
        assert r['destination_path'].startswith('data/') and '..' not in r['destination_path'].split('/')
    expected={r['destination_path']:r['expected_video_sha256'] for r in batch}
    archives=collections.defaultdict(list)
    for r in batch:
        if r['archive']:archives[r['source_repo'],r['source_revision']].append(r)
    for (source_repo,rev),items in archives.items():
        infos={r.path:r for r in api.get_paths_info(source_repo,[x['source_path'] for x in items],repo_type='dataset',revision=rev)}
        for r in items:
            item=infos[r['source_path']];assert item.lfs
            expected[r['destination_path']]=item.lfs.sha256
    for attempt in range(8):
        try:
            head=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
            existing=paths_info(list(expected),head)
            for path,info in existing.items():
                assert info.lfs and info.lfs.sha256==expected[path], 'Conflicting destination object'
            missing=[r for r in batch if r['destination_path'] not in existing]
            if missing:
                operations=[CommitOperationCopy(src_path_in_repo=r['source_path'],src_revision=r['source_revision'],
                    src_repo_id=r['source_repo'] if r['source_repo']!=repo else None,
                    src_repo_type='dataset' if r['source_repo']!=repo else None,
                    path_in_repo=r['destination_path']) for r in missing]
                commit=api.create_commit(repo,repo_type='dataset',operations=operations,parent_commit=head,
                    commit_message=f'Consolidate pinned scene media {start+1}-{start+len(batch)} of {len(rows)}')
                head=commit.oid
            verified=paths_info(list(expected),head)
            assert len(verified)==len(batch)
            assert all(verified[p].lfs and verified[p].lfs.sha256==h for p,h in expected.items())
            state['completed_operations']=start+len(source_batch);state['revision']=head
            state['skipped_retired_objects']=state.get('skipped_retired_objects',0)+len(source_batch)-len(batch)
            state['copied_objects']=state['completed_operations']-state['skipped_retired_objects']
            state['commits'].append({'revision':head,'start':start,'count':len(batch)})
            save();print(json.dumps({'processed_operations':state['completed_operations'],'copied_objects':state['copied_objects'],
                'skipped_retired_objects':state['skipped_retired_objects'],'total_source_operations':len(rows),'revision':head}),flush=True)
            break
        except Exception as exc:
            (ROOT/'media_copy_error.json').write_text(json.dumps({'start':start,'attempt':attempt,'error_type':type(exc).__name__,
                'http_status':getattr(getattr(exc,'response',None),'status_code',None),
                'message':re.sub(r'https?://\S+','[URL]',str(exc))[:1200]}))
            if attempt==7:raise
            time.sleep(min(30,3*(attempt+1)))
state['completed']=time.time();state['all_destination_lfs_hashes_verified']=True
(ROOT/'MEDIA_CONSOLIDATED.json').write_text(json.dumps(state,indent=2))
print(json.dumps({k:v for k,v in state.items() if k!='commits'}),flush=True)
