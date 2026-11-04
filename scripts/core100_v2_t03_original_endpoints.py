"""Probe T03 C01's original lower-phone edge axis on its actual GPU runtime.

Source labels/objects/solver agree; late trajectory drift and the unresolved
native depth diagnostic remain explicit. These probes are numerical candidates,
not automatic full-chain physical-quality or RGB admission.
"""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102')
source=root/'T03_C01_source';d=json.loads((source/'DISPATCH.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists()and str(Path(item['folder'])/'config.json').encode()in p.read_bytes()
assert not alive(d)and sha(source/'physics.json')==SOURCE_RESULT['state_sha256']
assert SOURCE_RESULT['source_event_match']and SOURCE_RESULT['objects_match']and not SOURCE_RESULT['physical_solver_differences']
cfg=json.loads((source/'config.json').read_text());assert sha(source/'config.json')==d['config_sha256']
assert cfg['experiment']['parameter']['lower_phone_com_edge_distance_m']==.1
bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029/native_bootstrap.py')
renderer=Path(SOURCE_RESULT['backend']['renderer'])
assert sha(renderer)==SOURCE_RESULT['backend']['renderer_sha256']
assert sha(bootstrap)==SOURCE_RESULT['backend']['instrumentation_sha256']
folder=root/'endpoints';folder.mkdir(exist_ok=True);lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu=d['gpu_uuid'];g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
known={str(d['pid']):d};paths=list(folder.glob('*/DISPATCH.json'))
paths+=list(Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t10_metadata_probe_20261102').glob('source_seed_*/DISPATCH.json'))
t18=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
paths+=list((t18/'endpoints').glob('*/DISPATCH.json'))+[t18/'source/DISPATCH.json',t18/'overlap_source/DISPATCH.json']
for p in paths:
 if not p.exists():continue
 item=json.loads(p.read_text())
 for r in item.get('points',[item]):known[str(r['pid'])]=r
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in known and alive(known[pid]),'Do not interfere with foreign GPU compute';live+=1
free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[]
for theta in[.006,.06866666666666667,.08433333333333333]:
 dest=folder/format(theta,'.12g');receipt=dest/'DISPATCH.json'
 if receipt.exists():continue
 if live>=8 or free<12000:pending.append(theta);continue
 assert .006<=theta<=.1
 c=copy.deepcopy(cfg);e=c['experiment'];p=e['parameter'];geometry=e['geometry_contract'];delta=theta-.1
 phone=next(o for o in c['dynamic_objects']if o['name']=='t03v5_lower_edge_phone')
 rise=delta*math.tan(math.radians(p['lower_transfer_ramp_slope_deg']))
 phone['pose']['position'][0]-=delta;phone['pose']['position'][2]+=rise
 p['lower_phone_com_edge_distance_m']=theta
 geometry['lower_phone_center_m'][0]-=delta;geometry['lower_phone_center_m'][2]+=rise
 geometry['initial_can_phone_horizontal_gap_m']-=delta
 dest.mkdir(exist_ok=True);c['render'].update(save_video=str(dest/'unused.mp4'))
 c['annotations']['save_path']=str(dest/'physics.json');path=dest/'config.json';path.write_text(json.dumps(c,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
  PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 with(dest/'run.log').open('xb')as log:
  process=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(path)],
   cwd='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 item=dict(clip_id='T03_C01',theta=theta,pid=process.pid,folder=str(dest),gpu_uuid=gpu,
  config_sha256=sha(path),original_source_state_sha256=d['source_state_sha256'],source_replay_state_sha256=SOURCE_RESULT['state_sha256'],
  reference_video_sha256=d['reference_video_sha256'],actual_seed=SOURCE_RESULT['backend']['actual_init_seed'],
  source_hashes=d['source_hashes'],formal_admission=False,frozen_inputs_modified=False,
  source_native_depth_diagnostic_unresolved=True,source_late_trajectory_drift_retained=True,
  scope='Original lower-phone edge axis with derived ramp height; independent GPU64 labels not transferred.')
 receipt.write_text(json.dumps(item,indent=2));started.append(item);live+=1;free-=2000
print(json.dumps(dict(started=started,pending=pending,all_dispatched=[json.loads(p.read_text())for p in folder.glob('*/DISPATCH.json')],duplicate_launched=False)))
'''


def main():
    pointer=json.loads((WORK/'T03_ORIGINAL_GPU_SOURCE_RESULT.json').read_text());path=ROOT/pointer['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256'];source=json.loads(path.read_text());assert source['status']=='completed'
    result=rpc(P21_OPTIONS,'p25','SOURCE_RESULT='+repr(source)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t03_original_gpu_endpoints_dispatch_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T03_ORIGINAL_GPU_ENDPOINTS_DISPATCH.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(dict(started=[dict(theta=p['theta'],pid=p['pid'])for p in result['started']],pending=result['pending'],duplicate_launched=False)))


if __name__=='__main__':main()
