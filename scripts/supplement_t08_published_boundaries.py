"""Recover T08 local event boundaries directly from published state parameters."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path

from scripts.export_original_boundary_distances import ROOT, distances


def physical_context(data,family):
    objects={o['name']:copy.deepcopy(o['spec']) for o in data['dynamic_objects']}
    if family.startswith('A_'):objects['t08_lower_impactor_book']['motion']['initial_velocity'][0]='<intervention>'
    elif family.startswith('B_'):objects['t08_target_mug']['pose']['position'][0]='<intervention>'
    elif family.startswith('C_'):
        mug=objects['t08_target_mug'];mug['mass']='<intervention>'
        if 'mass' in mug.get('material_preset',{}):mug['material_preset']['mass']='<intervention>'
    else:raise ValueError('unrecognized T08 family')
    e=data['experiment']
    payload=dict(objects=objects,scene=data['scene_overrides'],runtime_forces=data.get('runtime_forces',[]),
        background=e['background_id'],gravity=e['gravity_id'],replicate=e.get('replicate'),
        solver_revision=e['formal_sampling']['solver_revision'],
        timing={k:data['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def main():
    source=ROOT/'t08_measured_published_events.json';measured=json.loads(source.read_text(encoding='utf-8'))
    groups=collections.defaultdict(list)
    for i,r in enumerate(measured):
        if not r.get('family_id','').startswith(('A_','B_','C_')):continue
        raw=Path(r['local_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('published state hash changed')
        data=json.loads(gzip.decompress(raw));key=physical_context(data,r['family_id'])
        groups[(r['family_id'],key)].append({**r,'simulation_seed':data['experiment'].get('random_seed')})
        if i%100==0:print(json.dumps(dict(read=i+1)),flush=True)
    windows=[];rows=[]
    for (family,key),items in groups.items():
        ordered=sorted(items,key=lambda r:r['theta'])
        # Original primary surface is the independently observed support loss of
        # each body; preserve all three events rather than collapse their vector.
        for target in ['t08_lower_impactor_book_below_table_8cm','t08_upper_payload_book_below_table_8cm','t08_target_mug_below_table_8cm']:
            for a,b in zip(ordered,ordered[1:]):
                if a['theta']==b['theta'] or a['events'][target]==b['events'][target]:continue
                window=dict(family_id=family,fixed_context_sha256=key,target_event=target,bracket=[a['theta'],b['theta']],
                    endpoint_sample_ids=[a['sample_id'],b['sample_id']],endpoint_labels=[a['events'][target],b['events'][target]])
                windows.append(window)
                for r in items:
                    rows.append(dict(scene_id='T08',engine='genesis',sample_id=r['sample_id'],repo_id=r['repo_id'],revision=r['revision'],family_id=family,
                        theta=r['theta'],fixed_context_sha256=key,target_event=target,reference_label=r['events'][target],original_boundary_interval=window['bracket'],
                        **distances(r['theta'],bracket=window['bracket']),endpoint_sample_ids=window['endpoint_sample_ids'],reference_state_sha256=r['sha256'],
                        original_reference_kind='supplemental_interval_from_original_published_seed_varied_scan',original_rule_sha256=r['original_rule_sha256'],extra_validation_separate=True,
                        simulation_seed=r['simulation_seed'],endpoint_simulation_seeds=[a['simulation_seed'],b['simulation_seed']],
                        seed_scope='Original published scan varies initialization seeds. This is an observed scan transition interval, not a same-seed solved threshold.'))
    out=ROOT/'original_value_distance_ledger'
    (out/'t08_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (ROOT/'t08_supplemental_windows.json').write_text(json.dumps(windows,indent=2))
    summary=dict(fixed_physical_contexts=len(groups),local_intervals=len(windows),sample_event_interval_records=len(rows),unique_samples=len({r['sample_id'] for r in rows}),families=dict(collections.Counter(w['family_id'] for w in windows)))
    (out/'t08_supplemental_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
