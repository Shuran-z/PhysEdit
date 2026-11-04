"""Rebind the existing Isaac T06_C04 result at its original 4.1s window."""
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,hashlib,json,math
from pathlib import Path
root=Path('/data2/liyuhan/core100_remaining29_t06_20261031')
sourceraw=(root/'source.json').read_bytes();assert hashlib.sha256(sourceraw).hexdigest()==TARGET['pinned_config_sha256']
base=json.loads(sourceraw)['physics']['source_config'];result=json.loads((root/'result.json').read_text())
original_path=Path(TARGET['original_state_path']);originalraw=original_path.read_bytes();original=json.loads(originalraw)
assert hashlib.sha256(originalraw).hexdigest()==TARGET['source_state_sha256']
assert original['metadata']['engine']=='Isaac Sim 5.1.0'
assert hashlib.sha256(Path(TARGET['reference_video_path']).read_bytes()).hexdigest()==TARGET['reference_video_sha256']
required=base['experiment']['required_contact_pairs'];theta=base['experiment']['parameter']['parameter_value']
assert theta==TARGET['theta']and base['seed']==original['metadata']['source_seed']
def observe(s):
 assert len(s['trajectory'])==210
 fs=s['trajectory'][5:210];assert [f['frame_index']for f in fs]==list(range(5,210))
 first={}
 for f in fs:
  for c in f['contacts']:
   p=' / '.join(sorted(a.rsplit('/',1)[-1]for a in c['actors']));first.setdefault(p,f['frame_index'])
 hits=[first.get(' / '.join(sorted(p)))for p in required]
 return dict(label=int(all(f is not None for f in hits)),required_pair_first_contact_frames=hits)
assert observe(original)['label']==TARGET['label']==0
points=[]
for entry in result['probes']:
 p=Path(entry['state_path']);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['state_sha256']
 s=json.loads(raw);meta=s['metadata']
 cfgpath=Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/repro_20260909/inputs')/meta['source_config_filename']
 cfgraw=cfgpath.read_bytes();cfg=json.loads(cfgraw)
 assert hashlib.sha256(cfgraw).hexdigest()==entry['config_sha256']==meta['source_config_sha256']
 expected=copy.deepcopy(base);value=entry['theta']
 if value!=theta:
  expected['experiment']['parameter']['parameter_value']=value
  for force in expected['runtime_forces']:force['force_world']=[v*value/theta for v in force['force_world']]
 assert cfg==expected
 keys=['engine','physics_dt','steps_per_frame','settle_steps','pre_static_frames','force_mode','gravity','fps','frame_count','source_seed']
 assert all(meta[k]==original['metadata'][k]for k in keys)
 old_policy=copy.deepcopy(original['metadata']['material_policy']);new_policy=copy.deepcopy(meta['material_policy'])
 old_description=old_policy.pop('damping');new_description=new_policy.pop('damping');assert old_policy==new_policy
 # The producer added an inertia-based timestep refinement. For these same
 # bodies it executes factor=1 at every amplitude, so no integration setting
 # changes. Retain the code revision and the description change explicitly.
 assert meta['damping_timestep_audit']['refinement_factor']==1
 assert s['source_physics_objects']==original['source_physics_objects']
 assert abs(meta['physics_dt']*meta['steps_per_frame']*205-TARGET['horizon_s'])<1e-12
 m=observe(s);assert m['label']==entry['label']
 # Compare applied forces, including the original post-control hold tail;
 # config labels alone do not establish the executed intervention.
 error=0.
 for a,b in zip(original['trajectory'],s['trajectory']):
  assert a['external_force_world_N'].keys()==b['external_force_world_N'].keys()
  for name,v in a['external_force_world_N'].items():
   error=max(error,math.dist([x*value/theta for x in v],b['external_force_world_N'][name]))
 assert error<1e-10
 delta=None
 if value==theta:
  assert s['trajectory']==original['trajectory']
  delta=max(math.dist(x['position_m'],y['position_m'])for a,b in zip(original['trajectory'],s['trajectory'])for x,y in zip(a['objects'],b['objects']))
 points.append(dict(entry,measurement=m,config_path=str(cfgpath),source_force_waveform_maximum_error_N=error,
  original_engine_seed_force_mode_clock_and_physical_objects_verified=True,source_maximum_position_difference_m=delta,
  damping_refinement_factor=1,material_damping_description_change=[old_description,new_description],source_trajectory_exact=(True if value==theta else None)))
for interval in result['intervals']:
 assert [next(p['measurement']['label']for p in points if p['theta']==v)for v in interval['bracket']]==interval['labels']
print(json.dumps(dict(clip_id=TARGET['clip_id'],source_state_sha256=TARGET['source_state_sha256'],reference_video_sha256=TARGET['reference_video_sha256'],
 theta=theta,horizon_s=TARGET['horizon_s'],intervals=result['intervals'],points=points,
 native_source_measurement=observe(original),source_config_snapshot_sha256=hashlib.sha256(sourceraw).hexdigest(),
 result_sha256=hashlib.sha256((root/'result.json').read_bytes()).hexdigest(),new_simulations=0,original_sources_modified=False,
 original_producer_sha256=original['metadata']['code_sha256'],
 original_producer_backup_sha256=hashlib.sha256(Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/repro_20260909/backups_before_damping_fix_20260911/render_repro.py').read_bytes()).hexdigest(),
 producer_difference_scope='Later producer adds timestep refinement and inertia checks. Verified refinement factor1 for every point with unchanged bodies; exact full210-frame source trajectory; original clock/forces/material scalars unchanged.',
 scope='Isaac native contact conjunction at frame4..209. Same force waveform and hold tail, no Genesis boundary or new toppling threshold.')))
'''


def main():
    registry,_=load();r=next(x for x in registry['cases']if x['clip_id']=='T06_C04')
    source_path=ROOT/'review/core100_binding_20261028/t06_isaac_search_return_20261031.json'
    old=json.loads(source_path.read_text(encoding='utf8'))['result.json']
    readback_path=ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    point=next(x['points'][0]for x in json.loads(readback_path.read_text(encoding='utf8'))if x['clip_id']=='T06_C04')
    identity=json.loads((ROOT/'review/core100_remaining74_admission_20261101/reference_review/T06_C04/IDENTITY.json').read_text(encoding='utf8'))
    target=dict(clip_id=r['clip_id'],theta=r['theta'],horizon_s=r['horizon_s'],label=r['reference_events']['complete_required_contact_chain'],
        source_state_sha256=r['source_state_sha256'],original_state_path=point['state_path'],pinned_config_sha256=old['source_pinned_config_sha256'],
        reference_video_sha256=r['reference_video_sha256'],reference_video_path=identity['video_path'])
    assert r['horizon_s']==old['horizon_s']and identity['video_sha256']==r['reference_video_sha256']
    result=rpc(P21_OPTIONS,'p25','TARGET='+repr(target)+'\n'+REMOTE)
    result['source_local_snapshot_sha256']=hashlib.sha256(source_path.read_bytes()).hexdigest()
    result['source_readback_sha256']=hashlib.sha256(readback_path.read_bytes()).hexdigest()
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t06_isaac_existing_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    (WORK/'T06_ISAAC_EXISTING.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(clip_id=result['clip_id'],intervals=result['intervals'],native_source_measurement=result['native_source_measurement'],
        source_maximum_position_difference_m=next(p['source_maximum_position_difference_m']for p in result['points']if p['theta']==r['theta']))))


if __name__=='__main__':main()
