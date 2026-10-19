"""Replay each original scan axis endpoints with original seed-aware production backend."""
import collections,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def main():
 groups=collections.defaultdict(list)
 for file in OUT.glob('published_batch_*.json'):
  for r in json.loads(file.read_text(encoding='utf-8')):
   if r['scene_id'] not in ['T06','T09','T10'] or 'bg01_home_ase_g03_earth' not in r['sample_id']:continue
   param=r['config']['experiment']['parameter'];groups[(r['scene_id'],param['parameter_name'])].append(r)
 selected=[]
 for group,rows in sorted(groups.items()):
  rows.sort(key=lambda r:r['config']['experiment']['parameter']['parameter_value'])
  selected.extend([rows[0],rows[-1]])
 assert len(selected)==12
 (OUT/'t06_t09_t10_probe_plan.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
 code=r'''
import pathlib,json,os,subprocess,copy,hashlib,time
project=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
root=project/'configs/supplemental_original_axes_raster_20261018';root.mkdir(exist_ok=False)
output=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t06_t09_t10_original_axes_raster_20261018');output.mkdir(exist_ok=False)
py='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python';renderer=project/'scripts/render_sample.py'
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [renderer,project/'scripts/render_t06_t10_physics_v2.py',project/'scripts/render_base_physical_v5.py']}
results=[]
for i,row in enumerate(ROWS):
 c=copy.deepcopy(row['config']);folder=output/row['sample_id'];folder.mkdir();render=c['render']
 for k in ['save_video','save_first_rgb','save_last_rgb']:
  if k in render:render[k]=str(folder/pathlib.Path(render[k]).name)
 render['resolution']=[320,192];render['raytracing_spp']=1;render['render_backend']='raster'
 c['scene_overrides']['raytracing']=False
 c['annotations']['save_path']=str(folder/'physics.json')
 cp=root/(row['sample_id']+'.json');cp.write_text(json.dumps(c))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='2',TI_OFFLINE_CACHE='0')
 result=dict(sample_id=row['sample_id'],scene_id=row['scene_id'],parameter=c['experiment']['parameter'],source_sha256=row['sha256'],source_revision=row['revision'],original_seed=c.get('seed'),config_path=str(cp),output=str(folder),backend_sources=sources)
 with (folder/'run.log').open('w') as log:
  try:p=subprocess.run([py,str(renderer),'--config',str(cp)],cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180);result['returncode']=p.returncode
  except subprocess.TimeoutExpired:result['error']='original_backend_timeout'
 state=folder/'physics.json'
 if state.exists():
  s=json.loads(state.read_text());result['state_sha256']=hashlib.sha256(state.read_bytes()).hexdigest();result['frame_count']=len(s.get('frames',[]));result['top_level_keys']=list(s.keys())
 result['log_tail']=(folder/'run.log').read_text(errors='replace')[-1200:];results.append(result)
 (output/'status.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(dict(done=len(results),sample_id=result['sample_id'],returncode=result.get('returncode'),error=result.get('error'))),flush=True)
print('FINAL_JSON:'+json.dumps(results))
'''
 p=subprocess.Popen(['ssh','-o','BatchMode=yes','p25','python3 -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 p.stdin.write(code.replace('ROWS',repr(selected)).encode());p.stdin.close()
 for line in p.stdout:
  if line.startswith(b'FINAL_JSON:'):(OUT/'t06_t09_t10_probe_results.json').write_bytes(line[len(b'FINAL_JSON:'):])
  else:print(line.decode(errors='replace').strip(),flush=True)
 p.wait();(OUT/'t06_t09_t10_probe_stderr.txt').write_bytes(p.stderr.read())
 if p.returncode:raise RuntimeError('remote probe failed: '+str(p.returncode))
if __name__=='__main__':main()
