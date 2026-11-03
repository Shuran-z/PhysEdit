"""Check T03 original config seeds and both executed C-axis endpoints."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'benchmarks/t03_observable_stage_candidate_v1_20261103'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
paths={
'T03_C02':('/data_cached/wangzijun_p25/t03_configs_r032_pbr_scene/'+TARGETS[0]['sample_id']+'/cam03.json','41a4c371bd9b5dd460a267890543299ca0b992b2d44d3b056645f713125cfc9d'),
'T03_C03':('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T03_v5_multilevel_cascade/configs/formal_480p_fullsim_r014/'+TARGETS[1]['sample_id']+'/cam03.json','c6e798b5f59f1fc7d61e306626fde4127fd33d000706f902f90725fdbd014311')}
lighting={'raytracing_lights','raytracing_env_map','raytracing_env_euler','raytracing_env_encoding','raytracing_env_map_required','raytracing'}
rows=[]
for t in TARGETS:
 p=Path(paths[t['clip_id']][0]);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==paths[t['clip_id']][1]
 c=json.loads(raw);raw_state=Path(t['native']['state_path']).read_bytes();s=json.loads(gzip.decompress(raw_state))
 assert hashlib.sha256(raw_state).hexdigest()==t['native']['stored_state_sha256']
 assert c['dynamic_objects']==[o.get('spec',o)for o in s['dynamic_objects']]
 assert all(c['scene_overrides'].get(k)==s['scene_overrides'].get(k)for k in set(c['scene_overrides'])|set(s['scene_overrides'])if k not in lighting)
 assert c.get('runtime_forces',[])==s.get('runtime_forces',[])
 root=Path('/data2/liyuhan/core100_continue_families_20261031')/t['clip_id']
 effective=c['random_seed']&0x7fffffff;points=[]
 for theta in [.1,.4]:
  d=root/t['clip_id']/'profile_0'/str(theta);cfg=json.loads((d/'config.json').read_text());backend=json.loads((d/'runtime_backend.json').read_text())
  expected=copy.deepcopy(c['dynamic_objects']);phone=next(o for o in expected if o['name']=='t03v5_lower_edge_phone')
  phone['pose']['position'][0]+=.1-theta
  phone['pose']['position'][2]+=(theta-.1)*math.tan(math.radians(c['experiment']['parameter']['lower_transfer_ramp_slope_deg']))
  def close(a,b):
   if type(a)in[int,float]and type(b)in[int,float]:return math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12)
   if type(a)!=type(b):return False
   if isinstance(a,dict):return set(a)==set(b)and all(close(a[k],b[k])for k in a)
   if isinstance(a,list):return len(a)==len(b)and all(close(x,y)for x,y in zip(a,b))
   return a==b
  objects_match=close(cfg['dynamic_objects'],expected)
  physics_match=all(cfg['scene_overrides'].get(k)==c['scene_overrides'].get(k)for k in set(cfg['scene_overrides'])|set(c['scene_overrides'])if k not in lighting)
  clock_match=all(cfg['render'].get(k)==c['render'].get(k)for k in ['frames','pre_static_frames','physics_steps_per_render_frame'])
  receipt=json.loads((d/'receipt.json').read_text());raw=Path(receipt['state_path']).read_bytes();decoded=gzip.decompress(raw)
  assert hashlib.sha256(decoded).hexdigest()==receipt['state_sha256']
  actual=json.loads(decoded)
  assert {o['name']:o.get('spec',o)for o in actual['dynamic_objects']}=={o['name']:o for o in cfg['dynamic_objects']}
  errors={}
  if theta==.1:
   for f,g in zip(s['frames'][4:155],actual['frames'][4:155]):
    poses={o['name']:o for o in g['objects']}
    for o in f['objects']:errors[o['name']]=max(errors.get(o['name'],0),math.dist(o['position'],poses[o['name']]['position']))
  points.append(dict(theta=theta,original_C_geometry_verified=objects_match,physical_solver_matches_original=physics_match,
    original_window_clock_matches=clock_match,original_config_seed_matches=cfg.get('random_seed')==c.get('random_seed'),
    actual_backend=backend,effective_seed_matches=backend['actual_init_seed']==effective,
    decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),config_sha256=hashlib.sha256((d/'config.json').read_bytes()).hexdigest(),
    source_full_window_position_errors_m=errors if theta==.1 else None))
 rows.append(dict(clip_id=t['clip_id'],original_config_path=str(p),original_config_sha256=paths[t['clip_id']][1],
  native_stored_state_sha256=t['native']['stored_state_sha256'],reference_video_sha256=t['reference_video_sha256'],
  physical_objects_solver_controls_verified=True,source_random_seed=c['random_seed'],effective_Genesis_seed=effective,
  metadata_experiment_seed=s['experiment'].get('seed'),experimental_seed_is_not_Genesis_seed=True,
  points=points,original_parameter='lower_phone_com_edge_distance_m',normalization_domain=[.006,.1]))
print(json.dumps(dict(cases=rows,simulations_started=0,old_reference_labels_modified=False)))
'''


def main():
    r,_=load();targets=[dict(clip_id=c['clip_id'],sample_id=c['sample_id'],native=c['reference_native_state_binding'],reference_video_sha256=c['reference_video_sha256'])for c in r['cases']if c['clip_id']in ['T03_C02','T03_C03']]
    encoded=base64.b64encode(zlib.compress(('TARGETS='+repr(targets)+'\n'+REMOTE).encode())).decode()
    r=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(r,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=OUT/('original_axis_contract_'+digest[:12]+'.json');path.write_bytes(raw)
    (OUT/'ORIGINAL_AXIS_CONTRACT.json').write_text(json.dumps(dict(path=path.name,sha256=digest),indent=2))
    print(json.dumps([dict(clip_id=c['clip_id'],seed=c['effective_Genesis_seed'],points=[dict(theta=p['theta'],geometry=p['original_C_geometry_verified'],solver=p['physical_solver_matches_original'],clock=p['original_window_clock_matches'],seed=p['effective_seed_matches'])for p in c['points']])for c in r['cases']]))


if __name__=='__main__':main()
