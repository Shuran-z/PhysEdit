"""Stage the existing 72,000 videos directly under their existing scene folders.

No model calls, render changes, renamed video IDs, or split changes. Run on p25.
The temporary branch is removed after an exact-lease fast-forward publication.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
import time

os.environ['HTTPS_PROXY'] = os.environ['HTTP_PROXY'] = 'http://127.0.0.1:17891'
os.environ.pop('HF_HUB_DISABLE_XET', None)
os.environ['HF_XET_CACHE'] = '/data_cached/wangzijun_p25/scene_videos_20261031/xet_cache'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,.amazonaws.com'
from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationCopy, get_token

ROOT = Path('/data_cached/wangzijun_p25/scene_videos_20261031')
META = Path('/data_cached/wangzijun_p25/t19_final_release_20261030/stage/releases/physedit')
REPO = 'phy2/phydataset'
BASE = '11dff049f7d104728d462121b7bb9be9d72a4538'
BRANCH = 'codex/scene-videos'


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def load(path):
    return json.loads(path.read_text())


def read_retry(callback):
    for attempt in range(8):
        try:
            return callback()
        except Exception as error:
            response = getattr(error, 'response', None)
            status = getattr(response, 'status_code', None)
            if status is not None and status < 500 and status != 429:
                raise
            if attempt == 7:
                raise
            delay = min(2**attempt,20)
            if status == 429:
                match = re.search(r';t=(\d+)',response.headers.get('RateLimit',''))
                if match:
                    delay = int(match.group(1))+1
            print(json.dumps(dict(retrying_read=type(error).__name__, status=status, wait_seconds=delay, attempt=attempt+1)),flush=True)
            time.sleep(delay)


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare():
    ROOT.mkdir(exist_ok=True)
    api = HfApi(token=get_token())
    assert api.repo_info(REPO, repo_type='dataset').sha == BASE
    info = api.get_paths_info(REPO, ['releases/physedit/catalog/videos.jsonl.gz'],
                             repo_type='dataset', revision=BASE)[0]
    assert info.lfs.sha256 == file_sha(META/'catalog/videos.jsonl.gz')
    rows = []
    with gzip.open(META/'catalog/videos.jsonl.gz', 'rt') as stream:
        for line in stream:
            source = json.loads(line)
            assert source['canonical_filename'] == source['canonical_video_id']+'.mp4'
            rows.append(dict(id=source['canonical_video_id'], scene=source['quota_scene'],
                path='data/'+source['quota_scene']+'/'+source['canonical_filename'],
                sha256=source['sha256'], source=source['download'],
                local_source=source.get('local_source'), old_path=source['canonical_path']))
    counts = collections.Counter(r['scene'] for r in rows)
    assert counts == {f'T{i:02}':3600 for i in range(1,21)}
    assert len({r['path'] for r in rows}) == 72000
    if (ROOT/'PLAN.json').exists():
        assert load(ROOT/'PLAN.json')['rows'] == rows
    else:
        dump(ROOT/'PLAN.json', dict(base=BASE, branch=BRANCH, repo=REPO,
            counts=dict(counts), rows=rows, scientific_inputs_modified=False))
        api.create_branch(REPO, branch=BRANCH, revision=BASE, repo_type='dataset')
        dump(ROOT/'STATE.json', dict(base=BASE, branch=BRANCH, head=BASE,
            completed_ids=[], receipts=[], phase='prepared'))
    print(json.dumps(dict(phase='prepared', rows=len(rows), scenes=dict(counts))), flush=True)


def verify_new(api, expected, revision):
    for start in range(0, len(expected), 500):
        part = expected[start:start+500]
        infos = {x.path:x for x in read_retry(lambda: api.get_paths_info(REPO, [r['path'] for r in part],
            repo_type='dataset', revision=revision))}
        for row in part:
            entry = infos[row['path']]
            assert entry.lfs and entry.lfs.sha256 == row['sha256'], row['id']


def commit_rows(api, state, selected, operations, kind):
    assert read_retry(lambda: api.repo_info(REPO, repo_type='dataset', revision=BRANCH)).sha == state['head']
    started = time.time()
    for attempt in range(8):
        try:
            commit = api.create_commit(REPO, repo_type='dataset', revision=BRANCH,
                parent_commit=state['head'], operations=operations, num_threads=48,
                commit_message='Place existing videos directly in their scene folders')
            revision = commit.oid
            break
        except Exception:
            current = read_retry(lambda: api.repo_info(REPO, repo_type='dataset', revision=BRANCH)).sha
            if current != state['head']:
                verify_new(api, selected, current)
                revision = current
                break
            if attempt == 7:
                raise
            time.sleep(min(2**attempt,20))
    # Persist the accepted commit before potentially interruptible remote verification.
    state['head'] = revision
    state['pending_verification'] = selected
    dump(ROOT/'STATE.json', state)
    verify_new(api, selected, revision)
    state['completed_ids'] = sorted(set(state['completed_ids']) | {r['id'] for r in selected})
    state.pop('pending_verification', None)
    state['receipts'].append(dict(revision=revision, kind=kind, count=len(selected),
        elapsed_seconds=round(time.time()-started,2)))
    state['phase'] = 'staging_videos'
    dump(ROOT/'STATE.json', state)
    print(json.dumps(dict(completed=len(state['completed_ids']), total=72000,
        kind=kind, added=len(selected), seconds=round(time.time()-started,2))), flush=True)


def pilot():
    plan, state = load(ROOT/'PLAN.json'), load(ROOT/'STATE.json')
    api = HfApi(token=get_token())
    if state.get('pending_verification'):
        verify_new(api, state['pending_verification'], state['head'])
        state['completed_ids'] = sorted(set(state['completed_ids']) | {r['id'] for r in state['pending_verification']})
        state.pop('pending_verification')
        dump(ROOT/'STATE.json',state)
    selected = [r for r in plan['rows'] if r['source'].get('member') and r['id'] not in state['completed_ids']][:75]
    for row in selected:
        assert Path(row['local_source']).is_file()
        assert file_sha(row['local_source']) == row['sha256']
    operations = [CommitOperationAdd(path_in_repo=r['path'], path_or_fileobj=r['local_source']) for r in selected]
    if selected:
        commit_rows(api, state, selected, operations, 'individual_from_archive_source')


def copy_direct():
    plan, state = load(ROOT/'PLAN.json'), load(ROOT/'STATE.json')
    api = HfApi(token=get_token())
    if state.get('pending_verification'):
        verify_new(api, state['pending_verification'], state['head'])
        state['completed_ids'] = sorted(set(state['completed_ids']) | {r['id'] for r in state['pending_verification']})
        state.pop('pending_verification')
        dump(ROOT/'STATE.json',state)
    done = set(state['completed_ids'])
    pending = [r for r in plan['rows'] if not r['source'].get('member') and r['id'] not in done]
    for start in range(0, len(pending), 5000):
        part = pending[start:start+5000]
        operations = [CommitOperationCopy(src_path_in_repo=r['source']['path'],
            src_revision=r['source']['revision'], path_in_repo=r['path']) for r in part]
        commit_rows(api, state, part, operations, 'same_bytes_server_copy')


def preupload_local():
    """Upload blobs in parallel without changing the working branch's commit."""
    plan = load(ROOT/'PLAN.json')
    api = HfApi(token=get_token())
    receipt_path = ROOT/'PREUPLOADED.json'
    uploaded = load(receipt_path) if receipt_path.exists() else dict(ids=[], failures=[])
    done = set(uploaded['ids']) | set(load(ROOT/'STATE.json')['completed_ids'])
    pending = [r for r in plan['rows'] if r['source'].get('member') and r['id'] not in done]
    good = []
    for row in pending:
        source = Path(row.get('local_source') or '/absent')
        alternate = ROOT/'sg88_sources'/(row['id']+'.mp4')
        if not source.is_file() and alternate.is_file():
            source = alternate
        if source.is_file() and file_sha(source) == row['sha256']:
            row['upload_local'] = str(source)
            good.append(row)
        else:
            uploaded['failures'].append(row['id'])
    previous = {r['id']:r for r in load(ROOT/'LOCAL_UPLOAD_ROWS.json')} if (ROOT/'LOCAL_UPLOAD_ROWS.json').exists() else {}
    previous.update({r['id']:r for r in good})
    dump(ROOT/'LOCAL_UPLOAD_ROWS.json', list(previous.values()))
    uploaded['failures'] = sorted(set(uploaded['failures']) - set(previous))
    dump(receipt_path, uploaded)
    print(json.dumps(dict(local_hashes_matched=len(good), needs_immutable_archive=len(uploaded['failures']))), flush=True)
    for start in range(0, len(good), 1000):
        part = good[start:start+1000]
        additions = [CommitOperationAdd(path_in_repo=r['path'], path_or_fileobj=r['upload_local']) for r in part]
        api.preupload_lfs_files(REPO, additions, repo_type='dataset', revision=BRANCH,
                               num_threads=48, free_memory=False)
        uploaded['ids'] = sorted(set(uploaded['ids']) | {r['id'] for r in part})
        dump(receipt_path, uploaded)
        print(json.dumps(dict(preuploaded=len(uploaded['ids']), total_archived=15057)), flush=True)


