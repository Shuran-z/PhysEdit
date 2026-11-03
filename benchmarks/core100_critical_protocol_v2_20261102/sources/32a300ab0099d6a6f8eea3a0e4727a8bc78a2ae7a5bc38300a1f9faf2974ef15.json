"""Repeat the original C05 source and opposite endpoint, with no solver changes."""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import zlib
from scripts.t18_table_contact_boundary_worker import table_event
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,gzip,hashlib,importlib.util,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
base=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t18_gpu_20261102')
root=base/'c05_event_repeats_gpu4_retry';root.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(d):
 p=Path('/proc',str(d['pid']),'cmdline');return p.exists()and str(Path(d['folder'])/'config.json').encode()in p.read_bytes()
if ACTION=='collect':
 rows=[]
 for p in sorted(root.glob('*/DISPATCH.json')):
  d=json.loads(p.read_text());dest=Path(d['folder']);path=dest/'physics.json'
  if alive(d)or not path.exists():rows.append(dict(d,status='running'if alive(d)else'failed'));continue
  cfg=json.loads((dest/'config.json').read_text());assert sha(dest/'config.json')==d['config_sha256']
  for name,digest in d['source_hashes'].items():assert sha(Path(name))==digest
  s=json.loads(path.read_text());assert len(s['frames'])==210
  assert s['scene_overrides']==cfg['scene_overrides']
  assert {o['name']:o.get('spec',o)for o in s['dynamic_objects']}=={o['name']:o for o in cfg['dynamic_objects']}
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'and backend['actual_init_seed']==cfg['seed']%(2**31-1)
  frames=[]
  for f in s['frames'][4:155]:
   c=copy.deepcopy(f)
   if c['frame_index']>=s['render']['pre_static_frames']:c['contacts']=c['original_exterior_contacts']
   m=table_event(s,c);peak=max((a.get('penetration_m',0)for a in f.get('contacts',[])),default=0)
   frames.append(dict(frame=f['frame_index'],label=m['label'],upper_books_on_table=m['upper_books_on_table'],native_peak_depth_m=peak,
    target_table_depth_m=max((a.get('penetration_m',0)for a in m['contact_evidence']),default=0),
    target_table_contact_positions=[a['position']for a in m['contact_evidence']],
    contacts_inside_declared_support=all(math.dist(a['position'][:2],s['experiment']['support_center'])<=s['experiment']['support_radius']+.0001 for a in m['contact_evidence'])))
  rows.append(dict(d,status='completed',state_path=str(path),state_sha256=sha(path),backend=backend,
   source_hashes_verified=True,original_objects_solver_seed_and_clock_verified=True,
   window=[4,154],fps=s['render']['fps'],physical_frame_period_s=s['scene_overrides']['dt']*s['render']['physics_steps_per_render_frame'],
   contact_history=[f['frame']for f in frames if f['label']],terminal_frames=frames[-10:],
   finite_positions=all(math.isfinite(v)for f in s['frames'][4:155]for o in f['objects']for v in o['position']),formal_admission=False))
  del s
 print(json.dumps(dict(points=rows,status='completed'if len(rows)==2 and all(r['status']=='completed'for r in rows)else'pending')));raise SystemExit
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
paths=list((base/'endpoints').glob('*/DISPATCH.json'))+[base/'source/DISPATCH.json',base/'overlap_source/DISPATCH.json']
paths+=list(Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_legacy_exact_probes_20261102').glob('*/DISPATCH.json'))+list(root.glob('*/DISPATCH.json'))
known={}
for p in paths:
 if p.exists():
  d=json.loads(p.read_text())
  for item in d.get('points',[d]):known[str(item['pid'])]=item
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in known and alive(known[pid]),'Foreign compute: do not interfere';live+=1
free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[]
# The two older repeats had only just begun on a saturated card. Keep their
# entire attempt and receipt, terminate ONLY our exact config-bound PIDs, and
# record the scheduling handoff before starting on the newly idle same-model
# GPU. No source, endpoint state, solver parameter, or foreign job is changed.
handoff=root/'SCHEDULING_HANDOFF.json'
if not handoff.exists():
 assert live<=6 and free>12000,'Verified owned compute and free capacity required before handoff'
 import signal,time
 moved=[]
 for p in sorted((base/'c05_event_repeats').glob('*/DISPATCH.json')):
  item=json.loads(p.read_text());dest=Path(item['folder'])
  assert not(dest/'physics.json').exists(),'Old repeat completed: collect it rather than duplicate'
  if alive(item):
   os.kill(item['pid'],signal.SIGTERM)
   for _ in range(20):
    if not alive(item):break
    time.sleep(.1)
   assert not alive(item),'Owned repeat did not terminate; no duplicate launch'
  moved.append(dict(original_receipt=str(p),pid=item['pid'],folder=item['folder'],config_sha256=item['config_sha256'],
   previous_gpu_uuid=item['gpu_uuid'],status='superseded_for_newly_idle_same_model_gpu',partial_attempt_preserved=True))
 handoff.write_text(json.dumps(dict(attempts=moved,new_gpu_uuid=gpu,physical_inputs_and_solver_unchanged=True,foreign_jobs_modified=False,
  reason='The newly idle GPU1 failed with CUDA_ERROR_LAUNCH_FAILED and subsequently reports N/A. Preserve both failed attempts; retry only on the original healthy GPU without resetting any card.'),indent=2))
old=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_native_overlap_20261029');dep=json.loads((old/'deployment.json').read_text())
for name,digest in dep['sources'].items():assert sha(Path(name))==digest
job=next(j for j in json.loads((old/'jobs.json').read_text())if j['clip_id']=='T18_C05')
for kind,parent in [('source',base/'overlap_source/T18_C05'),('endpoint',base/'endpoints/T18_C05_0.15')]:
 dest=root/kind;receipt=dest/'DISPATCH.json'
 if receipt.exists():continue
 if live>=8 or free<12000:pending.append(kind);continue
 parent_cfg=parent/'config.json';cfg=json.loads(parent_cfg.read_text());original=copy.deepcopy(cfg)
 dest.mkdir(exist_ok=False);cfg['render']['save_video']=str(dest/'unused.mp4');cfg['annotations']['save_path']=str(dest/'physics.json')
 assert cfg['dynamic_objects']==original['dynamic_objects']and cfg['scene_overrides']==original['scene_overrides']and cfg['seed']==original['seed']
 path=dest/'config.json';path.write_text(json.dumps(cfg,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 if job.get('native_release_control'):env.update(CORE100_RELEASE_HOOK=dep['release_hook'],CORE100_MATERIAL_SEAL_HOOK=dep['material_hook'])
 with(dest/'run.log').open('xb')as log:
  p=subprocess.Popen([dep['python'],str(old/'native_bootstrap.py'),dep['renderer'],'--config',str(path)],cwd=dep['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 d=dict(kind=kind,clip_id='T18_C05',theta=.06534482758620688 if kind=='source'else.15,pid=p.pid,folder=str(dest),gpu_uuid=gpu,
  config_sha256=sha(path),parent_config_sha256=sha(parent_cfg),parent_state_sha256=sha(parent/'physics.json'),
  original_solver_and_physical_inputs_preserved=True,seed=cfg['seed'],source_hashes=dep['sources'],frozen_inputs_modified=False,formal_admission=False)
 receipt.write_text(json.dumps(d,indent=2));started.append(d);live+=1;free-=1000
print(json.dumps(dict(started=started,pending=pending,duplicate_launched=False)))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','collect']);args=parser.parse_args()
    payload='ACTION='+repr(args.action)+'\n'+inspect.getsource(table_event)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t18_c05_repeat_'+args.action+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('T18_C05_REPEAT_'+args.action.upper()+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(dict(status=result.get('status'),started=[dict(kind=r['kind'],pid=r['pid'])for r in result.get('started',[])],pending=result.get('pending'))))
    for r in result.get('points',[]):print(json.dumps(dict(kind=r['kind'],status=r['status'],terminal_labels=[f['label']for f in r.get('terminal_frames',[])])))


if __name__=='__main__':main()
