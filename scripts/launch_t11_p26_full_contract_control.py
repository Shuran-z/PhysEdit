"""One original three-camera control on its recorded p26 production GPU."""
import json
import argparse
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--replicate',type=int,choices=[1,2],default=1);args=parser.parse_args()
    suffix='' if args.replicate==1 else '_repeat2'
    receipt=ROOT/('t11_p26_full_contract_control'+suffix+'_launch_20261021.json')
    if receipt.exists():raise RuntimeError('full producer control already launched')
    job=json.loads((ROOT/'t11_verified_p26_producer_plan_20261020.json').read_text())[0]
    endpoint=job['endpoints'][0];production=job['production_completion_receipts'][0]
    if production['production_host']!='p26':raise ValueError('producer not verified')
    gpu=int(production['worker'].split('_gpu')[1].split('_')[0])
    directory='/21231_data1/liyuhan_t11_genesis_20261016/p26_full_contract_control_20261021'+suffix
    pipeline=r'''
import pathlib,json,subprocess,hashlib,copy,os,time,gzip,math
r=pathlib.Path(DIRECTORY);r.mkdir(parents=True,exist_ok=True);endpoint=ENDPOINT;production=PRODUCTION;gpu=GPU
source=pathlib.Path(production['source_state']).parent.parent;importer=pathlib.Path('/21231_data1/liyuhan_t11_genesis_20261016/importer');renderer=importer/'scripts/render_t11_r010_slow_chain.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sha(pathlib.Path(production['completion_receipt']))!=production['completion_sha256']:raise ValueError('completion provenance changed')
configs=[];records=[]
for camera in ['cam01','cam02','cam03']:
 p=source/'configs'/(camera+'.json');c=json.loads(p.read_text())
 if camera=='cam01' and c!=endpoint['config']:raise ValueError('selected endpoint differs from original producer config')
 d=r/camera;d.mkdir(exist_ok=True)
 for key in ['save_video','save_first_rgb','save_last_rgb']:
  if c['render'].get(key):c['render'][key]=str(d/pathlib.Path(c['render'][key]).name)
 c['annotations']['save_path']=str(d/'physics.json');cp=d/'config.json';cp.write_text(json.dumps(c));configs.append(cp);records.append(dict(camera=camera,source_config=str(p),source_sha256=sha(p),replay_config_sha256=sha(cp)))
(r/'source_contract.json').write_text(json.dumps(dict(production=production,original_gpu=gpu,configs=records,renderer_sha256=sha(renderer),scope='original three-camera resolution, renderer, seed and physics; isolated output paths only'),indent=2))
while float(subprocess.check_output(['nvidia-smi','-i',str(gpu),'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<12*1024:
 (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',gpu=gpu)));time.sleep(20)
e='/home/wangzijun_p25/miniconda3/envs/genesis';cache=r/'cache';cache.mkdir(exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYTHONUNBUFFERED='1',T11_FFMPEG_WRITER='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',XDG_CACHE_HOME=str(cache),TMPDIR=str(cache),PYTHONPATH=str(importer)+':'+str(importer/'scripts'),PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json')
env['LD_LIBRARY_PATH']=e+'/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib';env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
command=[e+'/bin/python',str(renderer),'--strict-live-physics','--config',str(configs[0])]
for p in configs[1:]:command+=['--extra-camera-config',str(p)]
(r/'resource_status.json').write_text(json.dumps(dict(status='running_full_producer_control',gpu=gpu)))
with (r/'render.log').open('w') as log:result=subprocess.run(command,cwd=importer,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=5400)
if result.returncode:raise RuntimeError('full producer control failed; inspect render.log')
sp=r/'cam01/physics.json';state=json.loads(sp.read_text())
if len(state['frames'])!=210 or any(not math.isfinite(v) for f in state['frames'] for o in f['objects'] for v in o['position']):raise ValueError('incomplete/nonfinite producer control state')
name=TARGET[:-len('_final_center_below_minus_20cm')];z=next(o['position'][2] for o in state['frames'][-1]['objects'] if o['name']==name)
out=dict(status='completed_full_producer_control',sample_id=endpoint['sample_id'],gpu=gpu,expected_label=endpoint['label'],actual_label=int(z<-.2),label_matches=int(z<-.2)==endpoint['label'],final_z_m=z,state_sha256=sha(sp),source_state_sha256=endpoint['state_sha256'],diagnostic_only=True)
(r/'status.json').write_text(json.dumps(out,indent=2));(r/'resource_status.json').write_text(json.dumps(dict(status='completed',gpu=gpu)))
'''.replace('DIRECTORY',repr(directory)).replace('ENDPOINT',repr(endpoint)).replace('PRODUCTION',repr(production)).replace('GPU',str(gpu)).replace('TARGET',repr(job['target_event']))
    compile(pipeline,'full_contract.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(directory)+");r.mkdir(parents=True,exist_ok=True)\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    result=subprocess.run(['ssh','p26','python3 -'],input=code.encode(),capture_output=True,timeout=45)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    launch=dict(host='p26',root=directory,gpu=gpu,replicate=args.replicate,sample_id=endpoint['sample_id'],diagnostic_only=True,**json.loads(result.stdout));receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
