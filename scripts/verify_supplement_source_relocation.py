"""Verify source JSON relocation without treating asset bytes or quality as proven."""
import collections
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'release_72000_active'
PREFIX = '/data/yangkaiyuan/t18_t19_resume_20261028/assets'
OUTPUTS = {'/annotations/save_path', '/render/save_video',
           '/render/save_first_rgb', '/render/save_last_rgb'}

def read(name):
    with gzip.open(ROOT / name, 'rt', encoding='utf-8') as stream:
        return list(map(json.loads, stream))

def changes(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(a.keys() | b.keys()):
            yield from changes(a.get(key), b.get(key), path + '/' + key)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from changes(x, y, path + '/' + str(i))
    elif a != b:
        yield path, a, b

def main():
    originals = {r['sample']: r for r in read('supplement_source_configs.jsonl.gz')}
    relocated = read('relocated_source_configs_verified.jsonl.gz')
    proofs = {}
    for row in relocated:
        sid = row['sample']
        differences = list(changes(originals[sid]['config'], row['config']))
        unresolved = []
        for path, before, after in differences:
            assert isinstance(before, str) and isinstance(after, str), (sid, path)
            allowed = after == PREFIX + before
            if path in OUTPUTS:
                allowed |= (Path(before).name == Path(after).name and sid in after)
            if not allowed:
                unresolved.append(dict(field=path, original=before, relocated=after))
        proofs[sid] = dict(original_sha256=originals[sid]['source_sha256'],
                           relocated_sha256=row['sha256'], changed_fields=[d[0] for d in differences],
                           result='UNRESOLVED_SOURCE_CHANGE' if unresolved else 'CONFIG_VALUES_MATCH_EXCEPT_RELOCATED_PATHS',
                           unresolved=unresolved,
                           asset_bytes_verified=False)
    rows = read('supplement_prompt_input_bindings.jsonl.gz')
    for row in rows:
        if row['source_link_status'] == 'RELOCATED_SOURCE_REQUIRES_TRANSITIVE_CHECK':
            proof = proofs[row['sample_id']]
            cam01 = next(c for c in row['runtime_config_binding'] if c['camera'] == 'cam01')
            assert cam01['source_sha256'] == proof['relocated_sha256']
            row['source_link_status'] = ('SOURCE_CHANGE_REQUIRES_REVIEW' if proof['unresolved']
                                         else 'TRANSITIVE_CONFIG_VALUES_VERIFIED')
            row['source_relocation_proof'] = proof
    target = ROOT / 'supplement_prompt_input_bindings.jsonl.gz'
    with gzip.open(target, 'wt', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row) + '\n')
    (ROOT / 'supplement_source_relocation_proofs.json').write_text(json.dumps(proofs, indent=2), encoding='utf-8')
    summary = dict(videos=len(rows), source_groups=len(originals),
                   source_link_counts=dict(collections.Counter(r['source_link_status'] for r in rows)),
                   prompt_text_built=0, formal_acceptance=False,
                   asset_bytes_verified=False,
                   binding_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (ROOT / 'supplement_prompt_input_bindings_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
