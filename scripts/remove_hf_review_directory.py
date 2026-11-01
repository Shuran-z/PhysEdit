"""Remove the explicitly authorized review/ tree, with exact-parent commit and backup."""
import hashlib
import io
import json
import logging
import os
from pathlib import Path

logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete, get_token

ROOT=Path('/data_cached/wangzijun_p25/review_removal_20261029')
plan=json.loads((ROOT/'removal_plan.json').read_text())
api=HfApi(token=get_token());repo=plan['repo'];before=plan['source_revision']
assert api.repo_info(repo,repo_type='dataset').sha==before, 'Repository advanced; refresh preflight before mutation'
assert plan['active_manifest_references_to_review']==0 and plan['manifest_entries_checked']==72000
files=[x for x in api.list_repo_tree(repo,path_in_repo='review',repo_type='dataset',revision=before,recursive=True)
       if x.__class__.__name__=='RepoFile']
assert {x.path:x.blob_id for x in files}=={x['path']:x['blob_id'] for x in plan['deleted_files']}
assert all(x.path.startswith('review/') and not x.path.startswith('/') for x in files)
roots_before={x.path:x.tree_id for x in api.list_repo_tree(repo,repo_type='dataset',revision=before)
              if x.__class__.__name__=='RepoFolder'}
api.create_branch(repo,repo_type='dataset',branch=plan['backup_branch'],revision=before,exist_ok=True)
assert api.repo_info(repo,repo_type='dataset',revision=plan['backup_branch']).sha==before
operations=[CommitOperationDelete(path_in_repo=x.path) for x in files]
for name in ['README.md','DIRECTORY.md']:
    operations.append(CommitOperationAdd(path_in_repo=name,path_or_fileobj=(ROOT/name).read_bytes()))
operations.append(CommitOperationAdd(path_in_repo='catalog/review_removal_20261029.json',
                                     path_or_fileobj=(ROOT/'removal_plan.json').read_bytes()))
commit=api.create_commit(repo,repo_type='dataset',operations=operations,parent_commit=before,
    commit_message='Remove review directory from main and point release documentation to unified 72000 catalog')
after=commit.oid
roots_after={x.path:x.tree_id for x in api.list_repo_tree(repo,repo_type='dataset',revision=after)
             if x.__class__.__name__=='RepoFolder'}
assert 'review' not in roots_after
for name in ['data','benchmarks','annotations','assets','scenes','releases','archive']:
    assert roots_before[name]==roots_after[name], 'Unrelated tree changed: '+name
receipt={'repo':repo,'revision':after,'source_revision':before,'deleted_files':len(files),
 'deleted_tree':'review/','backup_branch':plan['backup_branch'],'active_manifest_references':0,
 'unrelated_data_and_evaluation_trees_unchanged':True,'review_directory_absent':True}
(ROOT/'REMOVED.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt),flush=True)
