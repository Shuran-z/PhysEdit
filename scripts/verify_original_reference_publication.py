"""Verify original-reference media against frozen current HF revisions.

Read-only remote API calls; credentials remain on p25. This proves media identity,
not latest-release selection, event truth, or formal scoring admission.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path('review/scene_family_completion_20261018')
REMOTE = r'''
import json
from huggingface_hub import HfApi,get_token
api=HfApi(token=get_token())
for repo, paths in REQUESTS.items():
 try:
  revision=api.dataset_info(repo,files_metadata=False).sha
  found=[]
  for i in range(0,len(paths),200):
   for item in api.get_paths_info(repo_id=repo,paths=paths[i:i+200],repo_type='dataset',revision=revision):
    lfs=getattr(item,'lfs',None)
    found.append(dict(path=item.path,blob_id=getattr(item,'blob_id',None),
      sha256=getattr(lfs,'sha256',None),size=getattr(item,'size',None)))
  print(json.dumps(dict(repo_id=repo,revision=revision,files=found)),flush=True)
 except Exception as e: print(json.dumps(dict(repo_id=repo,error=type(e).__name__)),flush=True)
'''


def media_matches(expected, actual):
    if not actual or expected.get('bytes') != actual.get('size'):
        return False
    # HF's git object id is also a content identity when an LFS digest is absent.
    return bool((expected.get('sha256') and expected['sha256'] == actual.get('sha256')) or
                (expected.get('git_oid') and expected['git_oid'] == actual.get('blob_id')))


def main():
    source = ROOT / 'original_value_distance_ledger/sample_distances.jsonl'
    raw = source.read_bytes()
    rows = [json.loads(x) for x in raw.decode('utf8').splitlines() if x.strip()]
    requests = {}
    for r in rows:
        if r.get('repo_id') and r['scene_id'] != 'T19':
            requests.setdefault(r['repo_id'], set()).update(v['path'] for v in r.get('videos', {}).values())
    requests = {k: sorted(v) for k, v in requests.items()}
    proc = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
        '-o', 'ExitOnForwardFailure=yes', '-R', '127.0.0.1:0:127.0.0.1:7897',
        'p25', '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        match = re.search(rb'Allocated port (\d+)', proc.stderr.readline())
        if not match:
            raise RuntimeError('proxy forwarding unavailable')
        prefix = "import os\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n" % int(match[1])
        out, _ = proc.communicate((prefix + REMOTE.replace('REQUESTS', repr(requests))).encode(), timeout=600)
        if proc.returncode:
            raise RuntimeError('remote publication verification failed')
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    receipts = [json.loads(line) for line in out.splitlines() if line.strip()]
    repos = {r['repo_id']: r for r in receipts}
    files = {(r['repo_id'], f['path']): f for r in receipts for f in r.get('files', [])}
    bindings = []
    seen = set()
    for row in rows:
        key = (row.get('repo_id'), row.get('revision'), row.get('engine'), row['sample_id'])
        if key in seen:
            continue
        seen.add(key)
        repo = repos.get(row.get('repo_id'), {})
        videos = row.get('videos', {})
        checks = {cam: media_matches(v, files.get((row.get('repo_id'), v['path']))) for cam, v in videos.items()}
        status = ('retired_T19' if row['scene_id'] == 'T19' else
                  'server_only_no_HF_binding' if not row.get('repo_id') else
                  'lookup_failed' if repo.get('error') or not repo else
                  'same_media_at_current_revision' if videos and all(checks.values()) else
                  'media_missing_or_changed')
        bindings.append(dict(scene_id=row['scene_id'], sample_id=row['sample_id'], engine=row.get('engine'),
            repo_id=row.get('repo_id'), original_revision=row.get('revision'),
            checked_revision=repo.get('revision'), status=status, camera_checks=checks,
            media_identity=[dict(camera=c, path=v['path'], sha256=v.get('sha256'), git_oid=v.get('git_oid')) for c,v in videos.items()],
            current_release_selection_confirmed=False, formal_admission=False))
    result = dict(source_sha256=hashlib.sha256(raw).hexdigest(), records=bindings,
                  repositories=[{k:v for k,v in r.items() if k != 'files'} for r in receipts])
    (ROOT/'original_reference_publication_verification_20261026.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    from collections import Counter
    print(json.dumps(dict(counts=Counter(r['status'] for r in bindings),repositories=result['repositories'])))


if __name__ == '__main__':
    main()
