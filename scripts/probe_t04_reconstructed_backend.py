"""Replay T04 from original template, using published physics fields verbatim."""
import argparse,gzip,json,subprocess
from pathlib import Path
ROOT=Path('review/scene_family_completion_20261018')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--values',type=float,nargs='+',default=[.105,.14,.1225]);args=parser.parse_args()
    sid='T04F880V1__bg01_home_ase__g01_moon__cf_stack_sliding_star__rep01'
    state=json.loads(gzip.decompress((ROOT/'completion_states/T04'/(sid+'.json.gz')).read_bytes()))
    config=json.loads((ROOT/'t04_reconstructed_probe_config.json').read_text())
    assert config['dynamic_objects']==[o['spec'] for o in state['dynamic_objects']]
    assert config['runtime_forces']==state['runtime_forces']
    config['scene_overrides']=state['scene_overrides']
    config['experiment']=state['experiment']
    code=r'''
import pathlib,json,subprocess,os,hashlib,copy
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t04_completion_probe_long_20261018');root.mkdir(exist_ok=True)
renderer=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/scripts/render_t04_t05_live_multicam.py')
py='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
rows=[]
for value in VALUES:
 folder=root/str(value);folder.mkdir(exist_ok=True)
 if (folder/'physics.json').exists():
  saved=json.loads((folder/'physics.json').read_text())
  if len(saved.get('frames',[]))==210:
   row=dict(theta=value,status='existing_complete',output=str(folder),state_sha256=hashlib.sha256((folder/'physics.json').read_bytes()).hexdigest())
   rows.append(row);print(json.dumps(row),flush=True);continue
 c=copy.deepcopy(CONFIG)
 for o in c['dynamic_objects']:
  if o['name'] in ['t04v3_folder_ramp_pbr','t04v3_stack_book_bottom']:o['friction']=value
 for name in ['ramp_friction_coefficient','bottom_book_friction_coefficient']:c['experiment']['parameter'][name]=value
 c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1)
 for name in ['save_video','save_first_rgb','save_last_rgb']:
  if name in c['render']:c['render'][name]=str(folder/pathlib.Path(c['render'][name]).name)
 c['scene_overrides']['raytracing']=False
 c['annotations']['save_path']=str(folder/'physics.json')
 cp=folder/'config.json';cp.write_text(json.dumps(c))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='2',TI_OFFLINE_CACHE='0')
 env['LD_LIBRARY_PATH']='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 row=dict(theta=value,config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),renderer_sha256=hashlib.sha256(renderer.read_bytes()).hexdigest(),output=str(folder))
 with (folder/'run.log').open('w') as log:
  try:row['returncode']=subprocess.run([py,str(renderer),'--config',str(cp)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200).returncode
  except subprocess.TimeoutExpired:row['error']='timeout'
 if (folder/'physics.json').exists():
  saved=json.loads((folder/'physics.json').read_text());row['frames']=len(saved.get('frames',[]));row['state_sha256']=hashlib.sha256((folder/'physics.json').read_bytes()).hexdigest()
 row['log_tail']=(folder/'run.log').read_text(errors='replace')[-1000:]
 rows.append(row);(root/'status.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
'''
    proc=subprocess.Popen(['ssh','-o','BatchMode=yes','p25','python3 -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    proc.stdin.write(code.replace('CONFIG',repr(config)).replace('VALUES',repr(args.values)).encode());proc.stdin.close()
    rows=[]
    for line in proc.stdout:
        row=json.loads(line);rows.append(row)
        (ROOT/'t04_completion_probe_results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k!='log_tail'}),flush=True)
    proc.wait()
    if proc.returncode:raise RuntimeError('remote T04 probe failed')

if __name__=='__main__':main()
