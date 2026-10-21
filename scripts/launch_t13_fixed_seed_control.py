"""Two prespecified fixed-seed repetitions of the known variable T13 bracket."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t13_fixed_seed_control_launch_20261021.json'
    if receipt.exists():raise RuntimeError('fixed-seed control already launched')
    job=next(j for j in json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()) if j['job_id']=='6dbcdc1d510be4b0f1312e47')
    local=ROOT/'t13_fixed_seed_control_input_20261021.json';local.write_text(json.dumps(job))
    directory='/data_cached/wangzijun_p25/liyuhan/t13_fixed_seed_control_20261021'
    subprocess.run(['ssh','p25','mkdir','-p',directory],check=True)
    for path,name in [(local,'job.json'),(Path('scripts/genesis_seed_bootstrap.py'),'genesis_seed_bootstrap.py'),(Path('scripts/t13_current_boundary_worker.py'),'measurement.py')]:subprocess.run(['scp','-q',str(path.resolve()),'p25:'+directory+'/'+name],check=True)
    pipeline=r'''
import pathlib,json,subprocess,os,time,hashlib,importlib.util,re,copy
r=pathlib.Path(DIRECTORY);job=json.loads((r/'job.json').read_text());seed=0;repetitions=2;gpu='0'
py='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python';base=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer');renderer=base/'scripts/12_render_motion_sequence_t13_realasset_v6_sync3cam.py';bootstrap=r/'genesis_seed_bootstrap.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('measurement',r/'measurement.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
contract=dict(seed=seed,seed_origin='new prespecified supplementary control; original init seed=None',repetitions=repetitions,job_id=job['job_id'],source_state_sha256=[e['state_sha256'] for e in job['endpoints']],backend_sources={str(p):sha(p) for p in [renderer,base/'scripts/06_run_genesis_import.py',bootstrap,r/'measurement.py']},diagnostic_only=True)
(r/'source_contract.json').write_text(json.dumps(contract,indent=2));rows=[]
for repeat in range(repetitions):
 for endpoint,theta in zip(job['endpoints'],job['bracket']):
  while float(subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<18*1024:
   (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',gpu=gpu)));time.sleep(20)
  d=r/('repeat_'+str(repeat))/format(theta,'.12g');d.mkdir(parents=True,exist_ok=True);c=copy.deepcopy(endpoint['config'])
  for render in [c['render']]+c['render'].get('camera_outputs',[]):
   for k in ['save_video','save_first_rgb','save_last_rgb']:
    if render.get(k):render[k]=str(d/pathlib.Path(render[k]).name)
  c['annotations']['save_path']=str(d/'physics.json');cp=d/'config.json';cp.write_text(json.dumps(c))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,TI_OFFLINE_CACHE='0');lib=py.rsplit('/bin/python',1)[0]+'/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
  (r/'resource_status.json').write_text(json.dumps(dict(status='running_fixed_seed_control',repeat=repeat,theta=theta,seed=seed,gpu=gpu)))
  with (d/'run.log').open('w') as log:run=subprocess.run([py,str(bootstrap),'--seed',str(seed),str(renderer),'--config',str(cp)],cwd=base,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  if run.returncode:raise RuntimeError('seed control renderer failed; '+str(d/'run.log'))
  text=re.sub(r'\x1b\[[0-9;]*m','',(d/'run.log').read_text(errors='replace'))
  if not re.search(r'seed:\s*0\b',text):raise ValueError('actual Genesis seed not confirmed in runtime log')
  state=json.loads((d/'physics.json').read_text());events,tracks=m.metrics(state)
  row=dict(repeat=repeat,theta=theta,seed=seed,actual_genesis_seed_verified=True,events=events,reference_label=endpoint['label'],label_matches=events[job['target_event']]==endpoint['label'],config_sha256=sha(cp),state_sha256=sha(d/'physics.json'),source_state_sha256=endpoint['state_sha256'])
  rows.append(row);(r/'status.json').write_text(json.dumps(rows,indent=2))
comparison=dict(status='completed_fixed_seed_control',seed=seed,points=len(rows),all_original_labels_reproduced=all(x['label_matches'] for x in rows),repeat_labels_agree=all(rows[i]['events']==rows[i+2]['events'] for i in range(2)),diagnostic_only=True)
(r/'comparison.json').write_text(json.dumps(comparison,indent=2));(r/'resource_status.json').write_text(json.dumps(dict(status='completed',gpu=gpu)))
'''.replace('DIRECTORY',repr(directory))
    compile(pipeline,'fixed_seed_control.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(directory)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    result=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=directory,gpu=0,job_id=job['job_id'],seed=0,repetitions=2,planned_endpoint_runs=4,diagnostic_only=True,**json.loads(result.stdout))
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
