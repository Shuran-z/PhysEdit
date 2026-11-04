"""Bounded original-GPU T07 probes after saved same-context contrasts ran out."""
import argparse
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,importlib.util,json,math,os,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t07_cpu_exact_20261029')
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t07_gpu_20261102');root.mkdir(exist_ok=True)
deployment=json.loads((old/'deployment.json').read_text())
for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
spec=importlib.util.spec_from_file_location('original_t07_worker',old/'worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
jobs=json.loads((old/'jobs.json').read_text());assert len(jobs)==3
def read_state(path):
 raw=Path(path).read_bytes();return json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw),raw
def motion(state):
 origin=next(o['position']for o in state['frames'][4]['objects']if o['name']=='t07_smartphone')
 values=[(f['frame_index'],math.dist(origin,o['position']))for f in state['frames'][5:155]for o in f['objects']if o['name']=='t07_smartphone']
 return dict(label=int(max(v for _,v in values)>=.01),first_threshold_frame=next((f for f,v in values if v>=.01),None),maximum_displacement_m=max(v for _,v in values))
phase='source'if ACTION.endswith('source')else'endpoints';folder=root/phase;folder.mkdir(exist_ok=True)
dispatch=folder/'DISPATCH.json'
if ACTION.startswith('collect'):
 launched=json.loads(dispatch.read_text());rows=[]
 for item in launched['points']:
  dest=Path(item['folder']);path=dest/'physics.json'
  if not path.exists():
   rows.append(dict(clip_id=item['clip_id'],theta=item['theta'],status='running'if Path('/proc',str(item['pid'])).exists()else'failed_without_state',log_tail=(dest/'run.log').read_text()[-350:]));continue
  state,raw=read_state(path);job=next(j for j in jobs if j['clip_id']==item['clip_id'])
  configraw=(dest/'config.json').read_bytes();config=json.loads(configraw)
  assert hashlib.sha256(configraw).hexdigest()==item['config_sha256']
  expected=worker.intervention(job,item['theta']);assert config['dynamic_objects']==expected['dynamic_objects']and config['seed']==expected['seed']
  for k in['dt','substeps','constraint_timeconst']:assert config['scene_overrides'].get(k)==job['base_config']['scene_overrides'].get(k)
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
  labels,peak=worker.observe(state,job);observed=motion(state);assert labels['motion_ge_1cm']==observed['label']
  original,packed=read_state(SOURCES[job['clip_id']]);assert hashlib.sha256(packed).hexdigest()==job['state_sha256']
  original_specs={o['name']:o.get('spec',o)for o in original['dynamic_objects']}
  base_specs={o['name']:o for o in job['base_config']['dynamic_objects']}
  source_solver_differences={k:[original['scene_overrides'].get(k),job['base_config']['scene_overrides'].get(k)]
   for k in['dt','substeps','constraint_timeconst','box_box_detection','use_gjk_collision']
   if original['scene_overrides'].get(k)!=job['base_config']['scene_overrides'].get(k)}
  baseline=motion(original);assert baseline['label']==job['expected_labels']['motion_ge_1cm']
  errors=[math.dist(a['position'],b['position'])for f,g in zip(original['frames'][4:155],state['frames'][4:155])for a,b in zip(f['objects'],g['objects'])]
  rows.append(dict(clip_id=job['clip_id'],theta=item['theta'],status='completed',event='motion_ge_1cm',measurement=observed,
   reference_measurement=baseline,source_state_sha256=job['state_sha256'],state_path=str(path),state_sha256=hashlib.sha256(raw).hexdigest(),
   config_sha256=item['config_sha256'],original_seed_solver_and_intervention_verified=True,backend=backend,
   original_source_specs_match=original_specs==base_specs,original_source_solver_differences=source_solver_differences,
   seed_execution_note='Original config seed preserved; this original wrapper did not record an explicit gs.init seed.'if backend['actual_init_seed']is None else'Explicit init seed recorded.',
   native_peak_m=peak,quality_passed=peak<=.001,source_full_trajectory_exact=max(errors)==0,
   source_position_error_m=max(errors)if phase=='source'else None,source_theta=job['theta'],horizon_s=5.0))
 print(json.dumps(dict(phase=phase,status='completed'if all(r['status']=='completed'for r in rows)else'pending',points=rows,
  original_sources_modified=False,scope='Original-settings GPU32 probes; no numerical-convergence or exact-published-trajectory claim.')))
 raise SystemExit
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if dispatch.exists():print(json.dumps(dict(previous_dispatch=json.loads(dispatch.read_text()),duplicate_launched=False)));raise SystemExit
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
assert int(g.findtext('fb_memory_usage/free').split()[0])>=16000
assert all(p.findtext('type')=='G'for p in g.findall('processes/process_info'))
if phase=='endpoints':
 for job in jobs:
  path=root/'source'/job['clip_id']/'physics.json';state,_=read_state(path);labels,peak=worker.observe(state,job)
  assert labels==job['expected_labels']and peak<=.001
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 CORE100_PRECISION_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/contact_precision_render.py',
 CORE100_MATERIAL_SEAL_HOOK='/data_cached/wangzijun_p25/core100_recovery_20261021/sealed_material_render.py',
 PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
rows=[]
for job in jobs:
 original,packed=read_state(SOURCES[job['clip_id']]);assert hashlib.sha256(packed).hexdigest()==job['state_sha256']
 for theta in([job['theta']]if phase=='source'else[.26,.28]):
  dest=folder/(job['clip_id']if phase=='source'else job['clip_id']+'_'+str(theta));dest.mkdir(exist_ok=False)
  config=worker.intervention(job,theta);config['scene_overrides']['record_contacts']=True
  config['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),
   save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  config['annotations'].update(enabled=True,save_path=str(dest/'physics.json'))
  path=dest/'config.json';path.write_text(json.dumps(config,indent=2))
  command=[deployment['python'],str(old/'native_bootstrap.py'),deployment['renderer'],'--config',str(path)]
  with(dest/'run.log').open('xb')as log:
   p=subprocess.Popen(command,cwd=deployment['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  rows.append(dict(clip_id=job['clip_id'],theta=theta,pid=p.pid,folder=str(dest),config_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
receipt=dict(phase=phase,points=rows,gpu_uuid=gpu,original_physics_and_seed_preserved=True,rendering_disabled=True,
 no_near_targeted_refinement=True,original_sources_modified=False)
dispatch.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch-source','collect-source','launch-endpoints','collect-endpoints']);a=p.parse_args()
    readback=json.loads((ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json').read_text(encoding='utf8'))
    sources={r['clip_id']:r['points'][0]['state_path']for r in readback if r['clip_id']in['T07_C01','T07_C02','T07_C03']}
    result=rpc(P21_OPTIONS,'p25','ACTION='+repr(a.action)+'\nSOURCES='+repr(sources)+'\n'+REMOTE)
    if a.action.startswith('launch'):
        (WORK/('T07_GPU_'+a.action.split('-')[1].upper()+'_DISPATCH.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    elif result['status']=='completed':
        raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t07_gpu_'+result['phase']+'_'+digest[:12]+'.json')
        if not path.exists():path.write_bytes(raw)
        else:assert path.read_bytes()==raw
        (WORK/('T07_GPU_'+result['phase'].upper()+'_RESULT.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