def commit_local():
    plan, state = load(ROOT/'PLAN.json'), load(ROOT/'STATE.json')
    rows = {r['id']:r for r in load(ROOT/'LOCAL_UPLOAD_ROWS.json')}
    api = HfApi(token=get_token())
    done = set(state['completed_ids'])
    pending = [r for r in rows.values() if r['id'] not in done]
    for start in range(0, len(pending), 1000):
        part = pending[start:start+1000]
        operations = [CommitOperationAdd(path_in_repo=r['path'], path_or_fileobj=r['upload_local']) for r in part]
        commit_rows(api, state, part, operations, 'individual_verified_mp4')


def commit_preuploaded():
    """Commit completed preuploads without re-uploading their bytes after a checkpoint.

    This uses the installed SDK's NDJSON transport (the same final step as
    create_commit). The recorded successful preupload and local SHA are required.
    """
    from huggingface_hub._commit_api import _send_commit
    from urllib.parse import quote
    plan=load(ROOT/'PLAN.json');api=HfApi(token=get_token())
    direct={r['id']for r in plan['rows']if not r['source'].get('member')}
    state=load(ROOT/'STATE.json');assert direct<=set(state['completed_ids'])
    last_wait=0
    while len(set(state['completed_ids']))<72000:
        try:
            journal=load(ROOT/'PREUPLOADED.json')
        except json.JSONDecodeError:
            time.sleep(1);continue
        sources={r['id']:r for r in load(ROOT/'LOCAL_UPLOAD_ROWS.json')}
        ready=sorted(set(journal['ids'])-set(state['completed_ids']))
        if not ready:
            if time.time()-last_wait>60:
                print(json.dumps(dict(completed=len(state['completed_ids']),waiting_for_preupload=True)),flush=True);last_wait=time.time()
            time.sleep(10);continue
        part=[sources[key]for key in ready[:5000]];operations=[]
        for row in part:
            op=CommitOperationAdd(path_in_repo=row['path'],path_or_fileobj=row['upload_local'])
            assert op.upload_info.sha256.hex()==row['sha256']
            op._upload_mode='lfs'  # exact state of an addition returned by preupload_lfs_files
            op._is_uploaded=True
            operations.append(op)
        assert read_retry(lambda:api.repo_info(REPO,repo_type='dataset',revision=BRANCH)).sha==state['head']
        started=time.time()
        c=_send_commit(operations=operations,files_to_copy={},
            commit_message='Expose the already-uploaded MP4 files in their scene folders',
            commit_description='',repo_type='dataset',repo_id=REPO,
            headers=api._build_hf_headers(token=get_token()),revision=quote(BRANCH,safe=''),
            endpoint=api.endpoint,parent_commit=state['head'])
        state['head']=c.oid;state['pending_verification']=part;dump(ROOT/'STATE.json',state)
        verify_new(api,part,c.oid)
        state['completed_ids']=sorted(set(state['completed_ids'])|{r['id']for r in part})
        state.pop('pending_verification',None)
        state['receipts'].append(dict(revision=c.oid,kind='committed_successful_preuploads',count=len(part)))
        dump(ROOT/'STATE.json',state)
        print(json.dumps(dict(completed=len(state['completed_ids']),total=72000,added=len(part),seconds=round(time.time()-started,2))),flush=True)


