"""Publish only the author-approved five-reference Core100 update on p25."""
import argparse
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import time

logging.disable(logging.CRITICAL)
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(root):
    from huggingface_hub import HfApi,CommitOperationAdd,get_token,hf_hub_download
    root=Path(root);project=root/'project';name='core100_t19_isaac_v1_20261031'
    lock=(root/'publish.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    api=HfApi(token=get_token());repo='phy2/phydataset'
    head=api.repo_info(repo,repo_type='dataset').sha
    print(json.dumps(dict(phase='checking_current_reference',head=head)),flush=True)
    rel='catalog/active_core100_conditions.json'
    parent_revision=(head if api.file_exists(repo,rel,repo_type='dataset',revision=head)
                     else 'f23ee3577952ec1e5357c8a729bfc4daa5c7272d')
    current=Path(hf_hub_download(repo,rel,repo_type='dataset',revision=parent_revision,token=get_token()))
    old=json.loads(current.read_text());new=json.loads((project/rel).read_text())
    prefix='benchmarks/'+name
    if old.get('version')==new['version']:
        revision=head
    else:
        assert old['version']=='core100-declared-controls-v6-20261023', 'Active Core100 changed; cannot overwrite another version'
        parent=Path(hf_hub_download(repo,old['known_conditions'],repo_type='dataset',revision=parent_revision,token=get_token()))
        before={c['clip_id']:c for c in json.loads(parent.read_text())['tasks']}
        after=json.loads((project/prefix/'known_conditions.json').read_text())
        assert len(after['tasks'])==100
        assert all(c==before[c['clip_id']]for c in after['tasks']if not c['clip_id'].startswith('T19'))
        backup=project/prefix/'parent_active_core100_conditions.json'
        backup.write_bytes(current.read_bytes())
        files=[p for p in (project/prefix).rglob('*')if p.is_file()]+[project/rel]
        ops=[CommitOperationAdd(path_in_repo=p.relative_to(project).as_posix(),path_or_fileobj=str(p))for p in files]
        print(json.dumps(dict(phase='uploading_reference_release',files=len(files))),flush=True)
        commit=api.create_commit(repo,repo_type='dataset',parent_commit=head,operations=ops,
            commit_message='Activate five reviewed Isaac T19 references with parameter and boundary bindings; preserve other 95 inputs')
        revision=commit.oid
    print(json.dumps(dict(phase='verifying_uploaded_hashes',revision=revision)),flush=True)
    files=[p for p in (project/prefix).rglob('*')if p.is_file()]+[project/rel]
    names=[p.relative_to(project).as_posix()for p in files]
    for attempt in range(5):
        try:
            info={x.path:x for x in api.get_paths_info(repo,names,repo_type='dataset',revision=revision)}
            break
        except Exception as error:
            response=getattr(error,'response',None)
            status=getattr(response,'status_code',None)
            if status not in (429,500,502,503,504) or attempt==4:raise
            delay=min(40,5*2**attempt)
            print(json.dumps(dict(phase='verification_retry',http_status=status,wait_seconds=delay)),flush=True)
            time.sleep(delay)
    for p in files:
        key=p.relative_to(project).as_posix();entry=info[key];raw=p.read_bytes()
        assert entry.size==len(raw),key
        if entry.lfs:
            assert entry.lfs.sha256==sha(p),key
        else:
            assert entry.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),key
    receipt=dict(repo=repo,revision=revision,version=new['version'],files_verified=len(files),
        replaced_reference_cases=5,unchanged_reference_cases=95,near_reference_cases=4,pairs=2,
        old_model_outputs_or_annotations_changed=False,new_generation_required=True,
        manifest_sha256=sha(project/prefix/'MANIFEST.json'),active_pointer_sha256=sha(project/rel),
        parent_pointer_revision=parent_revision)
    (root/'PUBLISHED.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
    try:
        main(args.root)
    except Exception as e:
        # Exceptions from storage can contain signed URLs. Do not emit them.
        print(json.dumps(dict(status='publication_failed',exception=type(e).__name__,
            http_status=getattr(getattr(e,'response',None),'status_code',None))),flush=True)
        raise SystemExit(1)
