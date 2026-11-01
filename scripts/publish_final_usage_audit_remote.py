"""Publish audited usage fixes with an exact parent and no media operations."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

os.environ['HTTPS_PROXY'] = os.environ['HTTP_PROXY'] = 'http://127.0.0.1:17891'
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import HfApi, get_token, CommitOperationAdd, CommitOperationDelete

R = Path('/data_cached/wangzijun_p25/t19_final_release_20261030/usage_audit')
D = R.parent/'stage/releases/physedit'
S = R.parent/'stage'
REPO = 'phy2/phydataset'
BASE = 'c334d629b045619fe54688c7871751e71a3fd6e3'
TAG = 'v1.0.2'


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def main():
    api = HfApi(token=get_token())
    assert api.repo_info(REPO, repo_type='dataset').sha == BASE
    assert TAG not in {x.name for x in api.list_repo_refs(REPO, repo_type='dataset').tags}, 'Never move an existing release tag'
    checks = {p:load(R/p) for p in ['AUDIT.json', 'DOWNLOAD_OBJECTS_VERIFIED.json', 'TOOLS_SMOKE.json', 'CANONICAL_T19_VERIFIED.json']}
    assert all(x['status'] == 'PASS' for x in checks.values())
    current = load(R/'core100_current_inputs/RECEIPT.json')
    assert current['unchanged_actual_inputs'] == 95 and current['active_isaac_t19_inputs'] == 5
    assert current['all_exported_hashes_verified']
    report = dict(status='PASS', catalog_prompts_config_split=checks['AUDIT.json'],
        download_objects=checks['DOWNLOAD_OBJECTS_VERIFIED.json'], tool_smoke=checks['TOOLS_SMOKE.json'],
        canonical_hosted_t19=checks['CANONICAL_T19_VERIFIED.json'],
        current_core100_inputs=current, csv_hash_fields_refreshed=1983,
        csv_hash_refresh_by_scene={'T13':1980, 'T19':3}, train_test_membership_modified=False,
        baseline_release_commit=BASE)
    dump(D/'checks/FINAL_USAGE_AUDIT.json', report)
    # The concurrent format release moved the same inputs into canonical paths.
    # Keep that layout, while honoring the author's request for no archive copy.
    for path in [D/'README.md', D/'docs/CONTENT_IDENTITY.md']:
        text = path.read_text().replace('Historical folders are retained under `archive/T19`; use the current dataset directory for normal access.',
            'Duplicate upload/archive folders are excluded from this release. Original configs, trajectories and rendering metadata remain in the canonical source_metadata.zip; use the current dataset directory for normal access.')
        path.write_text(text)
    path = D/'provenance/T19/FORMAT_VALIDATION.json'
    data = load(path)
    data.pop('old_files_archived', None)
    data.pop('old_files_blob_ids_preserved', None)
    data.update(duplicate_upload_archive_in_current_main=False,
                original_inputs_preserved_in_canonical_source_metadata_zip=True)
    dump(path, data)
    path = D/'core100/README.md'
    text = path.read_text().replace('# Fixed Core100 evaluation inputs', '# Historical actual Core100 generation inputs', 1)
    if 'For a new evaluation, use `python tools/prepare_core100_current.py' not in text:
        text = text.replace('100 tasks: 80 ID, 10 OOD-1 (T03/T20), 10 OOD-2 (T11/T19).',
        'This directory and the HF `core100` config reproduce the historical actual generation inputs. '
        'For a new evaluation, use `python tools/prepare_core100_current.py --output NEW_DIRECTORY` from the package root. '
        'It preserves the 95 actual submitted inputs and replaces only the five T19 slots with active Isaac reference inputs, '
        'verified against `catalog/active_core100_conditions.json`. No historical annotations or scores are transferred.\n\n'
            '100 tasks: 80 ID, 10 OOD-1 (T03/T20), 10 OOD-2 (T11/T19).', 1)
    path.write_text(text)
    path = D/'docs/DOWNLOAD.md'
    text = path.read_text()+'\n\n## Current input export\n\n'
    text += ('`python tools/prepare_core100_current.py --output ../core100_current_inputs` exports 95 exact historical inputs '
        'plus the five active Isaac T19 replacements. `core100/download_inputs.py` above is the historical-reproduction path. '
        'Do not use its old five T19 inputs for a new current-reference evaluation.\n\n'
        'The video downloader defaults to `--split train_final`. To download new Genesis T19, use '
        '`--scene T19 --engine genesis --split all`; the expected selection is 2,640 records. '
        'The complete Chinese commands and source-config map are in [QUICKSTART_ZH.md](QUICKSTART_ZH.md).\n')
    path.write_text(text)
    path = D/'README.md'
    text = path.read_text().replace('## 下载', '## 下载\n\n完整命令、原始配置位置和当前Core100输入导出见[给同事的下载与使用说明](docs/QUICKSTART_ZH.md)。', 1)
    path.write_text(text)
    path = S/'README.md'
    text = path.read_text().replace('## Start here', '## Start here\n\n- [下载与使用说明（中文）](releases/physedit/docs/QUICKSTART_ZH.md)', 1)
    text = text.replace('Historical upload directories are outside the current data tree.', 'Duplicate upload/archive directories are excluded from this release.')
    text += ('\nFor new Core100 evaluations, run `tools/prepare_core100_current.py` from the metadata package: '
        '95 actual frozen inputs plus five active Isaac T19 inputs. The HF `core100` config and '
        '`core100/download_inputs.py` preserve historical actual generation inputs for reproduction; '
        'they do not transfer old T19 labels or scores.\n')
    path.write_text(text)
    path = S/'DIRECTORY.md'
    text = path.read_text().replace('Genesis T19 uses `data/T19/t19_gen_new/`.', 'Genesis T19 uses `data/T19/genesis/`.')
    text = text.replace(' Versioned provenance: [archive/T19](archive/T19).', '')
    path.write_text(text)
    path = D/'checks/TRAINING_SPLIT.json'
    data = load(path)
    data.update(current_split_csv_sha256=sha(D/'catalog/split_assignments.csv'),
        current_split_csv_matches_all72000_rows=True, csv_hash_fields_refreshed=1983, train_test_membership_modified=False)
    dump(path, data)
    path = D/'checks/ALIGNMENT_REPORT.json'
    data = load(path)
    data.update(final_usage_audit='checks/FINAL_USAGE_AUDIT.json', current_split_csv_all72000_sha256_matches=True)
    dump(path, data)
    files = [dict(path=p.relative_to(D).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(D.rglob('*')) if p.is_file() and p.relative_to(D).parts[0] != 'downloads'
        and p != D/'checks/FILES_SHA256.json']
    dump(D/'checks/FILES_SHA256.json', dict(algorithm='SHA-256',
        scope='Complete current metadata package excluding this file and downloads.', files=files))
    archive = D/'downloads/physedit_metadata.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(D.rglob('*')):
            if p.is_file() and p.relative_to(D).parts[0] != 'downloads':
                z.write(p, 'physedit/'+p.relative_to(D).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for record in files:
            assert hashlib.sha256(z.read('physedit/'+record['path'])).hexdigest() == record['sha256']
    path = S/'release_status.json'
    data = load(path)
    data.update(current_package_tag=TAG, offline_metadata_sha256=sha(archive),
        final_download_prompt_config_split_audit='PASS',
        usage_instructions='releases/physedit/docs/QUICKSTART_ZH.md',
        current_core100_input_exporter='releases/physedit/tools/prepare_core100_current.py')
    data['t19_genesis_old_version_preserved'] = False
    data['t19_genesis_duplicate_archive_in_current_release'] = False
    data.pop('t19_genesis_history_scope', None)
    dump(path, data)
    remote = {x.path:x for x in api.list_repo_tree(REPO, path_in_repo='releases/physedit',
        repo_type='dataset', revision=BASE, recursive=True) if hasattr(x, 'size')}
    for x in api.get_paths_info(REPO, ['README.md', 'release_status.json', 'DIRECTORY.md'], repo_type='dataset', revision=BASE):
        remote[x.path] = x
    ops, changed = [], []
    for p in S.rglob('*'):
        if not p.is_file():
            continue
        path = p.relative_to(S).as_posix()
        if path not in ['README.md', 'release_status.json', 'DIRECTORY.md'] and not path.startswith('releases/physedit/'):
            continue
        raw = p.read_bytes()
        h = hashlib.sha256(raw).hexdigest()
        x = remote.get(path)
        if x and x.size == len(raw) and (x.lfs.sha256 == h if x.lfs else x.blob_id == blob(raw)):
            continue
        assert not path.startswith('releases/physedit/core100/') or path == 'releases/physedit/core100/README.md'
        assert not path.endswith(('videos_train.parquet', 'train_final.jsonl.gz', 'train_unique_declared_triplets.jsonl.gz'))
        ops.append(CommitOperationAdd(path_in_repo=path, path_or_fileobj=str(p)))
        changed.append(dict(path=path, sha256=h, bytes=len(raw)))
    assert not any('/parquet/' in x['path'] for x in changed)
    roots = {x.path for x in api.list_repo_tree(REPO, repo_type='dataset', revision=BASE)}
    removed = []
    if 'archive' in roots:
        removed = load(R/'ARCHIVE_T19_INVENTORY.json')
        assert len(removed) == 5149 and all(x['path'].startswith('archive/T19/') for x in removed)
        actual = {x.path:x.blob_id for x in api.list_repo_tree(REPO, path_in_repo='archive/T19', repo_type='dataset', revision=BASE, recursive=True) if hasattr(x, 'size')}
        assert actual == {x['path']:x['blob'] for x in removed}
    # All retained media and source-config references were verified under data/T19/genesis.
    ops += [CommitOperationDelete(path_in_repo=x['path']) for x in removed]
    dump(R/'PUBLISH_PLAN.json', dict(base=BASE, tag=TAG, files=changed, removed_duplicate_archive=removed))
    assert api.repo_info(REPO, repo_type='dataset').sha == BASE
    commit = api.create_commit(REPO, repo_type='dataset', parent_commit=BASE, operations=ops,
        commit_message='Verify final download and input contracts; refresh split CSV hashes, exclude duplicate T19 archive and document current Core100 export')
    receipt = dict(revision=commit.oid, tag=TAG, base=BASE, changed_files=len(changed),
        offline_metadata_sha256=sha(archive), phase='committed_verification_pending')
    dump(R/'PUBLISHED.json', receipt)
    for start in range(0, len(changed), 100):
        entries = {x.path:x for x in api.get_paths_info(REPO, [r['path'] for r in changed[start:start+100]],
            repo_type='dataset', revision=commit.oid)}
        for row in changed[start:start+100]:
            x = entries[row['path']]
            raw = (S/row['path']).read_bytes()
            assert x.size == len(raw)
            assert x.lfs.sha256 == row['sha256'] if x.lfs else x.blob_id == blob(raw)
    api.create_tag(REPO, tag=TAG, revision=commit.oid, repo_type='dataset')
    assert not api.get_paths_info(REPO, ['archive/T19/MOVES.json', 'archive/T19/README.md'], repo_type='dataset', revision=commit.oid)
    assert 'archive' not in {x.path for x in api.list_repo_tree(REPO, repo_type='dataset', revision=commit.oid)}
    receipt.update(phase='remote_files_verified', audit_status='PASS',
        no_current_video_or_prompt_text_or_split_membership_modified=True,
        duplicate_archive_files_removed=len(removed))
    dump(R/'PUBLISHED.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