def stage_sources():
    state = load(ROOT/'STATE.json')
    assert len(set(state['completed_ids'])) == 72000 and not state.get('pending_verification')
    if (ROOT/'AUXILIARY.json').exists():
        assert load(ROOT/'AUXILIARY.json')['revision'] == state['head']
        return
    inventory = load(Path('/data_cached/wangzijun_p25/t19_final_release_20261030/size_audit_20261031/FILES.json'))
    files = [r for r in inventory if r['path'].startswith('data/') and r['path'].endswith('.tar.gz')]
    targets = []
    for r in files:
        targets.append(dict(source_path=r['path'],path='releases/physedit/shards/'+Path(r['path']).name,
                            sha256=r['sha256'],bytes=r['bytes']))
    required={r['source']['path']for r in load(ROOT/'PLAN.json')['rows']if r['source'].get('member')}
    assert required<={r['source_path']for r in targets}
    assert len({r['path']for r in targets})==len(targets)
    api=HfApi(token=get_token())
    assert read_retry(lambda:api.repo_info(REPO,repo_type='dataset',revision=BRANCH)).sha==state['head']
    operations=[CommitOperationCopy(src_path_in_repo=r['source_path'],src_revision=BASE,path_in_repo=r['path'])for r in targets]
    c=api.create_commit(REPO,repo_type='dataset',revision=BRANCH,parent_commit=state['head'],
        operations=operations,commit_message='Keep original state sources in the existing metadata area')
    state['head']=c.oid;dump(ROOT/'STATE.json',state)
    verify_new(api,targets,c.oid)
    dump(ROOT/'AUXILIARY.json',dict(revision=c.oid,files=targets,original_bytes_preserved=True))
    print(json.dumps(dict(phase='original_state_sources_preserved',files=len(targets))),flush=True)


