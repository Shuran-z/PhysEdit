"""Run two unchanged formal A endpoints with the original renderer/physics backend."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def main():
 configs=json.loads((OUT/'p26_configs.json').read_text(encoding='utf-8'))
 identities={r['sample_id']:r for r in json.loads(Path('review/original_search_tasks_20261018/t14_source_identity.json').read_text(encoding='utf-8'))}
 selected=[]
 for branch in ['A_wedged_r01','A_passed_r01']:
  r=next(r for r in configs if all(s in r['path'] for s in ['T14','/formal_r006/','bg03_neutral_studio','g03_earth',branch]))
  assert r['sha256']==identities[r['config']['sample_id']]['config_sha256']
  selected.append(r)
 sources=json.loads(Path('review/original_search_tasks_20261018/p26_records.json').read_text(encoding='utf-8'))
 analyzer=next(r for r in sources if r['path'].endswith('analyze_t14_v2.py'))
 renderer=next(r for r in json.loads(Path('review/original_search_tasks_20261018/p25_records.json').read_text(encoding='utf-8')) if r['path'].endswith('render_t01_t05_production_v3_multicam.py'))
 remote=r'''
import json,pathlib,hashlib,subprocess,os,copy
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t14_formal_boundary_probe_20261018');root.mkdir(exist_ok=False)
analyzer=root/'analyze_t14_v2.py';analyzer.write_text(ANALYZER['text'])
renderer=pathlib.Path(RENDERER['path'])
assert hashlib.sha256(renderer.read_bytes()).hexdigest()==RENDERER['sha256']
assert hashlib.sha256(analyzer.read_bytes()).hexdigest()==ANALYZER['sha256']
py='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python';results=[]
for i,r in enumerate(CONFIGS):
 c=copy.deepcopy(r['config']);folder=root/str(i);folder.mkdir();render=c['render']
 for key in ['save_video','save_first_rgb','save_last_rgb']:
  if key in render:render[key]=str(folder/pathlib.Path(render[key]).name)
 render.update(resolution=[160,96],raytracing_spp=1,write_video=False,render_backend='raster')
 c['scene_overrides']['raytracing']=False
 c['annotations']['save_path']=str(folder/'physics.json')
 cp=folder/'config.json';cp.write_text(json.dumps(c));op=folder/'outcome.json'
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='2',TI_OFFLINE_CACHE='0')
 env['LD_LIBRARY_PATH']='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 row=dict(original_path=r['path'],original_sha256=r['sha256'],config_path=str(cp),renderer_sha256=RENDERER['sha256'],analyzer_sha256=ANALYZER['sha256'],render_only_changes=True)
 with (folder/'run.log').open('w') as log:
  try:
   p=subprocess.run([py,str(renderer),'--config',str(cp)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150);row['returncode']=p.returncode
   if p.returncode==0:
    p=subprocess.run([py,str(analyzer),str(folder/'physics.json'),'--config',str(cp),'--output',str(op)],stdout=log,stderr=subprocess.STDOUT,timeout=30);row['analyzer_returncode']=p.returncode
  except subprocess.TimeoutExpired:row['error']='bounded original renderer probe timeout'
 if op.exists():row['outcome']=json.loads(op.read_text())
 row['log_tail']=(folder/'run.log').read_text(errors='replace')[-1800:];results.append(row)
 (root/'status.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
'''
 remote=remote.replace('ANALYZER',repr(analyzer)).replace('RENDERER',repr(renderer)).replace('CONFIGS',repr(selected))
 p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=remote.encode(),capture_output=True,timeout=380)
 (OUT/'t14_formal_backend_probe.stderr').write_bytes(p.stderr);p.check_returncode();result=json.loads(p.stdout)
 (OUT/'t14_formal_backend_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps([dict(returncode=r.get('returncode'),error=r.get('error'),outcome=r.get('outcome',{}).get('observed_outcome')) for r in result]))
if __name__=='__main__':main()
