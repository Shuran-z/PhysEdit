"""One original-setting GPU source replay for T16-C04, with no rendering.

This is not a new grid. Existing CPU source trajectories differ from the
published trajectory; test the original GPU route before admitting endpoints.
"""
import json
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

REMOTE=r'''
import copy,fcntl,hashlib,json,os,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_c04_sealed_window_v2_20261030')
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t16_gpu_source_20261102');root.mkdir(exist_ok=True)
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
launch=root/'DISPATCH.json'
if launch.exists():
 d=json.loads(launch.read_text());p=Path('/proc')/str(d['pid'])
 print(json.dumps(dict(previous_dispatch=d,process_exists=p.exists(),duplicate_launched=False)));raise SystemExit
deployment=json.loads((old/'deployment.json').read_text())
for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
job=json.loads((old/'jobs.json').read_text())[0];config=copy.deepcopy(job['base_config'])
gpu_uuid='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
xml=subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu_uuid],universal_newlines=True);g=ET.fromstring(xml).find('gpu')
assert g.findtext('uuid')==gpu_uuid
free=int(g.findtext('fb_memory_usage/free').split()[0]);processes=[]
for p in g.findall('processes/process_info'):
 processes.append(dict(pid=int(p.findtext('pid')),type=p.findtext('type'),memory_mib=int(p.findtext('used_memory').split()[0])))
if free<16000 or any(p['type']!='G'for p in processes)or sum(p['memory_mib']for p in processes)>2500:
 print(json.dumps(dict(status='waiting_for_idle_compute_gpu',gpu_uuid=gpu_uuid,free_mib=free,processes=processes)));raise SystemExit
# Unchanged physical fields, seed and solver settings. Only disable image
# outputs and enable native contact telemetry in an independent directory.
config['scene_overrides']['record_contacts']=True
config['render'].update(write_video=False,render_backend='raster',resolution=[160,96],
 save_video=str(root/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,
 save_depth_frames=False,save_seg_frames=False)
config['annotations'].update(enabled=True,save_path=str(root/'physics.json'))
path=root/'config.json';path.write_text(json.dumps(config,indent=2))
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu_uuid,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 CORE100_PRECISION_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/contact_precision_render.py',
 CORE100_MATERIAL_SEAL_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/sealed_material_render.py',
 PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
command=[deployment['python'],str(old/'native_bootstrap.py'),deployment['renderer'],'--config',str(path)]
with(root/'run.log').open('xb')as log:
 p=subprocess.Popen(command,cwd=deployment['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
d=dict(pid=p.pid,started_unix=time.time(),gpu_uuid=gpu_uuid,source_theta=job['theta'],source_state_sha256=job['state_sha256'],
 source_config_sha256=job['config_sha256'],config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
 original_physics_and_seed_preserved=True,rendering_disabled=True,new_grid=False,
 original_sources_modified=False,command=command,existing_graphics_processes=processes)
launch.write_text(json.dumps(d,indent=2));print(json.dumps(d))
'''

def main():
    from pathlib import Path
    result=rpc(P21_OPTIONS,'p25',REMOTE)
    folder=Path(__file__).resolve().parents[1]/'review/core100_v2_resolution_20261102'
    (folder/'T16_GPU_SOURCE_DISPATCH.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))

if __name__=='__main__':main()
