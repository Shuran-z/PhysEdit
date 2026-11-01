"""Upload frozen supplement shards, verify remote hashes, then publish the catalog."""
import hashlib
import json
import os
from pathlib import Path
import time

os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
# HF API needs the SSH proxy; the LFS S3 data plane is directly reachable from p25.
os.environ['NO_PROXY'] = ','.join(filter(None, [os.environ.get('NO_PROXY', ''), '.amazonaws.com']))
os.environ['no_proxy'] = os.environ['NO_PROXY']
import logging
logging.getLogger('huggingface_hub').setLevel(logging.CRITICAL)
logging.getLogger('httpx').setLevel(logging.CRITICAL)
from huggingface_hub import HfApi, get_token
import huggingface_hub.lfs as lfs
import httpx

# Retry the small multipart completion request without retransmitting gigabytes.
_lfs_backoff = lfs.http_backoff
def completion_backoff(method, url, **kwargs):
    for retry in range(20):
        try:
            return _lfs_backoff(method, url, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
            if method != 'POST' or retry == 19:
                raise
            print(json.dumps(dict(multipart_completion_retry=retry + 1)), flush=True)
            time.sleep(15)
lfs.http_backoff = completion_backoff

root = Path('/data_cached/wangzijun_p25/author_release_20261029')
active_file = root / 'UPLOAD_ACTIVE.json'
if active_file.exists():
    previous_pid = json.loads(active_file.read_text())['pid']
    if previous_pid != os.getpid():
        try:
            os.kill(previous_pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Another release uploader is active: ' + str(previous_pid))
active_file.write_text(json.dumps(dict(pid=os.getpid(), started=time.time())))
repo = 'phy2/phydataset'
prefix = 'releases/72000_author_review_20261029'
api = HfApi(token=get_token())
receipts = []
for host, scene in [('p25', 'T14S'), ('p25', 'T18'), ('p25', 'T19'), ('p25', 'T20'), ('sg88', 'T18'), ('sg88', 'T19')]:
    folder = root if host == 'p25' else root / host
    archive = folder / (scene + '.tar.gz')
    receipt_file = archive.with_suffix('.receipt.json')
    deadline = time.time() + 3600
    while not receipt_file.exists():
        if time.time() > deadline:
            raise TimeoutError('Waiting for verified shard transfer: ' + str(archive))
        time.sleep(10)
    expected = json.loads(receipt_file.read_text())
    h = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    assert h.hexdigest() == expected['sha256'], archive
    dest = prefix + '/shards/' + host + '/' + archive.name
    print(json.dumps(dict(starting=dest, bytes=expected['bytes'])), flush=True)
    for attempt in range(12):
        try:
            existing = api.get_paths_info(repo, [dest], repo_type='dataset')
            if not existing or getattr(existing[0].lfs, 'sha256', None) != expected['sha256']:
                api.upload_file(path_or_fileobj=str(archive), path_in_repo=dest,
                                repo_id=repo, repo_type='dataset',
                                commit_message='Add author-approved supplement shard ' + host + '/' + scene)
            info = api.get_paths_info(repo, [dest], repo_type='dataset')[0]
            assert info.size == expected['bytes'] and info.lfs.sha256 == expected['sha256']
            break
        except Exception as exc:
            (root / 'upload_error.json').write_text(json.dumps(dict(host=host, scene=scene, attempt=attempt, error_type=type(exc).__name__)))
            if attempt == 11:
                raise
            time.sleep(min(60, 15 * (attempt + 1)))
    receipts.append(dict(host=host, scene=scene, path=dest, sha256=expected['sha256'],
                         bytes=expected['bytes'], videos=expected['videos']))
    (root / 'upload_progress.json').write_text(json.dumps(receipts, indent=2))
    print(json.dumps(dict(uploaded=dest, verified=True)), flush=True)

metadata = root / 'metadata'
assert (metadata / 'README.md').exists()
(metadata / 'shard_receipts.json').write_text(json.dumps(receipts, indent=2))
for attempt in range(12):
    try:
        commit = api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=str(metadata),
                                  path_in_repo=prefix, commit_message='Publish author-reviewed supplement and versioned 72000-slot inventory')
        break
    except (httpx.TransportError, RuntimeError) as exc:
        (root / 'upload_error.json').write_text(json.dumps(dict(stage='metadata', attempt=attempt, error_type=type(exc).__name__)))
        if attempt == 11:
            raise
        time.sleep(min(60, 15 * (attempt + 1)))
revision = commit.oid
paths = [prefix + '/' + p.name for p in metadata.iterdir() if p.is_file()]
assert len(api.get_paths_info(repo, paths, repo_type='dataset', revision=revision)) == len(paths)
result = dict(repo=repo, revision=revision, prefix=prefix, uploaded_video_files=sum(r['videos'] for r in receipts),
              author_accepted_new_videos=1953, inventory_entries=72000, all_72000_quality_approved=False,
              shard_hashes_verified=True, metadata_files=len(paths), completed=time.time())
(root / 'PUBLISHED.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result), flush=True)