def upload_metadata():
    state=load(ROOT/'STATE.json');ready=load(ROOT/'METADATA_READY.json')
    assert ready['videos']==72000 and ready['media_revision']==state['head']
    api=HfApi(token=get_token());base=ROOT/'metadata';changed=[];operations=[]
    for p in sorted(base.rglob('*')):
        if not p.is_file():continue
        path=p.relative_to(base).as_posix()
        if path.startswith('data/'):
            continue  # video folders contain only their 3,600 MP4s
        operations.append(CommitOperationAdd(path_in_repo=path,path_or_fileobj=str(p)))
        changed.append(dict(path=path,sha256=file_sha(p),bytes=p.stat().st_size))
    # The prepared package is small; payload/state archives are server copies, never re-uploaded here.
    assert all(not r['path'].startswith('releases/physedit/shards/')for r in changed)
    c=api.create_commit(REPO,repo_type='dataset',revision=BRANCH,parent_commit=state['head'],
        operations=operations,num_threads=16,commit_message='Point the existing metadata and download tools to the twenty scene folders')
    state['head']=c.oid;state['phase']='metadata_uploaded';dump(ROOT/'STATE.json',state)
    # Verify both ordinary Git blobs and larger metadata objects by exact bytes.
    for start in range(0,len(changed),300):
        part=changed[start:start+300];infos={x.path:x for x in read_retry(lambda:api.get_paths_info(REPO,[r['path']for r in part],repo_type='dataset',revision=c.oid))}
        for row in part:
            x=infos[row['path']];raw=(base/row['path']).read_bytes();assert x.size==len(raw)
            assert x.lfs.sha256==row['sha256'] if x.lfs else x.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    dump(ROOT/'METADATA_UPLOADED.json',dict(revision=c.oid,files=changed,all_hashes_verified=True))
    print(json.dumps(dict(phase='metadata_verified',files=len(changed))),flush=True)


def cleanup_old():
    state=load(ROOT/'STATE.json');assert (ROOT/'METADATA_UPLOADED.json').exists()
    api=HfApi(token=get_token());plan=load(ROOT/'PLAN.json')
    all_new={r['path']for r in plan['rows']}
    keep=all_new
    inventory=load(Path('/data_cached/wangzijun_p25/t19_final_release_20261030/size_audit_20261031/FILES.json'))
    remove=[r for r in inventory if r['path'].startswith('data/')and r['path']not in keep]
    from huggingface_hub import CommitOperationDelete
    scenes={f'T{i:02}'for i in range(1,21)};folders=set();individual=[]
    for row in remove:
        parts=row['path'].split('/')
        if len(parts)<3:individual.append(row['path'])
        elif parts[1]not in scenes:folders.add('/'.join(parts[:2])+'/')
        elif len(parts)>3:folders.add('/'.join(parts[:3])+'/')
        else:individual.append(row['path'])
    # Only old engine/sample folders are removed; every new MP4 is at scene root.
    assert all(not any(p.startswith(folder)for p in all_new)for folder in folders)
    assert not set(individual)&all_new
    assert all(any(row['path'].startswith(folder)for folder in folders)or row['path']in individual for row in remove)
    dump(ROOT/'REMOVE_PLAN.json',dict(files=remove,folders=sorted(folders),individual=individual,
        new_video_paths=72000,source_archive_copies=len(load(ROOT/'AUXILIARY.json')['files'])))
    operations=[CommitOperationDelete(path_in_repo=folder,is_folder=True)for folder in sorted(folders)]
    operations += [CommitOperationDelete(path_in_repo=p)for p in individual]
    c=api.create_commit(REPO,repo_type='dataset',revision=BRANCH,parent_commit=state['head'],
        operations=operations,commit_message='Remove old nested storage folders after every scene video and source has been preserved')
    state['head']=c.oid;state['removed_old_paths']=[r['path']for r in remove]
    state['phase']='old_layout_removed';dump(ROOT/'STATE.json',state)
    print(json.dumps(dict(phase='old_layout_removed',old_files_removed=len(remove),folders=len(folders))),flush=True)


