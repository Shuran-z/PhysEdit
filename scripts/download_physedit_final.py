"""Download and verify the fixed PhysEdit metadata release (not video payloads)."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from huggingface_hub import HfApi, hf_hub_download

REPO = 'phy2/phydataset'
REVISION = 'v1.0.2'


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('physedit_release'))
    parser.add_argument('--revision', default=REVISION)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Choose a new output directory: '+str(output))
    revision = HfApi().repo_info(REPO, repo_type='dataset', revision=args.revision).sha
    status_path = hf_hub_download(REPO, filename='release_status.json', repo_type='dataset', revision=revision)
    status = json.loads(Path(status_path).read_text(encoding='utf8'))
    archive = hf_hub_download(REPO, filename=status['offline_metadata'], repo_type='dataset', revision=revision)
    if file_sha(archive) != status['offline_metadata_sha256']:
        raise ValueError('Offline metadata SHA256 mismatch')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.physedit_download_', dir=output.parent) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:
                raise ValueError('Invalid metadata ZIP')
            for member in z.infolist():
                rel = PurePosixPath(member.filename)
                if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] != 'physedit':
                    raise ValueError('Unsafe archive member: '+member.filename)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Symlink in metadata archive')
                target = staging.joinpath(*rel.parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
        package = staging/'physedit'
        checks = json.loads((package/'checks/FILES_SHA256.json').read_text(encoding='utf8'))
        for item in checks['files']:
            rel = PurePosixPath(item['path'])
            path = package.joinpath(*rel.parts).resolve()
            if rel.is_absolute() or '..' in rel.parts or not path.is_relative_to(package.resolve()):
                raise ValueError('Unsafe manifest path')
            if path.stat().st_size != item['bytes'] or file_sha(path) != item['sha256']:
                raise ValueError('Metadata file mismatch: '+item['path'])
        receipt = dict(repo=REPO, requested_revision=args.revision, resolved_revision=revision,
                       metadata_sha256=status['offline_metadata_sha256'], files_verified=len(checks['files']))
        (staging/'DOWNLOAD_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf8')
        # Move only the verified files into a previously nonexistent destination.
        staging.rename(output)
    print(json.dumps(dict(output=str(output), **receipt), ensure_ascii=False))


if __name__ == '__main__':
    main()
