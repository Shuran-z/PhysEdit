"""Bounded original-profile T18 endpoints, after each frozen source replay.

The old CPU results only select probes. They never supply GPU labels. Each
endpoint has its own dispatch receipt so a later invocation can resume missing
work without duplicating a live or completed process.
"""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path

from physedit.core100_critical import load
from scripts.t18_table_contact_boundary_worker import table_event
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,importlib.util,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
KNOWN_COMPLETED=[]
if KNOWN_RESULT_PATH:
 cached_report=json.loads(Path(KNOWN_RESULT_PATH).read_text())
 assert hashlib.sha256(json.dumps(cached_report,sort_keys=True).encode()).hexdigest()==KNOWN_RESULT_CANONICAL_SHA256
 KNOWN_COMPLETED=[p for p in cached_report.get('points',[])if p.get('status')=='completed']
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
folder=root/'endpoints';folder.mkdir(exist_ok=True)
old_roots={c:Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029')for c in['T18_C01','T18_C02','T18_C03']}
old_roots.update(T18_C04=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_c04_legacy_native_v13_20261030'),T18_C05=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_native_overlap_20261029'))
values={'T18_C01':[.08,.12,.8,0.,.04,2.,5.],'T18_C02':[.25,.08,.8,.1,.35,0.,.01],'T18_C03':[.08,.8,.2,.35,.65,.01,.04],
 'T18_C04':[.1947952586206897,.19523706896551726,.235],'T18_C05':[.15]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state(p):
 raw=Path(p).read_bytes();return json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw)
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists()and str(Path(item['folder'])/'config.json').encode()in p.read_bytes()
def observed(s,native=False):
 assert len(s['frames'])==210
 frame=copy.deepcopy(s['frames'][154])
 if native:frame['contacts']=frame['original_exterior_contacts']
 return table_event(s,frame)
