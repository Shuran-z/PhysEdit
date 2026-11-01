"""Publish only the colleague guide and its metadata-package checksums."""
import hashlib
import json
from pathlib import Path
import zipfile

from huggingface_hub import HfApi, CommitOperationAdd, hf_hub_download

ROOT = Path('/data_cached/wangzijun_p25/scene_videos_20261031')
STAGE = ROOT / 'guide_metadata_verified'
D = STAGE / 'releases/physedit'
REPO = 'phy2/phydataset'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    api = HfApi()
    parent = api.repo_info(REPO, repo_type='dataset').sha
    status = json.loads(Path(hf_hub_download(REPO, 'release_status.json', repo_type='dataset',
                                          revision=parent)).read_text())
    current_zip = Path(hf_hub_download(REPO, status['offline_metadata'], repo_type='dataset', revision=parent))
    assert sha(current_zip) == status['offline_metadata_sha256']
    assert not STAGE.exists(), 'Choose a fresh guide staging directory'
    D.mkdir(parents=True)
    with zipfile.ZipFile(current_zip) as z:
        assert z.testzip() is None
        for item in z.infolist():
            rel = Path(item.filename)
            assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[0] == 'physedit'
            if item.is_dir():
                continue
            target = STAGE / 'releases' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
    (D / 'downloads').mkdir(exist_ok=True)
    guide = (ROOT / 'DOWNLOAD_FOR_COLLEAGUES_ZH.md').read_text(encoding='utf8')
    targets = [D / 'docs/QUICKSTART_ZH.md', D / 'docs/DOWNLOAD.md']
    for target in targets:
        # Refuse to overwrite an independently updated remote guide.
        current = Path(hf_hub_download(REPO, target.relative_to(STAGE).as_posix(),
                                      repo_type='dataset', revision=parent))
        assert sha(current) == sha(target), str(target)
    for target in targets:
        target.write_text(guide, encoding='utf8')
    checks = D / 'checks/FILES_SHA256.json'
    records = json.loads(checks.read_text())
    for record in records['files']:
        if record['path'] in ['docs/QUICKSTART_ZH.md', 'docs/DOWNLOAD.md']:
            p = D / record['path']
            record.update(bytes=p.stat().st_size, sha256=sha(p))
        else:
            assert sha(D / record['path']) == record['sha256'], record['path']
    dump(checks, records)
    archive = D / 'downloads/physedit_metadata.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(D.rglob('*')):
            if p.is_file() and p.relative_to(D).parts[0] != 'downloads':
                z.write(p, 'physedit/' + p.relative_to(D).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for record in records['files']:
            assert hashlib.sha256(z.read('physedit/' + record['path'])).hexdigest() == record['sha256']
    status_path = STAGE / 'release_status.json'
    status['offline_metadata_sha256'] = sha(archive)
    dump(status_path, status)
    changed = targets + [checks, archive, status_path]
    result = api.create_commit(REPO, repo_type='dataset', parent_commit=parent,
        commit_message='Clarify scene-folder downloads and video metadata/split correspondence',
        operations=[CommitOperationAdd(path_in_repo=p.relative_to(STAGE).as_posix(), path_or_fileobj=str(p))
                    for p in changed])
    for p in changed:
        actual = Path(hf_hub_download(REPO, p.relative_to(STAGE).as_posix(), repo_type='dataset',
                                    revision=result.oid))
        assert sha(actual) == sha(p), str(p)
    receipt = dict(revision=result.oid, parent=parent, changed_files=[p.relative_to(STAGE).as_posix() for p in changed],
                   published_hashes_verified=True, metadata_package_members_verified=len(records['files']))
    dump(ROOT / 'DOWNLOAD_GUIDE_UPDATED.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
