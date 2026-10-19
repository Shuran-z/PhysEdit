"""Read-only reference pilot for the frozen T15 V11 release; run on p25.

Writes JSON to stdout only. No generation/simulation, no GT labels inferred
from the names minus/star/plus. Physical hashes use the fields consumed by
t15_v11_physics.py, plus its actual recorded solver provenance.
"""
import collections
import copy
import hashlib
import json
from pathlib import Path

BASE = Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
BOOK = 't15v4_driver_book'
LAPTOP = 't15v4_closed_laptop'
PHONE = 't15v4_floor_phone'


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def physical_contract(config, state, remove_speed=False):
    objects = []
    for obj in config['dynamic_objects']:
        if obj['name'] not in [BOOK, LAPTOP, PHONE, 't15v4_tabletop_collision', 't15v4_floor_collision']:
            continue
        row = {k: copy.deepcopy(obj.get(k)) for k in ['name', 'size', 'mass', 'friction', 'fixed', 'pose', 'motion']}
        if remove_speed and obj['name'] == BOOK:
            velocity = row['motion'].pop('initial_velocity')
            row['motion']['fixed_velocity_yz'] = velocity[1:]
        objects.append(row)
    provenance = {k: v for k, v in state['physical_provenance'].items() if k != 'config_sha256'}
    return {'objects': objects, 'gravity': config['scene_overrides']['gravity'], 'solver': provenance}


def main():
    manifest = BASE / 'configs/v11_20260914/delivery/manifest.json'
    entries = json.loads(manifest.read_text())
    rows = []
    for entry in entries:
        config = json.loads(Path(entry['config']).read_text())
        folder = Path(entry['output'])
        state_path = folder / 'metadata/physics.json'
        state = json.loads(state_path.read_text())
        audit_path = folder / 'qa/physics_audit_scene_bounds.json'
        if not audit_path.exists():
            audit_path = folder / 'qa/physics_audit.json'
        audit = json.loads(audit_path.read_text())
        track = {name: [next(o for o in f['objects'] if o['name'] == name) for f in state['frames']]
                 for name in [BOOK, LAPTOP, PHONE]}
        frame_map = audit['event_frames']
        event_names = ['book_contacts_laptop', 'laptop_crosses_support_boundary',
                       'laptop_falls_to_floor', 'laptop_contacts_phone', 'phone_slides']
        event_vector = [int(isinstance(frame_map.get(k), (int, float)) and frame_map[k] >= 0) for k in event_names]
        raw_fall = any(o['position'][2] < -.15 for o in track[LAPTOP])
        book_spec = next(o for o in config['dynamic_objects'] if o['name'] == BOOK)
        rows.append({**entry, 'family': entry['slot'][:3] if entry['slot'].startswith('cf') else 'global',
                     'speed': book_spec['motion']['initial_velocity'][0],
                     'gravity': abs(config['scene_overrides']['gravity'][2]),
                     'physical_hash': sha(physical_contract(config, state)),
                     'speed_context_hash': sha(physical_contract(config, state, True)),
                     'track_hash': sha(state['frames']),
                     'config_sha256': hashlib.sha256(Path(entry['config']).read_bytes()).hexdigest(),
                     'state_sha256': hashlib.sha256(state_path.read_bytes()).hexdigest(),
                     'audit_valid': audit.get('valid'), 'events': event_vector, 'event_frames': frame_map,
                     'raw_fall': int(raw_fall), 'cached_fall_agrees': int(raw_fall) == event_vector[2],
                     'metadata': config['sample_metadata']})
    named = collections.defaultdict(list)
    contexts = collections.defaultdict(list)
    for row in rows:
        contexts[row['speed_context_hash']].append(row)
        if row['family'] == 'cfA':
            named[(row['background_id'], row['gravity_id'], row['slot'].split('_')[-1])].append(row)
    groups = []
    for key, items in named.items():
        items.sort(key=lambda x: x['speed'])
        hashes = {x['speed_context_hash'] for x in items}
        eligible = len(hashes) == 1
        extras = contexts[items[0]['speed_context_hash']] if eligible else []
        points = collections.defaultdict(set)
        for row in extras:
            points[row['speed']].add(row['raw_fall'])
        stable = [(v, next(iter(y))) for v, y in sorted(points.items()) if len(y) == 1]
        brackets = [[a[0], b[0]] for a, b in zip(stable, stable[1:]) if a[1] != b[1]]
        groups.append({'background': key[0], 'gravity': key[1], 'repeat': key[2],
                       'single_speed_contract': eligible, 'context_hash': items[0]['speed_context_hash'],
                       'points': [{'sample_id': x['sample_id'], 'speed': x['speed'], 'events': x['events']} for x in items],
                       'all_matching_speeds': [{'speed': k, 'labels': sorted(v)} for k, v in sorted(points.items())],
                       'existing_transition_brackets': brackets})
    canonical = [g for g in groups if g['background'] == 'bg01_home_ase' and g['repeat'] == 'rep01']
    # These are intentionally simple controls on reference labels, NOT video models.
    labels = [r['raw_fall'] for r in rows]
    cf_labels = [r['raw_fall'] for r in rows if r['family'] == 'cfA']
    def constant_report(labels):
        return {'n': len(labels), 'always_fall_accuracy': sum(labels) / len(labels),
                'always_no_fall_accuracy': 1 - sum(labels) / len(labels),
                'balanced_accuracy_either_constant': .5 if 0 < sum(labels) < len(labels) else None}
    result = {'status': 'reference_data_experiment_not_video_model_benchmark',
              'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'summary': {'trajectories': len(rows), 'unique_physical_configs': len({r['physical_hash'] for r in rows}),
                          'unique_state_tracks': len({r['track_hash'] for r in rows}),
                          'A_named_groups': len(groups), 'A_single_speed_groups': sum(g['single_speed_contract'] for g in groups),
                          'A_unique_speed_contexts': len({r['speed_context_hash'] for r in rows if r['family'] == 'cfA'}),
                          'raw_cached_fall_disagreements': sum(not r['cached_fall_agrees'] for r in rows)},
              'constant_controls': {'all_880': constant_report(labels), 'A_180': constant_report(cf_labels)},
              'canonical_A_groups': canonical, 'A_groups': groups, 'rows': rows}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
