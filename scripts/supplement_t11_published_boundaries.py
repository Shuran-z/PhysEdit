"""T11 conditional fall brackets using the original released control recipes."""
import collections
import copy
import hashlib
import json

from scripts.export_original_boundary_distances import ROOT, distances


def lerp(value,lo,hi,a,b):return a+max(0.,min(1.,(value-lo)/(hi-lo)))*(b-a)


def context(config,family,theta):
    objects={o['name']:copy.deepcopy(o) for o in config['dynamic_objects']};forces=copy.deepcopy(config['runtime_forces'])
    driver='t11_driver_eraser';relay='t11_relay_pencil_case';case='t11_eyeglasses_case'
    # Subtract the exact r010/r011 recipe rather than erasing arbitrary varying
    # fields. Repairs outside that recipe remain visible in the fingerprint.
    if family=='driver_initial_speed_mps':
        for force in forces:
            if force['target']==driver:
                force['force_world'][0]-=lerp(theta,1.8,3.6,.18,.30)
                force['force_world_after_contact'][0]-=lerp(theta,1.8,3.6,0,.60)
                force['stop_after_contact_delay_frames']-=int(round(lerp(theta,1.8,3.6,0,20)))
    elif family in ['relay_case_gap_m','case_edge_margin_m']:
        delta=lerp(theta,.012,.085,.12,.27) if family=='relay_case_gap_m' else lerp(theta,.025,.175,.008,.22)
        for name in ([driver,relay] if family=='relay_case_gap_m' else [driver,relay,case]):objects[name]['pose']['position'][0]+=delta
    elif family=='relay_block_mass_kg':
        objects[relay]['mass']-=theta
        if 'mass' in objects[relay].get('material_preset',{}):objects[relay]['material_preset']['mass']-=theta
        expected=.35+10*max(0.,theta-.08)
        for force in forces:
            if force['target']==driver:
                for key in ['force_world_after_first_contact','force_world_relay_phase']:force[key][0]-=expected
    else:raise ValueError('unknown original T11 parameter family')
    def stable(x):
        if isinstance(x,float):return round(x,9)
        if isinstance(x,list):return [stable(v) for v in x]
        if isinstance(x,dict):return {k:stable(v) for k,v in x.items()}
        return x
    e=config['experiment']
    payload=dict(objects=objects,forces=forces,scene=config['scene_overrides'],manifest=config.get('manifest'),room_boundary=config.get('room_boundary'),
        seed=e.get('simulation_seed'),random_seed=e.get('random_seed'),background=e['background_id'],gravity=e['gravity_id'],
        timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(stable(payload),sort_keys=True).encode()).hexdigest()


def main():
    states={r['sample_id']:r for r in json.loads((ROOT/'t11_published_final_states.json').read_text(encoding='utf-8')) if 'error' not in r}
    parameters={r['sample_id']:r for r in map(json.loads,(ROOT/'original_value_distance_ledger/t11_current_published_parameters.jsonl').read_text(encoding='utf-8').splitlines())}
    groups=collections.defaultdict(list)
    for path in ROOT.glob('t11_latest_*_evidence_20261019.json'):
        for record in json.loads(path.read_text(encoding='utf-8')):
            f=next(f for f in record['files'] if '/configs/' in f['archive_path']);c=f['data'];r=parameters[record['sample_id']];family=r['family_id']
            if family=='joint_global_configuration' or r['sample_id'] not in states:continue
            state=states[r['sample_id']]
            if state['config_sha256']!=r['original_config_sha256']:raise ValueError('state/config publication identity mismatch')
            key=context(c,family,r['theta']);groups[(family,key)].append({**r,'state':state})
    windows=[];rows=[]
    for (family,key),items in groups.items():
        values=collections.defaultdict(list)
        for r in items:values[r['theta']].append(r)
        for name in ['t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case']:
            consistent={t:rr for t,rr in values.items() if len({r['state']['fallen'][name] for r in rr})==1}
            for a,b in zip(sorted(values),sorted(values)[1:]):
                if a not in consistent or b not in consistent:continue
                left,right=consistent[a][0],consistent[b][0]
                if left['state']['fallen'][name]==right['state']['fallen'][name]:continue
                window=dict(family_id=family,fixed_context_sha256=key,target_event=name+'_final_center_below_minus_20cm',bracket=[a,b],endpoint_sample_ids=[left['sample_id'],right['sample_id']])
                windows.append(window)
                for r in items:
                    rows.append({**{k:v for k,v in r.items() if k!='state'},**window,'original_boundary_interval':[a,b],**distances(r['theta'],bracket=[a,b]),
                        'reference_label':r['state']['fallen'][name],'reference_state_sha256':r['state']['state_sha256'],
                        'original_reference_kind':'supplemental_interval_from_original_published_states',
                        'original_target_definition':r['state']['original_target_definition']})
    out=ROOT/'original_value_distance_ledger'
    (out/'t11_supplemental_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (ROOT/'t11_supplemental_windows.json').write_text(json.dumps(windows,indent=2))
    summary=dict(states=len(states),fixed_contexts=len(groups),local_event_intervals=len(windows),sample_event_interval_records=len(rows),unique_samples=len({r['sample_id'] for r in rows}),
        by_family=dict(collections.Counter(w['family_id'] for w in windows)))
    (out/'t11_supplemental_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
