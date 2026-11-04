"""Replay frozen T18 friction contexts with their original GPU/control setup."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path

from physedit.core100_critical import load
from scripts.t18_table_contact_boundary_worker import table_event
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,importlib.util,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029')
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102');root.mkdir(exist_ok=True)
old_roots=([old]if GROUP=='friction'else[
 Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_c04_legacy_native_v13_20261030'),
 Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_native_overlap_20261029')])
jobs=[];deployments={};bootstraps={};source_hashes={}
for old in old_roots:
 deployment=json.loads((old/'deployment.json').read_text());batch=json.loads((old/'jobs.json').read_text())
 for name,digest in deployment['sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
 for j in batch:
  jobs.append(j);deployments[j['clip_id']]=deployment;bootstraps[j['clip_id']]=old/'native_bootstrap.py'
 source_hashes.update(deployment['sources'])
assert {j['clip_id']for j in jobs}==({t['clip_id']for t in TARGETS})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state(p):
 raw=Path(p).read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 return json.loads(decoded),raw,decoded
def observed(s,native=False):
 frame=copy.deepcopy(s['frames'][154])
 if native:
  assert isinstance(frame.get('original_exterior_contacts'),list)
  frame['contacts']=frame['original_exterior_contacts']
 return table_event(s,frame)
folder=root/('source'if GROUP=='friction'else'overlap_source');folder.mkdir(exist_ok=True);dispatch=folder/'DISPATCH.json'
if ACTION=='collect-source':
 receipt=json.loads(dispatch.read_text());points=[]
 for item in receipt['points']:
  dest=Path(item['folder']);p=dest/'physics.json';proc=Path('/proc',str(item['pid']),'cmdline')
  alive=proc.exists()and str(dest/'config.json').encode()in proc.read_bytes()
  if alive or not p.exists():
   points.append(dict(clip_id=item['clip_id'],status='running'if alive else'failed_without_state',log_tail=(dest/'run.log').read_text(errors='replace')[-1000:]));continue
  t=next(t for t in TARGETS if t['clip_id']==item['clip_id']);original,raw,decoded=state(t['source_state_path'])
  assert t['source_state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(decoded).hexdigest()]
  replay,stored,_=state(p);cfg=json.loads((dest/'config.json').read_text());j=next(j for j in jobs if j['clip_id']==t['clip_id'])
  original_specs={o['name']:o.get('spec',o)for o in original['dynamic_objects']}
  replay_specs={o['name']:o.get('spec',o)for o in replay['dynamic_objects']}
  assert original_specs==replay_specs=={o['name']:o for o in cfg['dynamic_objects']}
  assert replay['scene_overrides']==original['scene_overrides']==cfg['scene_overrides']
  assert cfg['seed']==j['base_config']['seed']and cfg['experiment']==j['base_config']['experiment']
  assert abs(replay['scene_overrides']['dt']*replay['render']['physics_steps_per_render_frame']*150-5)<1e-12
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
  first=observed(original);now=observed(replay,native=True)
  assert first['label']==t['reference_label']
  errors=[math.dist(a['position'],b['position'])for f,g in zip(original['frames'][4:155],replay['frames'][4:155])for a,b in zip(f['objects'],g['objects'])]
  contacts=[c for f in replay['frames'][5:155]for c in f.get('contacts',[])]
  points.append(dict(item,status='completed',source_state_sha256=t['source_state_sha256'],reference_video_sha256=t['reference_video_sha256'],
   state_path=str(p),state_sha256=sha(p),config_sha256=sha(dest/'config.json'),original_specs_solver_seed_and_controller_preserved=True,
   backend=backend,source_measurement=first,measurement=now,source_label_matches=first['label']==now['label'],
   source_maximum_position_difference_m=max(errors),native_peak_penetration_m=max((c.get('penetration_m',0)for c in contacts),default=0),
   original_contact_semantics='Registered original exterior contact list at frame154, not any earlier sinking or later contact.',
   horizon_s=5.,native_release_control=bool(j.get('native_release_control'))))
 print(json.dumps(dict(status='completed'if all(p['status']=='completed'for p in points)else'pending',phase='source',points=points,
  original_sources_modified=False,source_hashes=receipt['source_hashes'])));raise SystemExit
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if dispatch.exists():print(json.dumps(dict(previous_dispatch=json.loads(dispatch.read_text()),duplicate_launched=False)));raise SystemExit
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419';g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
assert int(g.findtext('fb_memory_usage/free').split()[0])>=12000
owned={}
for path in [Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t20_canonical_gpu_20261102/endpoints/DISPATCH.json'),root/'source/DISPATCH.json',root/'overlap_source/DISPATCH.json']:
 if path.exists():
  for item in json.loads(path.read_text())['points']:owned[str(item['pid'])]=str(Path(item['folder'])/'config.json')
for process in g.findall('processes/process_info'):
 if process.findtext('type')=='G':continue
 pid=process.findtext('pid');p=Path('/proc',str(pid),'cmdline')
 assert pid in owned and p.exists()and owned[pid].encode()in p.read_bytes(),'Do not interfere with foreign compute'
points=[]
for t in TARGETS:
 j=next(j for j in jobs if j['clip_id']==t['clip_id']);original,raw,decoded=state(t['source_state_path'])
 deployment=deployments[t['clip_id']]
 assert t['source_state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(decoded).hexdigest()]
 assert {o['name']:o.get('spec',o)for o in original['dynamic_objects']}=={o['name']:o for o in j['base_config']['dynamic_objects']}
 assert original['scene_overrides']==j['base_config']['scene_overrides']
 assert observed(original)['label']==t['reference_label']
 dest=folder/t['clip_id'];dest.mkdir(exist_ok=False);cfg=copy.deepcopy(j['base_config'])
 cfg['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),
  save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
 cfg['annotations'].update(enabled=True,save_path=str(dest/'physics.json'));path=dest/'config.json';path.write_text(json.dumps(cfg,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',
  PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 if j.get('native_release_control'):env.update(CORE100_RELEASE_HOOK=deployment['release_hook'],CORE100_MATERIAL_SEAL_HOOK=deployment['material_hook'])
 command=[deployment['python'],str(bootstraps[t['clip_id']]),deployment['renderer'],'--config',str(path)]
 with(dest/'run.log').open('xb')as log:p=subprocess.Popen(command,cwd=deployment['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 points.append(dict(clip_id=t['clip_id'],theta=t['theta'],pid=p.pid,folder=str(dest),config_sha256=sha(path),native_release_control=bool(j.get('native_release_control'))))
receipt=dict(phase='source',group=GROUP,points=points,gpu_uuid=gpu,source_hashes=source_hashes,original_sources_modified=False,
 scope='Original fixed contexts only; no CPU profile/stiffness edits, no scan across changing book counts or extraction layers.')
dispatch.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch-source','collect-source']);p.add_argument('--group',choices=['friction','overlap'],default='friction');args=p.parse_args()
    registry,_=load();readback=json.loads((ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json').read_text(encoding='utf8'))
    sources={r['clip_id']:r['points'][0]for r in readback}
    targets=[dict(clip_id=r['clip_id'],theta=r['theta'],source_state_sha256=r['source_state_sha256'],source_state_path=sources[r['clip_id']]['state_path'],
        reference_label=r['reference_events']['upper_nonpulled_book_on_table_at_end'],reference_video_sha256=r['reference_video_sha256'])for r in registry['cases']if r['clip_id']in (['T18_C01','T18_C02','T18_C03']if args.group=='friction'else['T18_C04','T18_C05'])]
    result=rpc(P21_OPTIONS,'p25','ACTION='+repr(args.action)+'\nGROUP='+repr(args.group)+'\nTARGETS='+repr(targets)+'\n'+inspect.getsource(table_event)+'\n'+REMOTE)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t18_gpu_'+args.group+'_'+args.action.replace('-','_')+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('T18_GPU_'+('OVERLAP_'if args.group=='overlap'else'')+'SOURCE_'+('DISPATCH'if args.action.startswith('launch')else'RESULT')+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
