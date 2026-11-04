"""Render an isolated new reference pair from already validated GPU states.

This is pose replay, not a new numerical search or a published-video relabel.
Original inputs, simulation outputs and annotation jobs are never overwritten.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_six_replacements_20261103'
REMOTE = r'''
import copy,fcntl,hashlib,json,os,pathlib,subprocess,xml.etree.ElementTree as ET
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_replacement_rgb_replay_v2_20261103');root.mkdir(exist_ok=True)
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(r):
 p=pathlib.Path('/proc',str(r['pid']),'cmdline')
 return p.exists()and str(pathlib.Path(r['folder'])/'config.json').encode()in p.read_bytes()
old=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029')
dep=json.loads((old/'deployment.json').read_text());source=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102/endpoints')
points=[]
for target in TARGETS:
 cid=target['clip_id'];dest=root/cid;receipt=dest/'DISPATCH.json'
 if receipt.exists():
  r=json.loads(receipt.read_text());assert r['source_state_sha256']==target['state_sha256']
 else:
  assert ACTION=='launch','replacement_render_not_dispatched'
  query=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],text=True)).find('gpu')
  assert int(query.findtext('fb_memory_usage/free').split()[0])>=9000,'replacement_render_memory_pending'
  dest.mkdir(exist_ok=False);sp=pathlib.Path(target['state_path']);assert sha(sp)==target['state_sha256'];state=json.loads(sp.read_text())
  assert len(state['frames'])==210 and target['actual_original_objects_axis_seed_solver_controller_and_clock_verified']
  # Keep only the original exterior contact list for the exported replay;
  # native all-substep evidence stays immutable in the numerical source.
  replay=copy.deepcopy(state)
  for f in replay['frames']:
   if 'original_exterior_contacts'in f:f['contacts']=f['original_exterior_contacts']
  path=dest/'trajectory_replay.json';path.write_text(json.dumps(replay))
  cfg=json.loads((pathlib.Path(target['folder'])/'config.json').read_text());original_render=copy.deepcopy(state['render'])
  cfg['experiment'].update(trajectory_id='T18_CRITICAL_GPU_PAIR_20261103_'+cid)
  cfg.update(trajectory_replay_path=str(path),trajectory_replay_sha256=sha(path))
  cfg['render'].update(write_video=True,render_backend='raytracing',resolution=[1280,720],raytracing_spp=32,
    save_video=str(dest/'reference.mp4'),save_first_rgb=str(dest/'first.png'),save_last_rgb=str(dest/'last.png'),
    save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  cfg['annotations'].update(enabled=True,save_path=str(dest/'rendered_state.json'))
  cp=dest/'config.json';cp.write_text(json.dumps(cfg,indent=2))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,PYOPENGL_PLATFORM='egl',EGL_DEVICE_ID='4',CORE100_BACKEND='gpu32',
    TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
  for k in ['CORE100_NO_RGB','CORE100_NUMERIC_ONLY','CORE100_RELEASE_HOOK','CORE100_MATERIAL_SEAL_HOOK']:env.pop(k,None)
  # A pose renderer must never execute the numerical telemetry bootstrap:
  # its contract requires physics substeps, which replay deliberately lacks.
  bootstrap=root/'replay_bootstrap.py'
  bootstrap_text="""import hashlib,importlib.util,json,os,pathlib,sys
import genesis as gs
renderer=pathlib.Path(sys.argv[1]);config_path=pathlib.Path(sys.argv[sys.argv.index('--config')+1]);config=json.loads(config_path.read_text())
assert config['trajectory_replay_path'] and config['render']['write_video']
original_init=gs.init
def init(*args,**kwargs):
 kwargs.update(backend=gs.gpu,precision='32');result=original_init(*args,**kwargs)
 (config_path.parent/'runtime_backend.json').write_text(json.dumps(dict(backend='gpu32_pose_replay',seed=kwargs.get('seed'),simulation_steps_forbidden=True)))
 return result
gs.init=init
def forbidden(*args,**kwargs):raise RuntimeError('Reference pose replay must not execute physics steps')
gs.Scene.step=forbidden
sys.path[:0]=[str(renderer.parent),str(renderer.parents[1])];sys.argv=[str(renderer)]+sys.argv[2:]
spec=importlib.util.spec_from_file_location('_reference_pose_replay',renderer);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.main()
"""
  if bootstrap.exists():assert bootstrap.read_text()==bootstrap_text
  else:bootstrap.write_text(bootstrap_text)
  cmd=[dep['python'],str(bootstrap),dep['renderer'],'--config',str(cp)]
  with(dest/'run.log').open('xb')as log:p=subprocess.Popen(cmd,cwd=dep['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  r=dict(clip_id=cid,pid=p.pid,folder=str(dest),theta=target['theta'],source_state_sha256=sha(sp),source_state_path=str(sp),
    replay_sha256=sha(path),config_sha256=sha(cp),source_config_sha256=target['config_sha256'],gpu_uuid=gpu,
    is_new_reference_render=True,is_pose_replay=True,simulations_started=0,
    renderer_sha256=sha(pathlib.Path(dep['renderer'])),bootstrap_sha256=sha(bootstrap),simulation_steps_forbidden=True)
  receipt.write_text(json.dumps(r,indent=2))
 video=dest/'reference.mp4';log=(dest/'run.log').read_text(errors='replace')
 r['status']='running'if alive(r)else'awaiting_output_validation'if video.exists()and video.stat().st_size>1000 else'failed'
 r['log_tail']=log[-800:]
 if video.exists():r['video_bytes']=video.stat().st_size
 points.append(r)
print(json.dumps(dict(points=points,remote_root=str(root),source_files_modified=False)))
'''


def main():
    p = argparse.ArgumentParser();p.add_argument('action', choices=['launch', 'status']);args=p.parse_args()
    pointer=json.loads((ROOT/'review/core100_v2_resolution_20261102/T18_GPU_ENDPOINTS_RESULT.json').read_text())
    source=ROOT/pointer['path'];assert hashlib.sha256(source.read_bytes()).hexdigest()==pointer['sha256']
    report=json.loads(source.read_text())
    rows=[]
    for cid,theta in [('T18_C01',.04),('T18_C02',.08)]:
        row=next(r for r in report['points']if r['clip_id']=='T18_C03'and r['theta']==theta)
        assert row['status']=='completed'
        assert row['measurement']['label']==(1 if theta==.04 else 0)
        rows.append(dict({k:row[k]for k in ['theta','state_sha256','state_path','folder','config_sha256',
            'actual_original_objects_axis_seed_solver_controller_and_clock_verified']},clip_id=cid))
    payload='TARGETS='+repr(rows)+'\nACTION='+repr(args.action)+'\n'+REMOTE
    packed=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(packed)+')))')
    WORK.mkdir(exist_ok=True)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t18_render_'+args.action+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T18_RENDER_CURRENT.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'],pid=r['pid'],log_tail=r['log_tail'])for r in result['points']]))


if __name__=='__main__':main()