def verify_layout():
    state,plan=load(ROOT/'STATE.json'),load(ROOT/'PLAN.json');api=HfApi(token=get_token())
    expected={r['path']:r for r in plan['rows']};found=set();counts=collections.Counter()
    from concurrent.futures import ThreadPoolExecutor
    def check_scene(scene):
        own=HfApi(token=get_token());paths=set()
        for item in own.list_repo_tree(REPO,path_in_repo='data/'+scene,repo_type='dataset',revision=state['head'],recursive=True):
            if not hasattr(item,'size'):raise AssertionError('Unexpected subfolder: '+item.path)
            if item.path.endswith('.mp4'):
                assert item.path in expected,item.path
                row=expected[item.path];assert item.lfs and item.lfs.sha256==row['sha256']
                assert Path(item.path).parent.as_posix()=='data/'+scene
                paths.add(item.path)
            else:raise AssertionError('Non-video file in scene folder: '+item.path)
        assert len(paths)==3600,(scene,len(paths))
        return scene,paths
    with ThreadPoolExecutor(max_workers=4)as pool:
        for scene,paths in pool.map(check_scene,[f'T{i:02}'for i in range(1,21)]):
            found.update(paths);counts[scene]=len(paths)
    roots=list(api.list_repo_tree(REPO,path_in_repo='data',repo_type='dataset',revision=state['head']))
    assert {x.path for x in roots}=={f'data/T{i:02}'for i in range(1,21)}
    assert found==set(expected)and counts=={f'T{i:02}':3600 for i in range(1,21)}
    state['phase']='complete_layout_verified';dump(ROOT/'STATE.json',state)
    dump(ROOT/'LAYOUT_VERIFIED.json',dict(revision=state['head'],videos=72000,scene_counts=dict(counts),
        all_remote_video_hashes_verified=True,video_archives_in_scene_folders=0,old_nested_video_paths=0))
    print(json.dumps(dict(phase=state['phase'],videos=72000,scenes=dict(counts))),flush=True)


def publish():
    import subprocess
    state=load(ROOT/'STATE.json');assert state['phase']=='complete_layout_verified'
    api=HfApi(token=get_token())
    assert read_retry(lambda:api.repo_info(REPO,repo_type='dataset')).sha==BASE,'Main advanced: do not overwrite another update'
    commits=api.list_repo_commits(REPO,repo_type='dataset',revision=BRANCH)
    ids=[c.commit_id for c in commits];assert BASE in ids and ids[0]==state['head']
    depth=ids.index(BASE)+3
    env=os.environ.copy();env.update(GIT_ASKPASS=str(ROOT/'git_askpass.py'),GIT_TERMINAL_PROMPT='0',
        GIT_LFS_SKIP_SMUDGE='1',https_proxy='http://127.0.0.1:17891')
    gitdir=ROOT/'publication.git'
    if not gitdir.exists():
        subprocess.run(['git','init','--bare',str(gitdir)],check=True,capture_output=True)
        subprocess.run(['git','--git-dir',str(gitdir),'remote','add','origin','https://huggingface.co/datasets/'+REPO],check=True)
    def git(*args):
        p=subprocess.run(['git','--git-dir',str(gitdir),*args],env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError(p.stderr[-1500:])
        return p.stdout
    git('fetch','--depth='+str(depth),'origin',BRANCH,'main')
    # A normal fast-forward push retains history and rejects concurrent changes.
    subprocess.run(['git','--git-dir',str(gitdir),'merge-base','--is-ancestor',BASE,state['head']],check=True)
    assert api.repo_info(REPO,repo_type='dataset').sha==BASE
    git('push','origin',state['head']+':refs/heads/main')
    assert api.repo_info(REPO,repo_type='dataset').sha==state['head']
    api.delete_branch(REPO,branch=BRANCH,repo_type='dataset')
    receipt=dict(revision=state['head'],base=BASE,videos=72000,scenes=20,videos_per_scene=3600,
        all_individual_mp4=True,existing_names_and_sha256_preserved=True,
        prompt_parameters_and_split_membership_preserved=True,temporary_branch_removed=True)
    dump(ROOT/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare','pilot','copy_direct','preupload_local','commit_local','commit_preuploaded',
        'stage_sources','upload_metadata','cleanup_old','verify_layout','publish'])
    args = parser.parse_args()
    globals()[args.action]()
