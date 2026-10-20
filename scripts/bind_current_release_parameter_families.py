"""Bind current T11/T12/T13 physical parameters; never infer event labels from names."""
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bind_t13(config):
    """Use current sample metadata and collision geometry, not stale experiment fields."""
    meta=config['sample_metadata'];family=meta['main_parameter_name'];theta=float(meta['main_parameter_value'])
    objects={o['name']:o for o in config['dynamic_objects']}
    shelf=objects['t13_shelf_plank'];drink=objects['t13_drink_box']
    if shelf['pose'].get('euler_xyz')!=[0.,0.,0.] or drink['pose'].get('euler_xyz')!=[0.,0.,0.]:
        raise ValueError('T13 initial gap adapter requires the published axis-aligned initial geometry')
    shelf_width=shelf.get('collision_proxy_size',shelf['size'])[0]
    drink_width=drink.get('collision_proxy_size',drink['size'])[0]
    physical_edge=shelf['pose']['position'][0]+shelf_width/2-drink['pose']['position'][0]-drink_width/2
    if family=='drink_edge_distance':
        if not math.isclose(theta,physical_edge,abs_tol=1e-10):raise ValueError('T13 physical edge parameter mismatch')
    elif family=='driver_pivot_gap':
        physical_gap=objects['t13_falling_book']['pose']['position'][0]-objects['t13_driver_book']['motion']['pivot_world'][0]
        if not math.isclose(theta,physical_gap,abs_tol=1e-10):raise ValueError('T13 physical driver pivot gap mismatch')
    elif family=='book_cluster_shift_toward_drink':
        if theta!=meta['book_cluster_shift_m']:raise ValueError('T13 cluster shift metadata conflict')
    else:raise ValueError('unknown T13 current-release family')
    return dict(family=family,theta=theta,unit='m',physical_edge_distance_m=physical_edge,
                parameter_source='sample_metadata.main_parameter_value, checked against collision geometry where directly defined',
                stale_experiment_edge_distance=config['experiment'].get('drink_edge_distance'),
                stale_t13_parameters_edge_distance=config.get('t13_parameters',{}).get('drink_edge_distance'))


def main():
    release=json.loads((ROOT/'new_release_manifests_20261019.json').read_text(encoding='utf-8'))[0]
    records=[]
    for path in ROOT.glob('t11_latest_*_evidence_20261019.json'):
        for row in json.loads(path.read_text(encoding='utf-8')):
            file=next(f for f in row['files'] if '/configs/' in f['archive_path']);c=file['data'];exp=c['experiment'];p=exp['parameter']
            records.append(dict(scene='T11',sample_id=row['sample_id'],revision=release['revision'],source_sha256=file['sha256'],family=exp['formal_design']['changed_variable'],theta=p['parameter_value'],
                declared_parameter_name=p['parameter_name'],declared_unit=p['parameter_unit'],
                actual_driver_initial_speed_mps=p['driver_initial_speed_mps'],runtime_forces=c.get('runtime_forces',[]),
                actual_parameter_recipe=p,simulation_seed=exp.get('simulation_seed'),
                physical_contract_sha256=digest({k:c.get(k) for k in ['dynamic_objects','scene_overrides','runtime_forces']}),
                status='current_release_bound_boundary_unfinished',
                note='A coordinate named speed may control a finite-force recipe; do not interpret as an actual initial velocity'))
    with gzip.open(ROOT/'t12_latest_verified_records_20261019.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            if '/configs/' not in r['path']:continue
            c=r['data'];exp=c['experiment'];objects={o['name']:o for o in c['dynamic_objects']};params=c['t12_parameters']
            values=dict(speed=objects['t12_stapler']['motion']['initial_velocity'][0],friction=objects['t12_stapler']['friction'],target_mass=objects['t12_tissue_box']['mass'])
            if values!=dict(speed=params['stapler_initial_velocity_mps'][0],friction=params['stapler_friction'],target_mass=params['tissue_mass_kg']):raise ValueError('R005 declared/runtime parameter mismatch')
            records.append(dict(scene='T12',sample_id=c['sample_id'],revision=release['revision'],source_sha256=r['sha256'],family='joint_parameter_grid',values=values,random_seed=c.get('random_seed'),background=exp['background_id'],gravity=exp['gravity_id'],
                physical_contract_sha256=digest({k:c.get(k) for k in ['dynamic_objects','scene_overrides','runtime_forces','random_seed']}),status='current_release_bound_fixed_context_slices_and_boundaries_unfinished'))
    for line in (ROOT/'t13_latest_archive_records_20261019.jsonl').open(encoding='utf-8'):
        r=json.loads(line)
        if 'config' not in r:continue
        c=r['config'];sid=r['path'].split('/')[1].removesuffix('_rgb3d');m=c['sample_metadata']
        records.append(dict(scene='T13',sample_id=sid,revision=release['revision'],source_sha256=r['sha256'],archive_sha256=r['archive_sha256'],background=m['background_id'],gravity=m['gravity_id'],**bind_t13(c),
            physical_contract_sha256=digest({k:c.get(k) for k in ['dynamic_objects','scene_overrides','runtime_forces','random_seed']}),status='current_release_bound_event_boundary_unfinished'))
    target=ROOT/'current_release_parameter_bindings_20261019.jsonl'
    target.write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    summary={scene:dict(samples=sum(r['scene']==scene for r in records),families=dict(collections.Counter(r['family'] for r in records if r['scene']==scene))) for scene in ['T11','T12','T13']}
    (ROOT/'current_release_parameter_bindings_summary_20261019.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
