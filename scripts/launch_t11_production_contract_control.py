"""Replay one failing endpoint with the original three-camera production contract."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t11_production_contract_control_launch_20261020.json'
    if receipt.exists():raise RuntimeError('production control already dispatched')
    job=next(j for j in json.loads((ROOT/'five_scene_prepared_plan_20261020.json').read_text()) if j['scene_id']=='T11' and j['family_id']=='driver_initial_speed_mps')
    endpoint=job['endpoints'][1]
    source=next(s for s in json.loads((ROOT/'t11_published_final_states.json').read_text()) if s['sample_id']==endpoint['sample_id'])
    root='/data_cached/wangzijun_p25/liyuhan/t11_original_production_control_20261020'
    pipeline=r'''
import json,pathlib,subprocess,time,copy,hashlib,gzip,os
r=pathlib.Path(ROOT_DIRECTORY);r.mkdir(exist_ok=True,parents=True);endpoint=ENDPOINT;source=SOURCE;renderer=RENDERER
original=pathlib.Path(source['source_state']).parent.parent
paths=[];provenance=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for camera in ['cam01','cam02','cam03']:
 p=original/'configs'/(camera+'.json');raw=p.read_bytes();c=json.loads(raw)
 if camera=='cam01' and c!=endpoint['config']:raise ValueError('original production config differs from selected published config')
 for key in ['save_video','save_first_rgb','save_last_rgb']:
  if c['render'].get(key):c['render'][key]=str(r/camera/pathlib.Path(c['render'][key]).name)
 d=r/camera;d.mkdir(exist_ok=True);c['annotations']['save_path']=str(d/'physics.json')
 dest=d/'config.json';dest.write_text(json.dumps(c));paths.append(dest);provenance.append(dict(camera=camera,source_config=str(p),source_sha256=hashlib.sha256(raw).hexdigest(),replay_config_sha256=sha(dest)))
(r/'source_contract.json').write_text(json.dumps(dict(configs=provenance,renderer=renderer,renderer_sha256=sha(pathlib.Path(renderer)),profile='original three 1280x720 raytracing cameras, original seed/timing/physics and producer thread settings'),indent=2))
while float(subprocess.check_output(['nvidia-smi','-i','1','--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<18*1024:
 (r/'status.json').write_text(json.dumps(dict(status='waiting_for_18GiB_memory')));time.sleep(20)
cache=r/'cache';cache.mkdir(exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='1',PYTHONUNBUFFERED='1',XDG_CACHE_HOME=str(cache),TMPDIR=str(cache),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='2')
lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
cmd=['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',renderer,'--strict-live-physics','--config',str(paths[0])]
for p in paths[1:]:cmd+=['--extra-camera-config',str(p)]
(r/'status.json').write_text(json.dumps(dict(status='running_original_three_camera_contract')))
with (r/'render.log').open('w') as log:result=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=5400)
if result.returncode:raise RuntimeError('original producer renderer failed; inspect render.log')
actors=['t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case'];sp=r/'cam01/physics.json';data=json.loads(sp.read_text());raw=pathlib.Path(source['source_state']).read_bytes();original_state=json.loads(gzip.decompress(raw))
if hashlib.sha256(raw).hexdigest()!=endpoint['state_sha256']:raise ValueError('original state identity changed')
name=TARGET[:-len('_final_center_below_minus_20cm')]
position=next(o['position'] for o in data['frames'][-1]['objects'] if o['name']==name);label=int(position[2]<-.20)
def positions(frame):return {o['name']:o['position'] for o in frame['objects'] if o['name'] in actors}
import math
errors=[max(math.dist(positions(a)[n],positions(b)[n]) for n in actors) for a,b in zip(original_state['frames'],data['frames'])]
summary=dict(status='completed_production_contract_control',sample_id=endpoint['sample_id'],expected_label=endpoint['label'],actual_label=label,label_matches=label==endpoint['label'],max_position_difference_m=max(errors),reference_state_sha256=endpoint['state_sha256'],generated_state_sha256=sha(sp),diagnostic_only=True)
(r/'status.json').write_text(json.dumps(summary,indent=2))
'''.replace('ROOT_DIRECTORY',repr(root)).replace('ENDPOINT',repr(endpoint)).replace('SOURCE',repr(source)).replace('RENDERER',repr(job['renderer'])).replace('TARGET',repr(job['target_event']))
    compile(pipeline,'production_control.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+");r.mkdir(exist_ok=True,parents=True)\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    result=dict(host='p25',root=root,gpu=1,diagnostic_only=True,sample_id=endpoint['sample_id'],**json.loads(p.stdout))
    receipt.write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
