"""Original-setting T08 GPU replay before adopting any conditional boundary."""
import argparse
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t08_gpu_20261102');root.mkdir(exist_ok=True)
renderer=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T07_T08_v2_independent/scripts/render_t08_v3_multicam.py')
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t07_cpu_exact_20261029/native_bootstrap.py')
assert hashlib.sha256(renderer.read_bytes()).hexdigest()=='a79b32e89606d05feb1e58a78e307e3546179f59d1a6537058ac3e3b3995974a'
assert hashlib.sha256(bootstrap.read_bytes()).hexdigest()=='892a2331dd842c0380c4a8a0d2b43eb100057c6ff5ec2fb2d5c871af106e71e7'
def read_state(p):
 raw=Path(p).read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 return json.loads(decoded),raw,decoded
def position(f,name):return next(o['position']for o in f['objects']if o['name']==name)
def measurement(s):
 threshold=s['experiment']['table_top_z']-.08
 fs=s['frames'][5:155];assert [f['frame_index']for f in fs]==list(range(5,155))
 values=[position(f,'t08_target_mug')[2]for f in fs]
 return dict(label=int(min(values)<threshold),minimum_mug_world_z_m=min(values),threshold_world_z_m=threshold,
  first_threshold_frame=next((f['frame_index']for f,z in zip(fs,values)if z<threshold),None))
phase='source'if ACTION.endswith('source')else'endpoints';folder=root/phase;folder.mkdir(exist_ok=True)
dispatch=folder/'DISPATCH.json'
if ACTION.startswith('collect'):
 receipt=json.loads(dispatch.read_text());points=[]
 for item in receipt['points']:
  dest=Path(item['folder']);p=dest/'physics.json'
  proc=Path('/proc',str(item['pid']),'cmdline');alive=proc.exists()and str(dest/'config.json').encode()in proc.read_bytes()
  if alive or not p.exists():
   points.append(dict(clip_id=item['clip_id'],theta=item['theta'],status='running'if alive else'failed_without_state',
    log_tail=(dest/'run.log').read_text(errors='replace')[-1800:]));continue
  target=next(t for t in TARGETS if t['clip_id']==item['clip_id']);original,packed,decoded=read_state(target['source_state_path'])
  assert target['source_state_sha256']in[hashlib.sha256(packed).hexdigest(),hashlib.sha256(decoded).hexdigest()]
  state,raw,_=read_state(p);c=json.loads((dest/'config.json').read_text())
  specs={o['name']:o.get('spec',o)for o in state['dynamic_objects']};assert specs=={o['name']:o for o in c['dynamic_objects']}
  old={o['name']:copy.deepcopy(o.get('spec',o))for o in original['dynamic_objects']}
  expected=copy.deepcopy(old);v=expected['t08_lower_impactor_book']['motion']['initial_velocity'];norm=math.dist(v,[0,0,0])
  expected['t08_lower_impactor_book']['motion']['initial_velocity']=[x*item['theta']/norm for x in v]
  assert specs==expected
  differences={k:[v,state['scene_overrides'].get(k)]for k,v in original['scene_overrides'].items()if state['scene_overrides'].get(k)!=v}
  assert not differences
  period=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame'];assert abs(period*150-5)<1e-12
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
  errors=[math.dist(position(f,n),position(g,n))for f,g in zip(original['frames'][4:155],state['frames'][4:155])for n in old]
  points.append(dict(item,status='completed',source_state_sha256=target['source_state_sha256'],reference_video_sha256=target['reference_video_sha256'],
   config_sha256=hashlib.sha256((dest/'config.json').read_bytes()).hexdigest(),state_path=str(p),state_sha256=hashlib.sha256(raw).hexdigest(),
   original_specs_and_intervention_verified=True,original_solver_differences=differences,backend=backend,
   measurement=measurement(state),source_measurement=measurement(original),source_maximum_position_difference_m=max(errors)if phase=='source'else None,
   native_peak_penetration_m=max((ct['penetration_m']for f in state['frames'][5:155]for ct in f.get('contacts',[])),default=0),
   horizon_s=5.,native_frame_count=len(state['frames']),
   seed_scope='Original config seed/experiment header preserved. Actual original gs.init seed was not attested by the released state; current executed seed recorded separately.'))
 print(json.dumps(dict(phase=phase,status='completed'if all(p['status']=='completed'for p in points)else'pending',points=points,
  original_sources_modified=False,scope='Original recorded object specifications and solver settings on GPU32, with added observation-only telemetry; not a physical convergence certificate.')))
 raise SystemExit
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if dispatch.exists():print(json.dumps(dict(previous_dispatch=json.loads(dispatch.read_text()),duplicate_launched=False)));raise SystemExit
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
assert int(g.findtext('fb_memory_usage/free').split()[0])>=16000
owned={}
for path in [Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t20_canonical_gpu_20261102/source/DISPATCH.json')]:
 if path.exists():
  for item in json.loads(path.read_text())['points']:owned[str(item['pid'])]=str(Path(item['folder'])/'config.json')
for process in g.findall('processes/process_info'):
 if process.findtext('type')=='G':continue
 pid=process.findtext('pid');cmd=Path('/proc',str(pid),'cmdline')
 assert pid in owned and cmd.exists()and owned[pid].encode()in cmd.read_bytes(),'Do not overlap foreign compute'
if phase=='endpoints':
 for t in TARGETS:
  source=json.loads((root/'source'/t['clip_id']/'physics.json').read_text())
  assert measurement(source)['label']==t['reference_label']
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 CORE100_PRECISION_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/contact_precision_render.py',
 CORE100_MATERIAL_SEAL_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/sealed_material_render.py',
 PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
rows=[]
for t in TARGETS:
 state,packed,decoded=read_state(t['source_state_path'])
 assert t['source_state_sha256']in[hashlib.sha256(packed).hexdigest(),hashlib.sha256(decoded).hexdigest()]
 assert measurement(state)['label']==t['reference_label']
 base=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T07_T08_v2_independent/configs/formal_v4_480p')/t['sample_id']/'cam01.json'
 original_config=json.loads(base.read_text())
 for theta in([t['theta']]if phase=='source'else[t['normalization_domain'][0]]):
  dest=folder/t['clip_id'];dest.mkdir(exist_ok=False);c=copy.deepcopy(original_config)
  c['dynamic_objects']=[copy.deepcopy(o.get('spec',o))for o in state['dynamic_objects']]
  c['scene_overrides']=copy.deepcopy(state['scene_overrides'])
  c['experiment']=copy.deepcopy(state['experiment'])
  v=next(o for o in c['dynamic_objects']if o['name']=='t08_lower_impactor_book')['motion']['initial_velocity'];norm=math.dist(v,[0,0,0])
  assert abs(norm-t['theta'])<1e-12
  next(o for o in c['dynamic_objects']if o['name']=='t08_lower_impactor_book')['motion']['initial_velocity']=[x*theta/norm for x in v]
  c['experiment']['book_initial_speed_mps']=theta;c['experiment']['all_physics_values']['A_book_initial_speed_mps']=theta
  c['render']=copy.deepcopy(state['render'])
  c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),
   save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  c['annotations'].update(enabled=True,save_path=str(dest/'physics.json'))
  path=dest/'config.json';path.write_text(json.dumps(c,indent=2))
  command=['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(path)]
  with(dest/'run.log').open('xb')as log:
   p=subprocess.Popen(command,cwd='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  rows.append(dict(clip_id=t['clip_id'],theta=theta,pid=p.pid,folder=str(dest),config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
   original_config_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),source_physics_from='hash-pinned released runtime header, not the later edited cam01 config'))
