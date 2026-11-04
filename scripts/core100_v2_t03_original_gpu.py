"""Replay the original T03 C01 runtime, not the independent GPU64 proxy.

The original production worker points into T01's shared runtime directory.
The similarly named copy under T03 is not its executable dependency tree.
This script only dispatches one original-source numerical replay; no event or
boundary is admitted merely because the job starts.
"""
import argparse
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,json,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
base=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
original=base/'everyday_bifurcation_T03_v5_multilevel_cascade'
runtime=base/'everyday_bifurcation_T01_v2_7s/scripts'
renderer=runtime/'render_t03_v5_multicam_r008.py'
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029/native_bootstrap.py')
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102');root.mkdir(exist_ok=True)
folder=root/'T03_C01_source';folder.mkdir(exist_ok=True)
receipt=folder/'DISPATCH.json'
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists()and str(Path(item['folder'])/'config.json').encode()in p.read_bytes()
if receipt.exists():
 item=json.loads(receipt.read_text());print(json.dumps(dict(previous_dispatch=item,alive=alive(item),state_exists=(folder/'physics.json').exists(),duplicate_launched=False)));raise SystemExit
cfg_path=original/'configs/formal_480p_fullsim_r014'/TARGET['sample_id']/'cam03.json'
assert sha(cfg_path)=='19225096620eb41ab71cdbca7f37a3242cd9d16dd7fccc3ef1054c343891d523'
cfg=json.loads(cfg_path.read_text());raw=Path(TARGET['state_path']).read_bytes()
assert sha(Path(TARGET['state_path']))==TARGET['state_sha256']
source=json.loads(gzip.decompress(raw))
assert {o['name']:o.get('spec',o)for o in source['dynamic_objects']}=={o['name']:o for o in cfg['dynamic_objects']}
assert cfg['scene_overrides']['dt']*cfg['render']['physics_steps_per_render_frame']*150==5.
assert source['experiment']['three_camera_contract']=='one_live_genesis_simulation_three_synchronized_views'
worker=original/'scripts/run_t03_v5_formal_480p_worker.py'
assert 'everyday_bifurcation_T01_v2_7s/scripts/render_t03_v5_multicam_r008.py'in worker.read_text()
assert sha(renderer)=='76bea0d2a7dd30c3c7b15da3a5169c7e5d70a429c6d78090f00401ef769ed31c'
assert sha(bootstrap)=='1a4b48ec891a8518d2f535d4a3af2898b855af3c46c464bec29b0b586f4e18dc'
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
owned={}
t18=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
for p in list((t18/'endpoints').glob('*/DISPATCH.json'))+[t18/'source/DISPATCH.json',t18/'overlap_source/DISPATCH.json']:
 if not p.exists():continue
 d=json.loads(p.read_text())
 for item in d.get('points',[d]):owned[str(item['pid'])]=item
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in owned and alive(owned[pid]),'Foreign GPU compute must remain untouched'
 live+=1
assert live<8 and int(g.findtext('fb_memory_usage/free').split()[0])>=12000
dependencies=[cfg_path,renderer,bootstrap,worker]
dependencies+=list(runtime.glob('*.py'))
source_hashes={str(p):sha(p)for p in dependencies}
cfg['render'].update(write_video=False,render_backend='raster',resolution=[160,96],
 save_video=str(folder/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,
 save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
cfg['annotations'].update(enabled=True,save_path=str(folder/'physics.json'))
path=folder/'config.json';path.write_text(json.dumps(cfg,indent=2))
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
 PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
with(folder/'run.log').open('xb')as log:
 p=subprocess.Popen([python,str(bootstrap),str(renderer),'--config',str(path)],cwd=base,env=env,
  stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
item=dict(clip_id='T03_C01',theta=.1,pid=p.pid,folder=str(folder),gpu_uuid=gpu,
 config_sha256=sha(path),original_config_sha256=sha(cfg_path),source_hashes=source_hashes,
 source_state_path=TARGET['state_path'],source_state_sha256=TARGET['state_sha256'],
 reference_video_sha256=TARGET['video_sha256'],expected_primary_event=0,
 expected_actual_init_seed=cfg['random_seed']&0x7fffffff,
 frozen_inputs_modified=False,boundary_admitted=False,source_replay_only=True)
receipt.write_text(json.dumps(item,indent=2));print(json.dumps(dict(dispatch=item,duplicate_launched=False)))
'''


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    registry,_=load();row=next(r for r in registry['cases']if r['clip_id']=='T03_C01')
    readback=json.loads((ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json').read_text())
    original=next(r for r in readback if r['clip_id']=='T03_C01')['points'][0]
    target=dict(sample_id=row['sample_id'],state_path=original['state_path'],state_sha256=original['stored_state_sha256'],video_sha256=row['reference_video_sha256'])
    result=rpc(P21_OPTIONS,'p25','TARGET='+repr(target)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t03_original_gpu_source_dispatch_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T03_ORIGINAL_GPU_SOURCE_DISPATCH.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    item=result.get('dispatch',result.get('previous_dispatch',{}))
    print(json.dumps(dict(clip_id=item.get('clip_id'),pid=item.get('pid'),folder=item.get('folder'),duplicate_launched=False)))


if __name__=='__main__':main()
