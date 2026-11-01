"""Publish the audited catalog/card after media consolidation, without changing visibility or license."""
import hashlib
import json
import logging
import os
from pathlib import Path
import time

os.environ['HF_HUB_DISABLE_XET']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
os.environ['NO_PROXY']=os.environ.get('NO_PROXY','')+',.amazonaws.com';os.environ['no_proxy']=os.environ['NO_PROXY']
logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,get_token

ROOT=Path('/data_cached/wangzijun_p25/publication_audit_20261029')
media=json.loads((ROOT/'MEDIA_CONSOLIDATED.json').read_text())
assert media['all_destination_lfs_hashes_verified']
meta=ROOT/'metadata';api=HfApi(token=get_token());repo='phy2/phydataset'
active=ROOT/'CARD_UPLOAD_ACTIVE.json'
if active.exists():
    pid=json.loads(active.read_text())['pid']
    try:os.kill(pid,0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Existing card publisher active')
active.write_text(json.dumps({'pid':os.getpid(),'started':time.time()}))


def retry_preflight(call):
    for attempt in range(6):
        try:return call()
        except Exception:
            if attempt==5:raise
            time.sleep(2*(attempt+1))


before=retry_preflight(lambda:api.repo_info(repo,repo_type='dataset',expand=['sha'])).sha
roots_before={r.path:r.tree_id for r in retry_preflight(lambda:list(api.list_repo_tree(repo,repo_type='dataset',revision=before))) if r.__class__.__name__=='RepoFolder'}
backup='snapshot-before-publication-card-20261029'
retry_preflight(lambda:api.create_branch(repo,repo_type='dataset',branch=backup,revision=before,exist_ok=True))
files=sorted(p for p in meta.rglob('*') if p.is_file())
for attempt in range(12):
    try:
        commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=str(meta),
            commit_message='Publish current PhysEdit introduction and audited scene catalogs with corrected units and source bindings')
        revision=commit.oid;paths=[p.relative_to(meta).as_posix() for p in files]
        info={r.path:r for r in api.get_paths_info(repo,paths,repo_type='dataset',revision=revision)}
        receipts=[]
        for p,path in zip(files,paths):
            raw=p.read_bytes();item=info[path];assert item.size==len(raw)
            h=hashlib.sha256(raw).hexdigest()
            if item.lfs:assert item.lfs.sha256==h
            else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            receipts.append({'path':path,'bytes':len(raw),'sha256':h})
        roots_after={r.path:r.tree_id for r in api.list_repo_tree(repo,repo_type='dataset',revision=revision) if r.__class__.__name__=='RepoFolder'}
        assert 'review' not in roots_after
        for name in ['benchmarks','annotations','assets','scenes']:assert roots_before[name]==roots_after[name]
        assert api.repo_info(repo,repo_type='dataset',revision=revision,expand=['private']).private is True
        assert len(api.get_paths_info(repo,['data/T01/genesis','data/T01/isaac'],repo_type='dataset',revision=revision))==2
        result={'repo':repo,'revision':revision,'prefix':'releases/72000_release_candidate_20261029',
            'entries':72000,'usable_entries':32868,'pending_review':36342,'excluded_entries':2790,
            'current_media_records':69210,'metadata_files':len(files),'all_metadata_hashes_verified':True,
            'media_revision':media['revision'],'benchmark_and_annotation_trees_unchanged':True,
            'review_directory_absent':True,'visibility_changed':False,'license_changed':False,
            'backup_branch':backup,'files':receipts,'completed':time.time()}
        (ROOT/'PUBLISHED.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True);break
    except Exception as exc:
        (ROOT/'card_upload_error.json').write_text(json.dumps({'attempt':attempt,'error_type':type(exc).__name__}))
        if attempt==11:raise
        print(json.dumps({'retry':attempt+1,'error_type':type(exc).__name__}),flush=True)
        time.sleep(min(60,10*(attempt+1)))
