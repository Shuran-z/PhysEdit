"""Explain failed source replays without changing published labels or intervals."""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path

try:
    from scripts.t18_table_contact_boundary_worker import table_event
except ModuleNotFoundError:
    from t18_table_contact_boundary_worker import table_event


def contact_history(config, frames):
    labels=[]
    for frame in frames:
        try:labels.append(table_event(config,frame)['label'])
        except ValueError as exc:
            if str(exc)!='native final contact telemetry absent':raise
            labels.append(None)
    # Missing contact telemetry is unknown, including intermediate frames.
    return dict(ever=1 if 1 in labels else 0 if all(v==0 for v in labels) else None, terminal=labels[-1],
                first_frame=next((i for i, value in enumerate(labels) if value), None),
                contact_frame_count=sum(v==1 for v in labels),unknown_frame_count=labels.count(None),terminal_sequence=labels[-10:])


def compare(config, source, replay):
    a = contact_history(config, source['frames'])
    b = contact_history(config, replay['frames'])
    actors = {o['name'] for o in config['dynamic_objects']}
    def positions(frame):
        return {o['name']: o['position'] for o in frame['objects'] if o['name'] in actors}
    if len(source['frames']) != len(replay['frames']):
        raise ValueError('different observation windows')
    errors = [max(math.dist(positions(x)[n], positions(y)[n]) for n in actors)
              for x, y in zip(source['frames'], replay['frames'])]
    first_contact = min((a['first_frame'] if a['first_frame'] is not None else len(errors),
                         b['first_frame'] if b['first_frame'] is not None else len(errors)))
    same_specs = ({o['name']: o['spec'] for o in source['dynamic_objects']} ==
                  {o['name']: o['spec'] for o in replay['dynamic_objects']})
    category = ('physical_configuration_mismatch' if not same_specs else
                'terminal_contact_unknown' if a['terminal'] is None or b['terminal'] is None else
                'different_terminal_contact_partial_history' if a['terminal']!=b['terminal'] and (a['ever'] is None or b['ever'] is None) else
                'same_ever_contact_different_terminal_contact' if a['ever'] == b['ever'] and a['terminal'] != b['terminal'] else
                'different_contact_history' if a['ever'] != b['ever'] else
                'event_matches_on_recheck')
    return dict(category=category, source_contact=a, replay_contact=b,
                dynamic_specs_match=same_specs, initial_error_m=errors[0],
                pre_table_contact_max_error_m=max(errors[:first_contact], default=0),
                max_position_error_m=max(errors),
                first_error_over_1mm_frame=next((i for i, value in enumerate(errors) if value > .001), None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    base, out = Path(args.base), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {j['job_id']: j for j in json.loads((base / 'inputs/plan_all567.json').read_text())}
    completed, failures = set(), {}
    for root in [base / name for name in ['run', 'legacy_run', 'asset_retry_run']] + sorted(base.glob('resource_parallel_20261022_*'))+sorted(base.glob('source_retry_20261025_*')):
        completed.update(p.parent.name for p in root.glob('*/result.json'))
        for status in [root/'status_before_disk_recovery_20261025.json',root/'status.json']:
            if not status.exists():continue
            for row in json.loads(status.read_text()):
                if row['status'] == 'failed' and row.get('error')=='published source event did not reproduce':
                    failures[row['job_id']] = (root, row)
    records = []
    for key, (root, failed) in failures.items():
        if key in completed:
            continue
        job = jobs[key]
        theta = job['base_config']['experiment']['parameter']['parameter_value']
        folder = root / key / format(theta, '.12g')
        cache = out / (key + '.json')
        if cache.exists():
            cached=json.loads(cache.read_text())
            if cached.get('category')!='audit_pending':
                records.append(cached)
                continue
        try:
            receipt = json.loads((folder / 'receipt.json').read_text())
            source_path = Path(job['source_event']['source_state_path'])
            stored = source_path.read_bytes()
            if hashlib.sha256(stored).hexdigest() != job['reference_state_sha256']:
                raise ValueError('published state digest mismatch')
            source = json.loads(gzip.decompress(stored) if source_path.suffix == '.gz' else stored)
            stored = Path(receipt['state_path']).read_bytes()
            raw = gzip.decompress(stored) if receipt['state_path'].endswith('.gz') else stored
            if hashlib.sha256(raw).hexdigest() != receipt['state_sha256']:
                raise ValueError('replay state digest mismatch')
            replay = json.loads(raw)
            result = compare(job['base_config'], source, replay)
            if result['source_contact']['terminal'] is not None and result['source_contact']['terminal'] != job['reference_label']:
                raise ValueError('reference rule differs from existing job')
            row = dict(job_id=key, sample_id=job['sample_id'], original_error=failed['error'],
                       source_state_sha256=job['reference_state_sha256'], replay_state_sha256=receipt['state_sha256'],
                       source_seed=job['base_config'].get('seed'), original_labels_unchanged=True, **result)
        except Exception as exc:
            row = dict(job_id=key, sample_id=job['sample_id'], category='audit_pending', error=str(exc))
        cache.write_text(json.dumps(row, indent=2))
        records.append(row)
        (out / 'progress.json').write_text(json.dumps(dict(examined=len(records), planned=len(failures))))
    summary = dict(examined=len(records), categories=dict(collections.Counter(r['category'] for r in records)),
                   scope='Observed causes and event-window disagreement; no unique solver-internal cause asserted.',
                   reference_labels_changed=0)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
