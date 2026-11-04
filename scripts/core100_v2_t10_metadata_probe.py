"""Test an explicitly reconstructed old T10 source with two declared seeds.

The original seed/config is not claimed recovered. Original executed objects,
solver, controls and timing come from the released native metadata, while a
later same-ID configuration supplies I/O scaffolding only. No boundary or RGB
admission follows from dispatch; full source readback must establish equivalence.
"""
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
base=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
project=base/'everyday_bifurcation_72k_T06_T10_v1'
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t10_metadata_probe_20261102');root.mkdir(exist_ok=True)
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists()and str(Path(item['folder'])/'config.json').encode()in p.read_bytes()
source_path=Path(TARGET['state_path']);raw=source_path.read_bytes();assert sha(source_path)==TARGET['stored_sha256']
s=json.loads(raw);assert sha(source_path)==TARGET['decoded_sha256']
objects={o['name']:o.get('spec',o)for o in s['dynamic_objects']}
assert objects['t10_support_pen']['pose']['position'][0]==.2171429
assert math.dist(objects['t10_tape_roll']['motion']['initial_velocity'],[0,0,0])==3.
assert abs(objects['t10_supported_folder']['pose']['euler_xyz'][1])==38.
assert s['experiment']['actuator']=='initial_rolling_velocity_true_lateral_side_strike'
template=project/'configs/production'/('PROD_T10_bg01_home_ase_g03_earth_supx_p17__cam01')/'cam01.json'
cfg=json.loads(template.read_text());renderer=project/'scripts/render_sample.py'
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029/native_bootstrap.py')
assert sha(bootstrap)=='1a4b48ec891a8518d2f535d4a3af2898b855af3c46c464bec29b0b586f4e18dc'
assert sha(renderer)=='89189629b1924b8beba41ace57f3ec18bade43e3b2685e17a4779c4437bd2256'
# Reconstruct already executed physical inputs, not the later same-ID inputs.
cfg['manifest']=s['manifest'];cfg['dynamic_objects']=list(objects.values());cfg['scene_overrides']=copy.deepcopy(s['scene_overrides'])
cfg['experiment']=copy.deepcopy(s['experiment']);cfg['runtime_forces']=[]
cfg.pop('background_profile_path',None)  # native solver/manifest already include it
cfg['render']=copy.deepcopy(s['render'])
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
known={}
t18=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
paths=list((t18/'endpoints').glob('*/DISPATCH.json'))+[t18/'source/DISPATCH.json',t18/'overlap_source/DISPATCH.json',Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102/T03_C01_source/DISPATCH.json')]+list(root.glob('source_seed_*/DISPATCH.json'))
for p in paths:
 if not p.exists():continue
 d=json.loads(p.read_text())
 for item in d.get('points',[d]):known[str(item['pid'])]=item
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in known and alive(known[pid]),'Do not interfere with foreign GPU compute'
 live+=1
free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[]
dependencies=[source_path,template,bootstrap,renderer,project/'scripts/render_t06_t10_physics_v2.py']
source_hashes={str(p):sha(p)for p in dependencies}
for seed in[0,1]:
 dest=root/('source_seed_'+str(seed));receipt=dest/'DISPATCH.json'
 if receipt.exists():continue
 if live>=8 or free<12000:pending.append(seed);continue
 dest.mkdir(exist_ok=True);c=copy.deepcopy(cfg);c['seed']=seed
 c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],
  save_video=str(dest/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
 c['annotations']=dict(enabled=True,save_path=str(dest/'physics.json'))
 c['_core100_reconstruction']=dict(original_seed_recovered=False,test_seed=seed,scope='Metadata source-equivalence probe only; no original seed or boundary claim.')
 path=dest/'config.json';path.write_text(json.dumps(c,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
  PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 with(dest/'run.log').open('xb')as log:
  p=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(path)],
   cwd=base,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 item=dict(clip_id='T10_C05',seed=seed,pid=p.pid,folder=str(dest),gpu_uuid=gpu,config_sha256=sha(path),
  source_state_path=str(source_path),source_state_sha256=TARGET['decoded_sha256'],reference_video_sha256=TARGET['video_sha256'],
  source_hashes=source_hashes,original_seed_recovered=False,original_config_recovered=False,
  physical_inputs_origin='Original executed native specs/solver/control and timing; same-ID later config is I/O scaffolding only.',
  formal_admission=False,frozen_inputs_modified=False)
 receipt.write_text(json.dumps(item,indent=2));started.append(item);live+=1;free-=2000
print(json.dumps(dict(started=started,pending_seeds=pending,all_dispatched=[json.loads(p.read_text())for p in root.glob('source_seed_*/DISPATCH.json')],duplicate_launched=False)))
'''


def main():
    data,_=load();row=next(r for r in data['cases']if r['clip_id']=='T10_C05')
    pointer=json.loads((WORK/'T10_C05_EXECUTED_VERSION.json').read_text());version=json.loads((ROOT/pointer['path']).read_text())
    context=version['source_physical_context']
    target=dict(state_path=context['state_path'],stored_sha256=context['state_stored_sha256'],decoded_sha256=context['state_decoded_sha256'],video_sha256=row['reference_video_sha256'])
    result=rpc(P21_OPTIONS,'p25','TARGET='+repr(target)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t10_metadata_source_dispatch_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T10_METADATA_SOURCE_DISPATCH.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(dict(started=[dict(seed=p['seed'],pid=p['pid'],folder=p['folder'])for p in result['started']],pending=result['pending_seeds'],original_seed_recovered=False)))


if __name__=='__main__':main()
