"""Recompute only missing R032 C endpoints with its recovered original seed."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v3_remaining8_20261103'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,json,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v4_t03_r032_original_seed_20261103');root.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def alive(i):
 p=Path('/proc',str(i['pid']),'cmdline');return p.exists()and str(Path(i['folder'])/'config.json').encode()in p.read_bytes()
config_path=Path(ORIGINAL['path']);assert sha(config_path)==ORIGINAL['sha256'];source=json.loads(config_path.read_text())
if ACTION=='collect':
 rows=[];native_state=None
 for p in sorted(root.glob('*/DISPATCH.json')):
  i=json.loads(p.read_text());d=p.parent;s=d/'physics.json';is_live=alive(i)
  if (d/'EXCLUDED_FROM_BOUNDARY.json').exists():
   rows.append(dict(i,alive=is_live,status='excluded_wrong_C_geometry',excluded_evidence=json.loads((d/'EXCLUDED_FROM_BOUNDARY.json').read_text()),log_tail='Excluded from boundary evidence.'));continue
  row=dict(i,alive=is_live,status='running'if is_live else'failed_without_state',log_tail=(d/'run.log').read_text(errors='replace')[-500:])
  if not is_live and s.exists():
   state=json.loads(s.read_text());cfg=json.loads((d/'config.json').read_text());assert sha(d/'config.json')==i['config_sha256']
   expected=copy.deepcopy(source['dynamic_objects']);phone=next(o for o in expected if o['name']=='t03v5_lower_edge_phone');phone['pose']['position'][0]+=.1-i['theta']
   phone['pose']['position'][2]+=(i['theta']-.1)*math.tan(math.radians(source['experiment']['parameter']['lower_transfer_ramp_slope_deg']))
   assert cfg['dynamic_objects']==expected==[o.get('spec',o)for o in state['dynamic_objects']]
   differences={k:[cfg['scene_overrides'].get(k),state['scene_overrides'].get(k)]for k in set(cfg['scene_overrides'])|set(state['scene_overrides'])if cfg['scene_overrides'].get(k)!=state['scene_overrides'].get(k)}
   assert set(differences)<={'raytracing_lights','raytracing_env_map'}and len(state['frames'])==210
   assert state['render']['physics_steps_per_render_frame']==cfg['render']['physics_steps_per_render_frame']
   assert state['render']['pre_static_frames']==cfg['render']['pre_static_frames']
   backend=json.loads((d/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'and backend['actual_init_seed']==(source['random_seed']&0x7fffffff)
   assert i['event_module_sha256']==MODULE_SHA
   errors=None
   if i['theta']==.1:
    raw_native=Path(NATIVE['state_path']).read_bytes();assert hashlib.sha256(raw_native).hexdigest()==NATIVE['stored_state_sha256']
    native_state=json.loads(gzip.decompress(raw_native));errors={}
    for f,g in zip(native_state['frames'][4:155],state['frames'][4:155]):
     poses={o['name']:o for o in g['objects']}
     for o in f['objects']:errors[o['name']]=max(errors.get(o['name'],0),math.dist(o['position'],poses[o['name']]['position']))
   row.update(status='completed',state_path=str(s),state_sha256=sha(s),original_C_axis_solver_seed_and_clock_verified=True,
    backend=backend,nonphysical_background_profile_differences=differences,measurement=reference_events(state,condition_frame=4,end_frame=154),
    source_full_window_position_errors_m=errors,original_native_state_sha256=NATIVE['stored_state_sha256'])
  rows.append(row)
 print(json.dumps(dict(points=rows)));raise SystemExit
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
known={str(i['pid']):i for p in root.glob('*/DISPATCH.json')for i in[json.loads(p.read_text())]}
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 assert p.findtext('pid')in known and alive(known[p.findtext('pid')]),'Foreign compute untouched'
assert int(g.findtext('fb_memory_usage/free').split()[0])>=12000
old_bootstrap=Path('/data2/liyuhan/core100_continue_original_20261031/T04_C02/native_bootstrap.py')
prelude="import runpy as _resource_handoff\n_resource_handoff.run_path('/data2/liyuhan/core100_continue_20261031_device_policy/device_handoff.py')\n"
body=old_bootstrap.read_text();assert body.startswith(prelude);body=body[len(prelude):]
bootstrap=root/'native_bootstrap_fixed_device.py'
if bootstrap.exists():assert bootstrap.read_text()==body
else:bootstrap.write_text(body)
renderer=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T03_v5_multilevel_cascade/scripts/render_t03_v5_multicam_r032.py')
assert sha(renderer)=='482fa1a15c91e3ad2dbc63448057b08602ff9a12eaae38dc6dc06c478031a3f6'
import sys
sys.path.insert(0,'/data2/liyuhan/core100_continue_20261031_device_policy')
from egl_uuid_identity import matching_egl_index
egl=matching_egl_index(gpu);started=[]
for theta in [.1,.4]:
 dest=root/('C_'+format(theta,'.12g')+('_original_incline'if theta==.4 else''));receipt=dest/'DISPATCH.json'
 if receipt.exists():continue
 dest.mkdir(exist_ok=False);c=copy.deepcopy(source)
 phone=next(o for o in c['dynamic_objects']if o['name']=='t03v5_lower_edge_phone');phone['pose']['position'][0]+=.1-theta
 phone['pose']['position'][2]+=(theta-.1)*math.tan(math.radians(source['experiment']['parameter']['lower_transfer_ramp_slope_deg']))
 c['experiment']['parameter'].update(lower_phone_com_edge_distance_m=theta,parameter_value=theta)
 c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
 c['annotations'].update(enabled=True,save_path=str(dest/'physics.json'));config=dest/'config.json';config.write_text(json.dumps(c,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,EGL_DEVICE_ID=str(egl),CUDA_DEVICE_ORDER='PCI_BUS_ID',CORE100_BACKEND='gpu32',CORE100_NUMERIC_ONLY='1',
  TI_OFFLINE_CACHE='0',PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 with(dest/'run.log').open('xb')as log:
  p=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(config)],
    cwd=str(renderer.parents[2]),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 i=dict(clip_id='T03_C02',theta=theta,pid=p.pid,folder=str(dest),config_sha256=sha(config),original_config_sha256=ORIGINAL['sha256'],
  reference_video_sha256=REFERENCE_VIDEO_SHA,event_module_sha256=MODULE_SHA,original_random_seed=source['random_seed'],expected_Genesis_seed=source['random_seed']&0x7fffffff,
  gpu_uuid=gpu,egl_index=egl,physical_bootstrap_body_identical=True,bootstrap_sha256=sha(bootstrap),renderer_sha256=sha(renderer),formal_admission=False)
 receipt.write_text(json.dumps(i,indent=2));started.append(i)
print(json.dumps(dict(started=started,duplicate_launched=False)))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','collect']);args=parser.parse_args()
    original=json.loads((WORK/'T03_C02_ORIGINAL_CONFIG_RECOVERED.json').read_text());data,_=load();c=next(c for c in data['cases']if c['clip_id']=='T03_C02')
    module=ROOT/'physedit/t03_visual_events.py';module_sha=hashlib.sha256(module.read_bytes()).hexdigest()
    payload=module.read_text(encoding='utf8')+'\nACTION='+repr(args.action)+'\nORIGINAL='+repr(original)+'\nREFERENCE_VIDEO_SHA='+repr(c['reference_video_sha256'])+'\nNATIVE='+repr(c['reference_native_state_binding'])+'\nMODULE_SHA='+repr(module_sha)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode();r=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(r,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t03_correct_seed_'+args.action+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('T03_CORRECT_SEED_'+args.action.upper()+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(r if args.action=='launch'else[dict(clip_id=p['clip_id'],theta=p['theta'],status=p['status'],alive=p['alive'],measurement=p.get('measurement'),log_tail=p['log_tail'][-180:])for p in r['points']]))


if __name__=='__main__':main()
