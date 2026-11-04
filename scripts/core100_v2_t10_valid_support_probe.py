"""Probe the old fixed-38-degree T10 family's geometrically valid endpoints.

The original nominal [-.05,.28] sweep is not all geometrically valid for this
fixed folder. Both admissible extremes are derived from the original builder's
clearance rules, not chosen to obtain Near. Reconstructed seeds remain explicit.
"""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t10_metadata_probe_20261102')
folder=root/'valid_support_endpoints';folder.mkdir(exist_ok=True)
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists()and str(Path(item['folder'])/'config.json').encode()in p.read_bytes()
known={};paths=list(root.glob('source_seed_*/DISPATCH.json'))+list(folder.glob('*/DISPATCH.json'))
t03=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102')
paths+=[t03/'T03_C01_source/DISPATCH.json']+list((t03/'endpoints').glob('*/DISPATCH.json'))
for p in paths:
 if not p.exists():continue
 d=json.loads(p.read_text());known[str(d['pid'])]=d
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu');live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in known and alive(known[pid]),'Do not interfere with foreign compute';live+=1
free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[];geometry=None
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029/native_bootstrap.py')
renderer=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1/scripts/render_sample.py')
for seed in[0,1]:
 src=root/('source_seed_'+str(seed));d=json.loads((src/'DISPATCH.json').read_text());assert not alive(d)
 comparison=next(p for p in COMPARISONS if p['seed']==seed)
 assert sha(src/'physics.json')==comparison['state_sha256']
 assert comparison['measurement']['label']==comparison['source_measurement']['label']==1
 assert comparison['measurement']['first_tape_pen_contact']==comparison['source_measurement']['first_tape_pen_contact']
 assert comparison['measurement']['first_threshold_frame']==comparison['source_measurement']['first_threshold_frame']
 cfg=json.loads((src/'config.json').read_text());assert cfg['seed']==seed
 objects={o['name']:o for o in cfg['dynamic_objects']};e=cfg['experiment'];design=e['t10_design'];pen=objects['t10_support_pen'];panel=objects['t10_supported_folder']
 lean=math.radians(abs(panel['pose']['euler_xyz'][1]));L,W,T=panel['size'];top=e['support_surface']['top_z'];base_x=design['folder_base_x_m']
 base_clearance=panel['pose']['position'][2]-top-.5*L*math.sin(lean)-.5*T*math.cos(lean)
 radius=pen['radius'];height=pen['height']
 low=base_x+radius+(height-base_clearance-1e-6)/math.tan(lean)
 high=base_x+L*math.cos(lean)-.002-radius
 geometry=dict(nominal_domain=[-.05,.28],geometrically_admissible_support_x=[low,high],
  inset_m=.00001,folder_angle_deg=math.degrees(lean),folder_base_clearance_m=base_clearance,
  rules=['underside_height(support_x-pen_radius)-pen_height >= -1e-6 m','support_x+pen_radius < folder_high_end_x-0.002 m'],
  original_recipe_source=RECIPE_PATH,original_recipe_sha256=RECIPE_SHA)
 for side,theta in[('low',low+.00001),('high',high-.00001)]:
  dest=folder/('seed'+str(seed)+'_'+side);receipt=dest/'DISPATCH.json'
  if receipt.exists():continue
  if live>=8 or free<12000:pending.append(dict(seed=seed,theta=theta));continue
  c=copy.deepcopy(cfg);o={o['name']:o for o in c['dynamic_objects']};meta=c['experiment']['t10_design']
  o['t10_support_pen']['pose']['position'][0]=theta;o['t10_tape_roll']['pose']['position'][0]=theta
  meta['support_x_m']=theta;meta['tape_x_m']=theta;meta['aim_target_world_xy_m'][0]=theta
  for name,offset in [('left',-radius),('center',0),('right',radius)]:
   meta['support_gap_'+name+('_rim_m'if name!='center'else'_m')]=base_clearance+(theta+offset-base_x)*math.tan(lean)-height
  assert meta['support_gap_left_rim_m']>=-1e-6
  assert theta+radius<base_x+L*math.cos(lean)-.002
  c['_core100_intervention']=dict(axis='support_x',theta=theta,legacy_header_preserved=True,original_seed_recovered=False)
  dest.mkdir(exist_ok=True);c['render']['save_video']=str(dest/'unused.mp4');c['annotations']['save_path']=str(dest/'physics.json')
  path=dest/'config.json';path.write_text(json.dumps(c,indent=2))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
   PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
  with(dest/'run.log').open('xb')as log:
   process=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(path)],cwd='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  item=dict(clip_id='T10_C05',seed=seed,theta=theta,side=side,pid=process.pid,folder=str(dest),gpu_uuid=gpu,
   config_sha256=sha(path),source_state_sha256=d['source_state_sha256'],reference_video_sha256=d['reference_video_sha256'],
   source_probe_state_sha256=comparison['state_sha256'],original_seed_recovered=False,formal_admission=False,
   geometry=geometry,normalization_domain_unchanged=[-.05,.28],frozen_inputs_modified=False)
  receipt.write_text(json.dumps(item,indent=2));started.append(item);live+=1;free-=2000
print(json.dumps(dict(started=started,pending=pending,geometry=geometry,all_dispatched=[json.loads(p.read_text())for p in folder.glob('*/DISPATCH.json')],duplicate_launched=False)))
'''


def main():
    path=WORK/'t10_metadata_source_comparison.json';comparisons=json.loads(path.read_text())
    recipe=json.loads((WORK/'t10_original_geometry_recipe.json').read_text())
    source=recipe['scene_t10'];assert 'T10 pen/folder initial penetration'in source and'folder_high_end_x - 0.002'in source
    # Hash the full original builder remotely as well; no recipe is edited.
    code='COMPARISONS='+repr(comparisons)+'\nRECIPE_PATH='+repr(recipe['path'])+'\n'+"from pathlib import Path\nimport hashlib\nRECIPE_SHA=hashlib.sha256(Path(RECIPE_PATH).read_bytes()).hexdigest()\n"+REMOTE
    result=rpc(P21_OPTIONS,'p25',code)
    result['source_comparison_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();out=WORK/('t10_valid_support_dispatch_'+digest[:12]+'.json');out.write_bytes(raw)
    (WORK/'T10_VALID_SUPPORT_DISPATCH.json').write_text(json.dumps(dict(path=out.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(dict(started=[dict(seed=p['seed'],theta=p['theta'],pid=p['pid'])for p in result['started']],pending=result['pending'],geometry=result['geometry'])))


if __name__=='__main__':main()
