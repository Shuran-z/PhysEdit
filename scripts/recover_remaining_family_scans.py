"""Recover every selected T16/T17/T20 scan family, including no-flip contexts."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
try:
    from scripts.register_t16_t20_contact_distances import context
    from scripts.published_contact_vectors import vector
except ModuleNotFoundError:
    from register_t16_t20_contact_distances import context
    from published_contact_vectors import vector


def recover(rows):
    groups = collections.defaultdict(list)
    pending, counts = [], collections.Counter()
    for row in rows:
        if row.get('scene_id') not in ['T16', 'T17', 'T20']:
            continue
        if row.get('status') != 'published_metadata_extracted' or not row.get('hash_verified'):
            pending.append(dict(sample_id=row.get('sample_id'), reason='unverified source'))
            continue
        counts[row['scene_id']] += 1
        try:
            signature, labels = context(row), vector(row)
            if not labels:
                raise ValueError('no applicable native-contact event')
        except (ValueError, KeyError) as exc:
            pending.append(dict(sample_id=row['sample_id'], reason=str(exc)))
            continue
        parameter = row['experiment']['parameter']
        groups[(row['scene_id'], parameter['parameter_name'], signature)].append(dict(
            scene_id=row['scene_id'], engine='genesis', sample_id=row['sample_id'], revision=row['revision'],
            family_id=parameter['parameter_name'], theta=parameter['parameter_value'],
            parameter_unit=parameter['parameter_unit'], fixed_context_sha256=signature,
            reference_state_sha256=row['metadata_sha256'], labels=labels,
            reference_scope='published seed-varied parameter scan; conditional fixed-seed searches separate'))
    bindings, windows, coverage = [], [], []
    for (scene, family, signature), members in groups.items():
        byvalue = collections.defaultdict(list)
        for member in members:
            byvalue[member['theta']].append(member)
        grid = sorted(byvalue)
        domain = [grid[0], grid[-1]]
        events = sorted({k for m in members for k in m['labels']})
        event_coverage = {}
        for event in events:
            consistent = {t: ms[0]['labels'][event] for t, ms in byvalue.items()
                          if all(event in m['labels'] for m in ms) and len({m['labels'][event] for m in ms}) == 1}
            found = []
            for a, b in zip(grid, grid[1:]):
                if a not in consistent or b not in consistent or consistent[a] == consistent[b]:
                    continue
                identity = dict(scene=scene, family=family, context=signature, target_event=event,
                                bracket=[a, b], endpoint_sample_ids=[byvalue[a][0]['sample_id'], byvalue[b][0]['sample_id']])
                job_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
                window = dict(identity, job_id=job_id, labels=[consistent[a], consistent[b]],
                              normalization_domain=domain, normalization_span=domain[1]-domain[0])
                windows.append(window)
                found.append(job_id)
                for member in members:
                    if event not in member['labels']:
                        continue
                    theta = member['theta']
                    low, high = max(a-theta, theta-b, 0), max(abs(theta-a), abs(theta-b))
                    bindings.append(dict({k: v for k, v in member.items() if k != 'labels'},
                        target_event=event, reference_label=member['labels'][event], original_boundary_interval=[a, b],
                        endpoint_sample_ids=identity['endpoint_sample_ids'], distance_lower=low, distance_upper=high,
                        normalized_distance_lower=low/(domain[1]-domain[0]), normalized_distance_upper=high/(domain[1]-domain[0]),
                        normalization_domain=domain, normalization_span=domain[1]-domain[0], refinement_job_id=job_id,
                        original_reference_kind='released_native_contact_scan_with_explicit_empty_recording_contract',
                        formal_nearacc_eligible=False))
            event_coverage[event] = dict(observed_values=len(consistent), total_released_values=len(grid),
                status='label_conflict_or_unknown' if len(consistent) != len(grid) else
                       'single_released_value' if len(grid) < 2 else
                       'observed_local_intervals' if found else 'no_observed_flip_on_released_grid', intervals=found)
        coverage.append(dict(scene_id=scene, family_id=family, fixed_context_sha256=signature,
            selected_samples=[m['sample_id'] for m in members], normalization_domain=domain,
            released_grid=grid, events=event_coverage))
    summary = dict(selected_verified_metadata=dict(counts), contexts=dict(collections.Counter(r['scene_id'] for r in coverage)),
                   intervals=dict(collections.Counter(r['scene'] for r in windows)),
                   bound_unique_samples={s: len({r['sample_id'] for r in bindings if r['scene_id']==s}) for s in counts},
                   pending_sources=len(pending), original_labels_overwritten=0, exact_root_claim=False)
    return dict(bindings=bindings, windows=windows, coverage=coverage, pending=pending, summary=summary)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--records', required=True)
    parser.add_argument('--out', required=True)
    args=parser.parse_args()
    rows=(json.loads(p.read_text()) for p in Path(args.records).glob('T*.json'))
    data=recover(rows)
    out=Path(args.out);out.mkdir(parents=True, exist_ok=True)
    for key, value in data.items():
        (out/(key+'.json')).write_text(json.dumps(value, indent=2))
    print(json.dumps(data['summary']))


if __name__=='__main__':
    main()
