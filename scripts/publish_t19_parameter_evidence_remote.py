"""Attach completed original-parameter checks without changing quality decisions."""
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil

logging.disable(logging.CRITICAL)
os.environ['HF_HUB_DISABLE_XET']='1';os.environ['NO_PROXY']='.amazonaws.com'
from huggingface_hub import HfApi,get_token

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029')
PREFIX='releases/72000_release_candidate_20261029/t19_review'
dest=ROOT/'metadata'/PREFIX
summary=json.loads((ROOT/'parameter_check_summary.json').read_text())
assert summary['groups']==610 and summary['facts_checked']==10512 and summary['groups_with_parameter_mismatch']==0
for name in ['results.json','original_parameter_checks.json','parameter_check_summary.json','accepted_parameter_checks.json']:
    shutil.copy2(ROOT/name,dest/name)
api=HfApi(token=get_token());repo='phy2/phydataset'
prior=json.loads((ROOT/'PUBLISHED.json').read_text())
head=api.repo_info(repo,repo_type='dataset',expand=['sha']).sha
assert head==prior['revision']
commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=str(dest),path_in_repo=PREFIX,
    parent_commit=head,commit_message='Attach original-state evidence: 610 T19 configurations and 10512 matching parameter facts; visual review remains incomplete')
files=sorted(p for p in dest.rglob('*') if p.is_file())
info={x.path:x for x in api.get_paths_info(repo,[PREFIX+'/'+p.relative_to(dest).as_posix() for p in files],repo_type='dataset',revision=commit.oid)}
for p in files:
    b=p.read_bytes();item=info[PREFIX+'/'+p.relative_to(dest).as_posix()];assert item.size==len(b)
    if item.lfs:assert item.lfs.sha256==hashlib.sha256(b).hexdigest()
    else:assert item.blob_id==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
prior.update(revision=commit.oid,parameter_checks=summary,all_parameter_evidence_hashes_verified=True)
(ROOT/'PUBLISHED.json').write_text(json.dumps(prior,indent=2));print(json.dumps({'published':commit.oid,'parameter_checks':summary}),flush=True)
