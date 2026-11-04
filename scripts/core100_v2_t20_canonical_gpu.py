"""Use the actual frozen T20 repair producer/config, never its production alias."""
import argparse
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t20_canonical_gpu_20261102');root.mkdir(exist_ok=True)
renderer=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/scripts/render_sample.py')
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_c04_sealed_window_v2_20261030/native_bootstrap.py')
precision=Path('/data_cached/wangzijun_p25/core100_recovery_20261021/contact_precision_render.py');seal=Path('/data_cached/wangzijun_p25/core100_recovery_20261021/sealed_material_render.py')
assert hashlib.sha256(bootstrap.read_bytes()).hexdigest()=='554fbab95e1c96200897083f1a8afd9af081691be35064b13f71ba8eb978b5a2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def observed(s):
 fs=s['frames'];assert len(fs)==210
 def pos(f,n):return next(o['position']for o in f['objects']if o['name']==n)
 hits=[]
 for a,b in zip(['t20_book','t20_can','t20_box'],['t20_can','t20_box','t20_cup']):
  hits.append(min(((f['frame_index'],c.get('physics_step_index',0))for f in fs[5:155]for c in f.get('original_exterior_contacts',f.get('contacts',[]))
   if{c.get('entity_a'),c.get('entity_b')}=={a,b}),default=None))
 displacement=math.dist(pos(fs[4],'t20_cup'),pos(fs[154],'t20_cup'))
 label=0 if displacement<=.015 else int(hits==sorted(hits))if all(hits)else None
 return dict(label=label,first_contact_tuples=hits,cup_final_displacement_m=displacement)