def original(cid):
 old=old_roots[cid];dep=json.loads((old/'deployment.json').read_text())
 for name,digest in dep['sources'].items():assert sha(Path(name))==digest
 job=next(j for j in json.loads((old/'jobs.json').read_text())if j['clip_id']==cid)
 spec=importlib.util.spec_from_file_location('original_'+cid,old/'worker.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return old,dep,job,module
def source_item(cid):
 d=root/('source'if cid in['T18_C01','T18_C02','T18_C03']else'overlap_source')/'DISPATCH.json'
 return next(i for i in json.loads(d.read_text())['points']if i['clip_id']==cid)
if ACTION=='collect':
 points=[];source_cache={};replay_cache={}
 for receipt in sorted(folder.glob('*/DISPATCH.json')):
  item=json.loads(receipt.read_text());dest=Path(item['folder']);p=dest/'physics.json'
  if alive(item)or not p.exists():
   points.append(dict(item,status='running'if alive(item)else'failed_without_state',log_tail=(dest/'run.log').read_text(errors='replace')[-500:]));continue
  cached=next((r for r in KNOWN_COMPLETED if r['folder']==item['folder']),None)
  if cached and cached['config_sha256']==item['config_sha256']and cached['state_sha256']==sha(p):
   target=next(t for t in TARGETS if t['clip_id']==item['clip_id'])
   assert cached['source_state_sha256']==target['source_state_sha256']and cached['reference_video_sha256']==target['reference_video_sha256']
   assert sha(dest/'config.json')==cached['config_sha256']and cached['actual_original_objects_axis_seed_solver_controller_and_clock_verified']
   points.append(cached);continue
  t=next(t for t in TARGETS if t['clip_id']==item['clip_id']);old,dep,j,module=original(t['clip_id'])
  cfg=module.intervention(j,item['theta']);result=state(p);specs={o['name']:o.get('spec',o)for o in result['dynamic_objects']}
  assert specs=={o['name']:o for o in cfg['dynamic_objects']}
  cid=t['clip_id']
  if cid not in source_cache:
   source=state(t['source_state_path'])
   source_cache[cid]=(source['scene_overrides'],observed(source));del source
  assert result['scene_overrides']==source_cache[cid][0]==cfg['scene_overrides']
  actual_cfg=json.loads((dest/'config.json').read_text());assert actual_cfg['seed']==j['base_config']['seed']
  assert abs(result['scene_overrides']['dt']*result['render']['physics_steps_per_render_frame']*150-5)<1e-12
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
  assert backend['actual_init_seed']==j['base_config']['seed']%(2**31-1)
  src=source_item(t['clip_id']);assert not alive(src)
  if cid not in replay_cache:
   replay=state(Path(src['folder'])/'physics.json');replay_cache[cid]=observed(replay,True);del replay
  peak=max((dict(c,frame=f['frame_index'])for f in result['frames'][5:155]for c in f.get('contacts',[])),key=lambda c:c.get('penetration_m',0),default={})
  points.append(dict(item,status='completed',state_path=str(p),state_sha256=sha(p),
   source_state_sha256=t['source_state_sha256'],reference_video_sha256=t['reference_video_sha256'],
   actual_original_objects_axis_seed_solver_controller_and_clock_verified=True,
   measurement=observed(result,True),source_measurement=source_cache[cid][1],
   source_replay_measurement=replay_cache[cid],
   native_peak_penetration_m=peak.get('penetration_m',0),peak_native_contact=peak,backend=backend,horizon_s=5.,
   formal_admission=False,source_hashes=dep['sources']))
  del result
 print(json.dumps(dict(points=points,status='completed'if points and all(p['status']=='completed'for p in points)else'pending',
  frozen_inputs_modified=False,normalization_domains_unchanged=True)));raise SystemExit
lock=(folder/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
owned={}
paths=[root/'source/DISPATCH.json',root/'overlap_source/DISPATCH.json']+list(folder.glob('*/DISPATCH.json'))
t20=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t20_canonical_gpu_20261102')
paths+=[t20/'endpoints/DISPATCH.json',t20/'gap_extension/DISPATCH.json']
paths+=[Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_original_gpu_20261102/T03_C01_source/DISPATCH.json')]
paths+=list(Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_legacy_exact_probes_20261102').glob('*/DISPATCH.json'))
for path in paths:
 if not path.exists():continue
 r=json.loads(path.read_text())
 for item in r.get('points',[r]):owned[str(item['pid'])]=item
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in owned and alive(owned[pid]),'Do not interfere with foreign compute'
 live+=1
slots=max(0,8-live);free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[]
for t in sorted(TARGETS,key=lambda t:['T18_C05','T18_C04','T18_C01','T18_C02','T18_C03'].index(t['clip_id'])):
 cid=t['clip_id'];src=source_item(cid)
 if alive(src)or not(Path(src['folder'])/'physics.json').exists():pending.append(dict(clip_id=cid,reason='source_replay_not_terminal'));continue
 source=state(t['source_state_path']);raw=Path(t['source_state_path']).read_bytes()
 assert t['source_state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw).hexdigest()]
 assert observed(source)['label']==t['reference_label']
 replay=state(Path(src['folder'])/'physics.json')
 if observed(replay,True)['label']!=t['reference_label']:pending.append(dict(clip_id=cid,reason='source_event_not_reproduced'));continue
 old,dep,j,module=original(cid)
 assert source['scene_overrides']==j['base_config']['scene_overrides']
 assert {o['name']:o.get('spec',o)for o in source['dynamic_objects']}=={o['name']:o for o in j['base_config']['dynamic_objects']}
 for theta in values[cid]:
  dest=folder/(cid+'_'+format(theta,'.12g'));receipt=dest/'DISPATCH.json'
  if receipt.exists():continue
  if slots<=0 or free<12000:pending.append(dict(clip_id=cid,theta=theta,reason='bounded_gpu_slots_or_memory'));continue
  assert j['domain'][0]<=theta<=j['domain'][1]or(cid in['T18_C01','T18_C02','T18_C03']and 0.<=theta<j['domain'][0])or(cid=='T18_C01'and theta in[2.,5.])
  cfg=module.intervention(j,theta);assert cfg['scene_overrides']==j['base_config']['scene_overrides']
  dest.mkdir(exist_ok=False)
  cfg['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  cfg['annotations'].update(enabled=True,save_path=str(dest/'physics.json'));path=dest/'config.json';path.write_text(json.dumps(cfg,indent=2))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
  if j.get('native_release_control'):env.update(CORE100_RELEASE_HOOK=dep['release_hook'],CORE100_MATERIAL_SEAL_HOOK=dep['material_hook'])
  cmd=[dep['python'],str(old/'native_bootstrap.py'),dep['renderer'],'--config',str(path)]
  with(dest/'run.log').open('xb')as log:p=subprocess.Popen(cmd,cwd=dep['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  item=dict(clip_id=cid,theta=theta,pid=p.pid,folder=str(dest),config_sha256=sha(path),gpu_uuid=gpu,
   outside_original_parameter_domain=not(j['domain'][0]<=theta<=j['domain'][1]),normalization_domain=j['domain'],
   source_state_sha256=t['source_state_sha256'],reference_video_sha256=t['reference_video_sha256'],source_hashes=dep['sources'],
   selection='Original physical parameter axis, with disclosed nonnegative extensions outside the published range; old CPU labels not transferred, original normalization and frozen input preserved.')
  receipt.write_text(json.dumps(item,indent=2));started.append(item);slots-=1;free-=1000
print(json.dumps(dict(started=started,pending=pending,
 all_dispatched=[json.loads(p.read_text())for p in sorted(folder.glob('*/DISPATCH.json'))],
 max_owned_compute_processes=8,duplicate_launched=False)))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','collect']);args=p.parse_args()
    data,_=load()
    targets=[dict(clip_id=r['clip_id'],source_state_path=r['reference_native_state_binding']['state_path'],
        source_state_sha256=r['source_state_sha256'],reference_video_sha256=r['reference_video_sha256'],
        reference_label=r['reference_events']['upper_nonpulled_book_on_table_at_end'])for r in data['cases']if r['scene_id']=='T18']
    cache=None;cache_file=WORK/'T18_INITIAL_READBACK_CACHE.json'
    if cache_file.exists():cache=json.loads(cache_file.read_text())
    elif args.action=='collect'and(WORK/'T18_GPU_COLLECTOR.json').exists()and(WORK/'T18_GPU_ENDPOINTS_RESULT.json').exists():
        old=json.loads((WORK/'T18_GPU_COLLECTOR.json').read_text())
        pointer=json.loads((WORK/'T18_GPU_ENDPOINTS_RESULT.json').read_text());source=ROOT/pointer['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==pointer['sha256']
        report=json.loads(source.read_text())
        cache=dict(path=old['collector']['result_path'],canonical_sha256=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest())
        cache_file.write_text(json.dumps(cache,indent=2))
    payload='ACTION='+repr(args.action)+'\nKNOWN_RESULT_PATH='+repr(cache['path']if cache else None)+'\nKNOWN_RESULT_CANONICAL_SHA256='+repr(cache['canonical_sha256']if cache else None)+'\nTARGETS='+repr(targets)+'\n'+inspect.getsource(table_event)+'\n'+REMOTE
    if args.action=='collect':
        # State readback can exceed an SSH request's 60s deadline. One CPU
        # collector persists its result remotely; transport retries poll it
        # rather than starting the same multi-GB readback again.
        fingerprint=hashlib.sha256(payload.encode()).hexdigest()
        wrapper="""
import base64,fcntl,hashlib,json,subprocess
from pathlib import Path
base=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
snapshot=[]
for p in sorted((base/'endpoints').glob('*/DISPATCH.json')):
 item=json.loads(p.read_text());cmd=Path('/proc',str(item['pid']),'cmdline')
 alive=cmd.exists()and str(p.parent/'config.json').encode()in cmd.read_bytes()
 state=p.parent/'physics.json';stat=state.stat()if not alive and state.exists()else None
 snapshot.append([str(p),item['pid'],alive,None if stat is None else[stat.st_size,stat.st_mtime_ns]])
snapshot_sha256=hashlib.sha256(json.dumps(snapshot).encode()).hexdigest()
root=base/'collectors'/(FINGERPRINT+'_'+snapshot_sha256[:16])
root.mkdir(parents=True,exist_ok=True)
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
output=root/'result.json';receipt=root/'DISPATCH.json';worker=root/'worker.py'
if output.exists():
 print(json.dumps(json.loads(output.read_text())));raise SystemExit
if receipt.exists():
 item=json.loads(receipt.read_text());proc=Path('/proc',str(item['pid']),'cmdline')
 if proc.exists()and str(worker).encode()in proc.read_bytes():
  print(json.dumps(dict(status='collecting',collector=item)));raise SystemExit
 raise RuntimeError('Collector ended without a result; inspect '+str(root/'stderr.log'))
payload=base64.b64decode(PAYLOAD_B64).decode()
code='import contextlib,io,json,os\\nfrom pathlib import Path\\nbuf=io.StringIO()\\ntry:\\n with contextlib.redirect_stdout(buf):exec('+repr(payload)+')\\nexcept SystemExit as exc:\\n if exc.code not in (None,0):raise\\nvalue=json.loads(buf.getvalue())\\np=Path('+repr(str(output))+')\\ntmp=p.with_suffix(\".partial\")\\ntmp.write_text(json.dumps(value))\\nos.replace(tmp,p)\\n'
worker.write_text(code)
with(root/'stderr.log').open('xb')as log:
 p=subprocess.Popen(['python3',str(worker)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
item=dict(pid=p.pid,worker=str(worker),result_path=str(output),fingerprint=FINGERPRINT,snapshot_sha256=snapshot_sha256)
receipt.write_text(json.dumps(item));print(json.dumps(dict(status='collecting',collector=item)))
"""
        wrapper='FINGERPRINT='+repr(fingerprint)+'\nPAYLOAD_B64='+repr(base64.b64encode(payload.encode()).decode())+'\n'+wrapper
        import zlib
        encoded=base64.b64encode(zlib.compress(wrapper.encode())).decode()
        result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
        if result.get('status')=='collecting':
            (WORK/'T18_GPU_COLLECTOR.json').write_text(json.dumps(result,indent=2),encoding='utf8')
            print(json.dumps(result));return
    else:
        # Completed readbacks can make the payload exceed Windows' command
        # line limit. Compress the structured program for both actions.
        import zlib
        encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
        result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t18_gpu_endpoints_'+args.action+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('T18_GPU_ENDPOINTS_'+('DISPATCH'if args.action=='launch'else'RESULT')+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(status=result.get('status'),path=str(path),
        points=[dict(clip_id=p['clip_id'],theta=p['theta'],status=p.get('status'),
            label=p.get('measurement',{}).get('label'),native_peak_penetration_m=p.get('native_peak_penetration_m'))
            for p in result.get('points',[])],
        started=[dict(clip_id=p['clip_id'],theta=p['theta'],pid=p['pid'])for p in result.get('started',[])],
        pending=result.get('pending',[]))))


if __name__=='__main__':main()
