"""Two bounded original-setting T16 probes; never refine to force a Near bin."""
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
REMOTE=r'''
import copy,fcntl,hashlib,importlib.util,json,os,shutil,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
source=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t16_gpu_source_20261102')
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t16_c04_sealed_window_v2_20261030')
root=source/'endpoints';root.mkdir(exist_ok=True)
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if(root/'DISPATCH.json').exists():
 print(json.dumps(dict(previous_dispatch=json.loads((root/'DISPATCH.json').read_text()),duplicate_launched=False)));raise SystemExit
assert(source/'physics.json').exists()
deployment=json.loads((old/'deployment.json').read_text())
for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
module=importlib.util.spec_from_file_location('original_t16_worker',old/'worker.py');worker=importlib.util.module_from_spec(module);module.loader.exec_module(worker)
job=json.loads((old/'jobs.json').read_text())[0]
state=json.loads((source/'physics.json').read_text());labels,peak=worker.observe(state,job)
assert labels['folder_downstream_contact']==job['expected_labels']['folder_downstream_contact']==1 and peak<=.001
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
assert int(g.findtext('fb_memory_usage/free').split()[0])>=16000 and shutil.disk_usage(root).free>=12*1024**3
assert all(p.findtext('type')=='G'for p in g.findall('processes/process_info'))
values=[84.77370689655172,85.60546875]
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 CORE100_PRECISION_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/contact_precision_render.py',
 CORE100_MATERIAL_SEAL_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/sealed_material_render.py',
 PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
rows=[]
for theta in values:
 folder=root/format(theta,'.12g');folder.mkdir(exist_ok=False)
 config=worker.intervention(job,theta)
 config['scene_overrides']['record_contacts']=True
 config['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(folder/'unused.mp4'),
  save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
 config['annotations'].update(enabled=True,save_path=str(folder/'physics.json'))
 path=folder/'config.json';path.write_text(json.dumps(config,indent=2))
 cmd=[deployment['python'],str(old/'native_bootstrap.py'),deployment['renderer'],'--config',str(path)]
 with(folder/'run.log').open('xb')as log:
  p=subprocess.Popen(cmd,cwd=deployment['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 rows.append(dict(theta=theta,pid=p.pid,folder=str(folder),config_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
receipt=dict(started_unix=time.time(),gpu_uuid=gpu,points=rows,original_job_sha256=hashlib.sha256((old/'jobs.json').read_bytes()).hexdigest(),
 source_replay_sha256=hashlib.sha256((source/'physics.json').read_bytes()).hexdigest(),source_target_label_reproduced=True,
 source_full_trajectory_exact=False,source_contact_frames_reproduced=True,source_peak_penetration_m=peak,
 original_physics_clock_and_seed_unchanged=True,parameter_search_cases=1,parameter_probes=2,
 no_near_targeted_refinement=True,original_sources_modified=False)
(root/'DISPATCH.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''


def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE)
    (ROOT/'review/core100_v2_resolution_20261102/T16_GPU_ENDPOINT_DISPATCH.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
