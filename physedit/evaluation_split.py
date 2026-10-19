"""Import the fixed evaluation set with current dataset labels.

    python -m physedit.evaluation_split --source-dir dataset_protocol --out runs/core100

Reads local metadata and exports evaluation lists; model execution is separate.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

RELEASE_PATH = Path(__file__).with_name('core100.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def release():
    return json.loads(RELEASE_PATH.read_text())


def split_for(event, protocol):
    if event in protocol['test_ood_1']:
        return 'test_ood_1'
    if event in protocol['test_ood_2']:
        return 'test_ood_2'
    return 'test_id'


def current_record(row, split):
    """Use current assignments while keeping source identity and measurement status."""
    result = {key: value for key, value in row.items()
              if key not in ('previous_v2_split', 'benchmark_pool')}
    result['split'] = split
    return result


def load(source_dir):
    """Verify published bytes before deriving event-level reporting labels."""
    protocol = release()
    root = Path(source_dir)
    for name, expected in protocol['files'].items():
        if digest(root/name) != expected:
            raise ValueError('published_split_file_sha256_mismatch: '+name)
    freeze = json.loads((root/'FREEZE.json').read_text())
    if (freeze['version'] != protocol['version'] or freeze['core_total'] != protocol['core_total']
            or freeze['core_membership_sha256'] != protocol['core_membership_sha256']
            or freeze['training_split_modified'] is not False):
        raise ValueError('published_split_freeze_mismatch')
    for name in ('core100.jsonl', 'reserve80.jsonl', 'PROTOCOL.md'):
        record = next(r for r in freeze['files'] if r['path'] == name)
        if record['sha256'] != protocol['files'][name] or record['bytes'] != (root/name).stat().st_size:
            raise ValueError('published_split_freeze_file_binding_mismatch: '+name)
    read = lambda name: [json.loads(s) for s in (root/name).read_text().splitlines() if s.strip()]
    core, reserve = read('core100.jsonl'), read('reserve80.jsonl')
    if len(core) != protocol['core_total'] or len(reserve) != protocol['reserve_total']:
        raise ValueError('published_split_count_mismatch')
    events = {f'T{n:02}' for n in range(1,21)}
    if Counter(row['event'] for row in core) != Counter({e:protocol['per_event'] for e in events}):
        raise ValueError('published_split_event_coverage_mismatch')
    all_rows = core+reserve
    for key in ('clip_id', 'anonymous_id'):
        if len({row[key] for row in all_rows}) != len(all_rows):
            raise ValueError('published_split_duplicate_'+key)
    for row in core:
        wanted = split_for(row['event'], protocol)
        declared = {'test_id':'ID_candidate_pending_group_holdout', 'test_ood_1':'OOD-1', 'test_ood_2':'OOD-2'}[wanted]
        if row['benchmark_pool'] != declared or row['membership'] != 'fixed_core100_v1':
            raise ValueError('published_split_pool_or_membership_mismatch')
        if row['training_group_exclusion_applied'] is not False:
            raise ValueError('published_split_training_status_drift')
    # Verify source bytes first, then export the current partition labels.
    assigned = [current_record(row, split_for(row['event'], protocol)) for row in core]
    reserve = [current_record(row, 'reserve') for row in reserve]
    counts = dict(Counter(row['split'] for row in assigned))
    if counts != protocol['expected_split_counts']:
        raise ValueError('published_split_pool_counts_mismatch')
    summary = dict(version=protocol['version'], repository=protocol['repository'],
                   revision=protocol['revision'], registered=len(core), reserves=len(reserve),
                   split_counts=counts, per_event=dict(Counter(row['event'] for row in core)),
                   source_classes=dict(Counter(row['source_class'] for row in core)),
                   scientific_admission=dict(Counter(row['scientific_admission'] for row in core)),
                   training_policy=protocol['training_policy'],
                   membership_frozen=True, training_group_exclusion_completed=False,
                   scientific_acceptance_complete=False, formal_test_ready=False,
                   source_files_sha256=protocol['files'], reserve_substitution=False)
    return assigned, reserve, summary


def materialize(source_dir, output_dir):
    core, reserve, summary = load(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    for split in ('test_id', 'test_ood_1', 'test_ood_2'):
        selected = [r for r in core if r['split'] == split]
        (output/(split+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
    (output/'assignments.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in core))
    (output/'reserve80.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in reserve))
    summary['output_files_sha256'] = {p.name:digest(p) for p in sorted(output.glob('*.jsonl'))}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',required=True)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    result = materialize(args.source_dir,args.out) if args.out else load(args.source_dir)[2]
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
