"""Remove superseded Genesis T19 from current HF main; verify the final package.

Run on p25 with --prepare, then --publish. This only targets the itemized
Genesis replacement, not Isaac/Core100 or unrelated local work.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

os.environ.update(HTTPS_PROXY='http://127.0.0.1:17891', HTTP_PROXY='http://127.0.0.1:17891', HF_HUB_DISABLE_XET='1')
from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete, get_token

ROOT = Path('/data_cached/wangzijun_p25/t19_final_release_20261030')
SOURCE = Path('/data_cached/wangzijun_p25/t19_gen_new_adoption_20261030')
PACKAGE = ROOT/'stage/releases/physedit'
REPO = 'phy2/phydataset'
TAG = 'physedit-20261030-final-t19'
HISTORY = 'provenance/t19_gen_new_20261030'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def fingerprint_matches(entry, path):
    raw = Path(path).read_bytes()
    return len(raw) == entry['size'] and (
        hashlib.sha256(raw).hexdigest() == entry['sha256'] if entry['sha256']
        else hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == entry['blob'])


def remote_entries(api, prefix, revision):
    return {x.path: dict(path=x.path, size=x.size, blob=x.blob_id,
                        sha256=x.lfs.sha256 if x.lfs else None)
            for x in api.list_repo_tree(REPO, path_in_repo=prefix, repo_type='dataset',
                                        revision=revision, recursive=True) if hasattr(x, 'size')}


def prepare():
    api = HfApi(token=get_token())
    inventory = read(ROOT/'inventory.json')
    before = inventory['revision']
    assert api.repo_info(REPO, repo_type='dataset').sha == before, 'Refresh inventory: main advanced'
    assert not PACKAGE.exists(), 'Do not overwrite a prepared release'
    baseline = inventory['files']
    original = SOURCE/'stage/releases/physedit'
    # Bind preparation to the exact current remote package, not an older staging copy.
    for path, entry in baseline.items():
        if path.startswith('releases/physedit/') and not path.startswith('releases/physedit/shards/'):
            local = original/path.removeprefix('releases/physedit/')
            assert local.is_file() and fingerprint_matches(entry, local), path
    shutil.copytree(original, PACKAGE, ignore=shutil.ignore_patterns('__pycache__'))
    delete = {p: e for p, e in baseline.items()
              if p.startswith('data/T19/genesis/') and p != 'data/T19/genesis/README.md'}
    assert sum(p.endswith('.mp4') for p in delete) == 1830
    assert sum(p.endswith('.tar.gz') for p in delete) == 2
    old_names = ['PREVIOUS_RELEASE.json', 'previous_genesis_T19.jsonl.gz',
                 'previous_prompt_texts.jsonl.gz', 'previous_video_prompt_bindings.jsonl.gz']
    for name in old_names:
        path = 'releases/physedit/'+HISTORY+'/'+name
        assert path in baseline
        delete[path] = baseline[path]
        (PACKAGE/HISTORY/name).unlink()

    # Consolidate new-source evidence under the one authoritative package.
    for path, entry in baseline.items():
        prefix = 'releases/t19_gen_new_source_bindings_20261030/'
        if not path.startswith(prefix):
            continue
        name = path.removeprefix(prefix)
        if name != 'README.md':
            local = SOURCE/name
            assert fingerprint_matches(entry, local), path
            target = PACKAGE/HISTORY/name
            if target.exists():
                assert sha(target) == sha(local), path
            else:
                shutil.copy2(local, target)
        delete[path] = entry

    # Verify all current downloads avoid each exact object being removed.
    count = new_count = prompts = 0
    split_counts = collections.Counter()
    archive_counts = collections.Counter()
    direct = set()
    for row in rows(PACKAGE/'catalog/videos.jsonl.gz'):
        count += 1
        prompts += len(row['prompt_variants_en'])
        split_counts[row['split']] += 1
        for field in ['download', 'source_download']:
            binding = row.get(field) or {}
            if binding.get('repo_id') == REPO:
                assert binding.get('path') not in delete, (row['video_id'], field)
        binding = row['download']
        if binding.get('member'):
            archive_counts[binding['path']] += 1
        else:
            direct.add(binding['path'])
        if row['engine'] == 'genesis' and row['quota_scene'] == 'T19':
            new_count += 1
            assert binding['path'].startswith('data/T19/t19_gen_new/')
            assert not row['training_ready'] and row['author_accepted']
            for text, expected in zip(row['prompt_variants_en'], row['prompt_variant_sha256']):
                assert hashlib.sha256(text.encode()).hexdigest() == expected
    assert (count, new_count, prompts) == (72000, 2640, 216000)
    new_media = remote_entries(api, 'data/T19/t19_gen_new', before)
    verified_media = read(SOURCE/'VERIFIED_MEDIA.json')
    assert len(verified_media) == 2640
    for row in verified_media:
        entry = new_media[row['path']]
        assert entry['size'] == row['bytes'] and entry['sha256'] == row['sha256'], row['path']
    dump(ROOT/'NEW_MEDIA_FINGERPRINTS.json', new_media)

    for rel in ['README.md', 'docs/CONTENT_IDENTITY.md']:
        path = PACKAGE/rel
        text = path.read_text(encoding='utf8').replace(
            'Old T19 media and metadata remain available at the pinned prior release.',
            'The superseded Genesis T19 media and backup metadata are removed from the current release.')
        path.write_text(text, encoding='utf8')
    evidence_readme = ('# Final Genesis T19\n\n'
        '2,640 current videos, 880 background-specific cases, 220 unique physical trajectories, '
        'and 7,920 short English prompt bindings. Camera mapping: front=cam01, side=cam02, overhead=cam03. '
        'Actual gravity is 9.81 m/s². All cases remain OOD.\n\n'
        'Use the current catalog and tools/download_standardized.py. Native media are under '
        'data/T19/t19_gen_new; canonical filenames are materialized by the downloader. '
        'The superseded Genesis T19 files, archives and backup prompt/catalog tables are removed '
        'from current main and the offline metadata package. No old quality labels, event truths '
        'or boundaries are assigned to the new videos. Current source configs and bindings remain '
        'available here. Core100 and all Isaac records are unchanged.\n')
    (PACKAGE/HISTORY/'README.md').write_text(evidence_readme, encoding='utf8')
    validation = read(PACKAGE/HISTORY/'VALIDATION.json')
    validation.pop('old_version_preserved', None)
    validation.update(superseded_genesis_t19_present_in_current_main=False,
                      superseded_genesis_t19_in_offline_package=False,
                      current_2640_media_lfs_hashes_verified=True)
    dump(PACKAGE/HISTORY/'VALIDATION.json', validation)
    storage = read(PACKAGE/'checks/STORAGE_INTEGRITY.json')
    storage['archives'] = [r for r in storage['archives'] if r['source_path'] in archive_counts]
    missing_archives = set(archive_counts) - {r['source_path'] for r in storage['archives']}
    if missing_archives:
        current = api.get_paths_info(REPO, sorted(missing_archives), repo_type='dataset', revision=before)
        assert {x.path for x in current} == missing_archives
        for entry in current:
            assert entry.lfs and entry.lfs.sha256
            storage['archives'].append(dict(source_path=entry.path, archive_sha256=entry.lfs.sha256,
                selected_video_records=archive_counts[entry.path], current_object_lfs_hash_recorded=True,
                fresh_archive_member_decode_this_cleanup=False,
                member_validation_scope='Existing current-release validation; this cleanup refreshes storage paths only.'))
    assert {r['source_path'] for r in storage['archives']} == set(archive_counts)
    for record in storage['archives']:
        assert record.get('selected_videos_verified', record.get('selected_video_records')) == archive_counts[record['source_path']]
    storage.update(archives_total=len(archive_counts), archive_objects=len(archive_counts),
        selected_archive_video_records=sum(archive_counts.values()),
        direct_video_objects_current=len(direct), current_catalog_records=count,
        current_t19_genesis_version='t19-gen-new-v1-20261030',
        current_t19_new_media_lfs_sha256_verified=2640,
        superseded_genesis_t19_storage_records_removed=True)
    # The old direct-object count was an earlier audit, not a count of the current inventory.
    if 'direct_video_objects_lfs_sha256_verified' in storage:
        storage['earlier_audit_direct_video_objects_lfs_sha256_verified'] = storage.pop('direct_video_objects_lfs_sha256_verified')
    storage.pop('selected_archive_member_video_bytes_sha256_verified', None)
    dump(PACKAGE/'checks/STORAGE_INTEGRITY.json', storage)
    audit = read(PACKAGE/'checks/RELEASE_AUDIT.json')
    audit.update(current_catalog_records=count, current_prompt_bindings=prompts,
                 current_genesis_t19_version='t19-gen-new-v1-20261030',
                 current_genesis_t19_media_sha256_verified=2640,
                 current_genesis_t19_backup_files_present=False,
                 current_parameter_coverage_note='Genesis T19: four backgrounds, three cameras, gravity 9.81 m/s²; other scene contracts unchanged.')
    audit['regular_4_background_5_gravity_3_camera_sampling'] = False
    dump(PACKAGE/'checks/RELEASE_AUDIT.json', audit)
    cleanup = dict(status='PASS', scope='Superseded Genesis T19 only',
                   removed_old_direct_mp4=1830, removed_old_archives=2,
                   removed_old_backup_tables=4, current_genesis_t19_videos=2640,
                   current_genesis_t19_prompt_bindings=7920,
                   current_video_records=count, current_prompt_bindings=prompts,
                   current_download_references_to_removed_objects=0,
                   all_2640_new_media_remote_hashes_verified=True,
                   core100_and_isaac_and_training_files_unchanged=True,
                   old_labels_or_boundary_truth_transferred=False)
    dump(PACKAGE/'checks/T19_FINAL_RELEASE.json', cleanup)

    # Root documents: current publication only, with no parallel old-version entry.
    roots = ROOT/'stage'
    text = (ROOT/'base/README.md').read_text(encoding='utf8')
    text = text.replace('Use the current catalog/downloader; old canonical folders remain historical media. '
        'Old video bytes, metadata and prompt bindings are retained in the pinned prior release and '
        '[replacement provenance](releases/physedit/provenance/t19_gen_new_20261030/README.md).',
        'Use the current catalog/downloader. The superseded Genesis T19 media, archives and backup tables '
        'have been removed from the current release and offline metadata package. '
        '[Current source inputs and validation](releases/physedit/provenance/t19_gen_new_20261030/README.md).')
    (roots/'README.md').write_text(text, encoding='utf8')
    (roots/'DIRECTORY.md').write_text('# PhysEdit final repository\n\n'
        '- `data/`: current video files and payload archives. Genesis T19 uses `data/T19/t19_gen_new/`.\n'
        '- `releases/physedit/`: authoritative current metadata, prompts, evaluation and download package.\n'
        '- `catalog/active_core100_conditions.json`: independent active Core100 reference registration.\n'
        '- `assets/`: presentation media.\n\n'
        'The superseded Genesis T19 media and backup tables are not included in the current release.\n', encoding='utf8')
    redirect = roots/'data/T19/genesis/README.md'
    redirect.parent.mkdir(parents=True, exist_ok=True)
    redirect.write_text('# Genesis T19\n\nThe final 2,640 videos are stored in '
        '[t19_gen_new](../t19_gen_new). Use the [current catalog]'
        '(../../../releases/physedit/catalog/by_scene/genesis__T19.jsonl.gz) '
        'and the standard downloader for canonical filenames. This directory contains no superseded media.\n', encoding='utf8')
    # Keep full source inputs; remove only obsolete package checksums and regenerate them.
    files = [dict(path=p.relative_to(PACKAGE).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(PACKAGE.rglob('*')) if p.is_file()
        and p.relative_to(PACKAGE).parts[0] != 'downloads'
        and p != PACKAGE/'checks/FILES_SHA256.json']
    dump(PACKAGE/'checks/FILES_SHA256.json', dict(algorithm='SHA-256',
        scope='Complete current metadata package excluding this file and downloads.', files=files))
    archive = PACKAGE/'downloads/physedit_metadata.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(PACKAGE.rglob('*')):
            if p.is_file() and p.relative_to(PACKAGE).parts[0] != 'downloads':
                z.write(p, 'physedit/'+p.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(Path(n).name in old_names for n in z.namelist())
        for record in files:
            assert hashlib.sha256(z.read('physedit/'+record['path'])).hexdigest() == record['sha256']
    status = read(ROOT/'base/release_status.json')
    status.update(offline_metadata_sha256=sha(archive), current_package_tag=TAG,
        t19_genesis_old_version_preserved=False, t19_genesis_superseded_files_in_current_release=False,
        t19_genesis_release_cleanup='PASS', t19_genesis_old_media_in_offline_package=False)
    dump(roots/'release_status.json', status)
    protected = [p for p in baseline if p.startswith('releases/physedit/core100/')
        or p.endswith(('train_final.jsonl.gz', 'train_unique_declared_triplets.jsonl.gz',
                       'videos_train.parquet', 'videos_train_unique_declared_triplets.parquet', 'isaac__T19.jsonl.gz'))]
    for path in protected:
        assert fingerprint_matches(baseline[path], roots/path), path
    upload = []
    for p in roots.rglob('*'):
        if p.is_file():
            rel = p.relative_to(roots).as_posix()
            entry = baseline.get(rel)
            if entry is None or not fingerprint_matches(entry, p):
                upload.append(dict(path=rel, local=str(p), sha256=sha(p), size=p.stat().st_size))
    # No references to an exact deleted object remain in current metadata.
    deleted = set(delete)
    for record in files:
        assert 'releases/physedit/'+record['path'] not in deleted
    dump(ROOT/'PLAN.json', dict(repo=REPO, before=before, delete=list(delete.values()),
        upload=upload, protected=protected, new_media_fingerprints=str(ROOT/'NEW_MEDIA_FINGERPRINTS.json'),
        counts=cleanup, package_sha256=sha(archive), split_counts=dict(split_counts), tag=TAG))
    print(json.dumps(dict(phase='prepared', delete_files=len(delete), upload_files=len(upload),
                         counts=cleanup, package_sha256=sha(archive))), flush=True)


def publish():
    plan = read(ROOT/'PLAN.json')
    api = HfApi(token=get_token())
    assert api.repo_info(REPO, repo_type='dataset').sha == plan['before'], 'Concurrent change: refresh and merge first'
    assert all(sha(r['local']) == r['sha256'] for r in plan['upload'])
    # Exact-parent atomic commit: add the validated package and remove only itemized old objects.
    operations = [CommitOperationDelete(path_in_repo=r['path']) for r in plan['delete']]
    operations += [CommitOperationAdd(path_in_repo=r['path'], path_or_fileobj=r['local']) for r in plan['upload']]
    commit = api.create_commit(REPO, repo_type='dataset', parent_commit=plan['before'],
        operations=operations, commit_message='Finalize Genesis T19: remove superseded media and backup tables; publish current-only metadata')
    receipt = dict(phase='committed_verification_pending', revision=commit.oid,
        before=plan['before'], deleted_files=len(plan['delete']), uploaded_files=len(plan['upload']))
    dump(ROOT/'PUBLISHED.json', receipt)
    verify()


def verify():
    api = HfApi(token=get_token())
    plan = read(ROOT/'PLAN.json')
    receipt = read(ROOT/'PUBLISHED.json')
    revision = receipt['revision']
    assert api.repo_info(REPO, repo_type='dataset').sha == revision
    existing = remote_entries(api, 'data/T19/genesis', revision)
    assert set(existing) == {'data/T19/genesis/README.md'}
    package_entries = remote_entries(api, 'releases/physedit', revision)
    assert not set(r['path'] for r in plan['delete']) & set(package_entries)
    removed_tables = [r['path'] for r in plan['delete'] if not r['path'].startswith('data/T19/genesis/')]
    assert not api.get_paths_info(REPO, removed_tables, repo_type='dataset', revision=revision)
    paths = [r['path'] for r in plan['upload']] + plan['protected']
    for start in range(0, len(paths), 100):
        entries = {x.path: x for x in api.get_paths_info(REPO, paths[start:start+100], repo_type='dataset', revision=revision)}
        for path in paths[start:start+100]:
            x = entries[path]
            entry = dict(size=x.size, sha256=x.lfs.sha256 if x.lfs else None, blob=x.blob_id)
            assert fingerprint_matches(entry, ROOT/'stage'/path), path
    current_new = remote_entries(api, 'data/T19/t19_gen_new', revision)
    assert current_new == read(plan['new_media_fingerprints'])
    refs = api.list_repo_refs(REPO, repo_type='dataset')
    # Remove the two explicit superseded Genesis replacement tags, not unrelated releases.
    removed_tags = []
    for tag in refs.tags:
        if tag.name in ('physedit-pre-t19-gen-new-20261030', 'physedit-20261030-t19-gen-new-v1'):
            api.delete_tag(REPO, tag=tag.name, repo_type='dataset')
            removed_tags.append(tag.name)
    api.create_tag(REPO, tag=TAG, revision=revision, repo_type='dataset', exist_ok=True)
    receipt.update(phase='remote_hashes_and_deletions_verified', counts=plan['counts'],
        package_sha256=plan['package_sha256'], tag=TAG, removed_superseded_tags=removed_tags,
        current_genesis_t19_files_unchanged=True, protected_metadata_hashes_unchanged=True,
        published_visibility_unchanged=True)
    dump(ROOT/'PUBLISHED.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'publish', 'verify'])
    args = parser.parse_args()
    globals()[args.action]()