phase='gap_extension'if ACTION.endswith('gap-extension')else'source'if ACTION.endswith('source')else'endpoints';folder=root/phase;folder.mkdir(exist_ok=True);dispatch=folder/'DISPATCH.json'
if ACTION.startswith('collect'):
 receipt=json.loads(dispatch.read_text());points=[]
 for item in receipt['points']:
  d=Path(item['folder']);p=d/'physics.json'
  proc=Path('/proc',str(item['pid']),'cmdline');alive=proc.exists()and str(d/'config.json').encode()in proc.read_bytes()
  if alive or not p.exists():
   points.append(dict(clip_id=item['clip_id'],theta=item['theta'],status='running'if alive else'failed_without_state',log_tail=(d/'run.log').read_text(errors='replace')[-700:]));continue
  t=next(t for t in TARGETS if t['clip_id']==item['clip_id']);base=Path('/data_cached/wangzijun_p25/core100_recovery_20261021')/(t['clip_id']+'_geometry_r3_full')
  source=json.loads((base/'state.json').read_text());state=json.loads(p.read_text());c=json.loads((d/'config.json').read_text());original=json.loads((base/'config.json').read_text())
  manifest=json.loads((base/'RUN_MANIFEST.json').read_text());assert sha(base/'state.json')==manifest['files']['state.json']['sha256']==t['reference_native_state_sha256']
  assert sha(base/'video.mp4')==manifest['files']['video.mp4']['sha256']==t['reference_video_sha256']
  specs={o['name']:o.get('spec',o)for o in state['dynamic_objects']};expected={o['name']:copy.deepcopy(o)for o in original['dynamic_objects']}
  if t['parameter']=='box_cup_gap':
   for name in ['t20_book','t20_can','t20_box']:expected[name]['pose']['position'][0]-=item['theta']-t['theta']
  else:
   v=expected['t20_book']['motion']['initial_velocity'];speed=math.dist(v,[0,0,0]);expected['t20_book']['motion']['initial_velocity']=[x*item['theta']/speed for x in v]
  assert specs==expected and state['scene_overrides']==source['scene_overrides']==original['scene_overrides']
  if t['parameter']=='box_cup_gap':
   cup,box=[specs[n]for n in ['t20_cup','t20_box']]
   executed_theta=(cup['pose']['position'][0]-cup['size'][0]/2)-(box['pose']['position'][0]+box['size'][0]/2)
  else:executed_theta=math.dist(specs['t20_book']['motion']['initial_velocity'],[0,0,0])
  assert abs(executed_theta-item['theta'])<1e-12
  assert c['seed']==original['seed']and abs(state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']*150-5)<1e-12
  backend=json.loads((d/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'and backend['actual_init_seed']==original['seed']%(2**31-1)
  delta=None
  if phase=='source':
   delta=max(math.dist(a['position'],b['position'])for f,g in zip(source['frames'][4:155],state['frames'][4:155])for a,b in zip(f['objects'],g['objects']))
  points.append(dict(item,status='completed',state_path=str(p),state_sha256=sha(p),config_sha256=sha(d/'config.json'),
   reference_native_state_sha256=t['reference_native_state_sha256'],old_numerical_state_sha256=t['old_numerical_state_sha256'],
   reference_video_sha256=t['reference_video_sha256'],actual_frozen_solver_seed_objects_and_axis_verified=True,backend=backend,
   measurement=observed(state),source_measurement=observed(source),source_maximum_position_difference_m=delta,horizon_s=5.,
   executed_parameter_value=executed_theta,recorded_experiment_gap=c['experiment'].get('box_cup_gap'),
   parameter_attestation='Executed dynamic-object poses/velocity checked; descriptive legacy experiment fields are separately retained.',
   native_peak_penetration_m=max((ct.get('penetration_m',0)for f in state['frames'][5:155]for ct in f.get('contacts',[])),default=0),
   scope='Frozen geometry_r3_full producer/profile. Original production distances are kept separately and not transferred.'))
 print(json.dumps(dict(phase=phase,status='completed'if all(p['status']=='completed'for p in points)else'pending',points=points,source_hashes=receipt['source_hashes'],original_sources_modified=False)))
 raise SystemExit
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if dispatch.exists():print(json.dumps(dict(previous_dispatch=json.loads(dispatch.read_text()),duplicate_launched=False)));raise SystemExit
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
assert int(g.findtext('fb_memory_usage/free').split()[0])>=12000
owned={}
for path in [root/'endpoints/DISPATCH.json',root/'gap_extension/DISPATCH.json',
 Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102/source/DISPATCH.json'),
 Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102/overlap_source/DISPATCH.json')]:
 if path.exists():
  for item in json.loads(path.read_text())['points']:owned[str(item['pid'])]=str(Path(item['folder'])/'config.json')
for process in g.findall('processes/process_info'):
 if process.findtext('type')=='G':continue
 pid=process.findtext('pid');p=Path('/proc',str(pid),'cmdline')
 assert pid in owned and p.exists()and owned[pid].encode()in p.read_bytes(),'Do not interfere with foreign compute'
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 CORE100_PRECISION_HOOK=str(precision),CORE100_MATERIAL_SEAL_HOOK=str(seal),PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
rows=[]
for t in TARGETS:
 base=Path('/data_cached/wangzijun_p25/core100_recovery_20261021')/(t['clip_id']+'_geometry_r3_full')
 manifest=json.loads((base/'RUN_MANIFEST.json').read_text());assert sha(base/'config.json')==manifest['config_sha256']
 assert sha(renderer)==manifest['renderer_sha256']and sha(seal)==manifest['sealing_wrapper_sha256']
 assert sha(base/'state.json')==manifest['files']['state.json']['sha256']==t['reference_native_state_sha256']
 c=json.loads((base/'config.json').read_text());source=json.loads((base/'state.json').read_text())
 assert observed(source)['label']==1 and source['scene_overrides']==c['scene_overrides']
 assert c['scene_overrides']['default_fixed_collider_friction']==1. and c['experiment']['parameter']['parameter_value']==t['theta']
 values=[.7]if phase=='gap_extension'else[t['theta']]if phase=='source'else([t['normalization_domain'][1],.45]if t['parameter']=='box_cup_gap'else[t['normalization_domain'][0],sum(t['normalization_domain'])/2])
 for theta in values:
  c=json.loads((base/'config.json').read_text())
  d=folder/(t['clip_id']if phase=='source'else t['clip_id']+'_'+format(theta,'.12g'));d.mkdir(exist_ok=False)
  if t['parameter']=='box_cup_gap':
   for o in c['dynamic_objects']:
    if o['name']in['t20_book','t20_can','t20_box']:o['pose']['position'][0]-=theta-t['theta']
   if phase=='gap_extension':
    # Stay on the recorded round support. Do not manufacture a false branch
    # by moving the initial book off the tabletop when extending the gap.
    center=c['experiment']['support_center'];radius=c['experiment']['support_radius']
    for o in c['dynamic_objects']:
     if o['name']not in ['t20_book','t20_box']:continue
     x,y=o['pose']['position'][:2];sx,sy=o['size'][:2]
     assert all((x+dx-center[0])**2+(y+dy-center[1])**2<radius**2 for dx in[-sx/2,sx/2]for dy in[-sy/2,sy/2])
  else:
   o=next(o for o in c['dynamic_objects']if o['name']=='t20_book');v=o['motion']['initial_velocity'];speed=math.dist(v,[0,0,0]);o['motion']['initial_velocity']=[x*theta/speed for x in v]
  c['experiment']['parameter']['parameter_value']=theta
  if t['parameter']=='box_cup_gap':c['experiment']['box_cup_gap']=theta
  c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(d/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  c['annotations'].update(enabled=True,save_path=str(d/'physics.json'))
  cfg=d/'config.json';cfg.write_text(json.dumps(c,indent=2));cmd=['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(cfg)]
  with(d/'run.log').open('xb')as log:p=subprocess.Popen(cmd,cwd=str(renderer.parents[2]),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  rows.append(dict(clip_id=t['clip_id'],theta=theta,pid=p.pid,folder=str(d),config_sha256=sha(cfg),original_frozen_config_sha256=manifest['config_sha256']))
receipt=dict(phase=phase,points=rows,gpu_uuid=gpu,source_hashes={str(p):sha(p)for p in[renderer,bootstrap,precision,seal]},
 original_sources_modified=False,normalization_domains_unchanged=True,original_production_search_not_overwritten=True,
 parameter_selection='Original gap upper endpoint and gap0.45; gap extension0.7 remains fully on the recorded round support. Original speed lower endpoint and domain midpoint. Normalization unchanged; no Near targeting.')
dispatch.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch-source','collect-source','launch-endpoints','collect-endpoints','launch-gap-extension','collect-gap-extension']);args=p.parse_args()
    data,_=load();targets=[]
    for r in data['cases']:
        if r['clip_id']in ['T20_C01','T20_C05']:
            if args.action.endswith('gap-extension')and r['clip_id']!='T20_C01':continue
            targets.append(dict(clip_id=r['clip_id'],theta=r['theta'],parameter=r['parameter'],normalization_domain=r['normalization_domain'],
                old_numerical_state_sha256=r.get('historical_production_state_sha256',r['source_state_sha256']),reference_native_state_sha256=r['reference_native_state_binding']['decoded_state_sha256'],reference_video_sha256=r['reference_video_sha256']))
    result=rpc(P21_OPTIONS,'p25','ACTION='+repr(args.action)+'\nTARGETS='+repr(targets)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t20_canonical_gpu_'+args.action.replace('-','_')+'_'+digest[:12]+'.json');path.write_bytes(raw)
    name='T20_CANONICAL_GPU_'+('GAP_EXTENSION'if args.action.endswith('gap-extension')else args.action.split('-')[1].upper())+('_DISPATCH'if args.action.startswith('launch')else'_RESULT')+'.json'
    (WORK/name).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