receipt=dict(phase=phase,points=rows,gpu_uuid=gpu,rendering_disabled=True,original_sources_modified=False,
 source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in[renderer,bootstrap]},no_domain_expansion=True)
dispatch.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch-source','collect-source','launch-endpoints','collect-endpoints']);args=parser.parse_args()
    data,_=load()
    readback=json.loads((ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json').read_text(encoding='utf8'))
    sources={r['clip_id']:r['points'][0]for r in readback}
    targets=[dict(clip_id=r['clip_id'],sample_id=r['sample_id'],theta=r['theta'],normalization_domain=r['normalization_domain'],
        reference_label=r['reference_events']['t08_target_mug_below_table_8cm'],source_state_path=sources[r['clip_id']]['state_path'],
        source_state_sha256=sources[r['clip_id']]['decoded_state_sha256'],reference_video_sha256=r['reference_video_sha256'])for r in data['cases']if r['clip_id']in ['T08_C01','T08_C02','T08_C03']]
    result=rpc(P21_OPTIONS,'p25','ACTION='+repr(args.action)+'\nTARGETS='+repr(targets)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t08_gpu_'+args.action.replace('-','_')+'_'+digest[:12]+'.json');path.write_bytes(raw)
    name='T08_GPU_'+args.action.split('-')[1].upper()+('_DISPATCH'if args.action.startswith('launch')else'_RESULT')+'.json'
    (WORK/name).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
