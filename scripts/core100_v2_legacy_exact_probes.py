"""Probe recovered T06/T09 configurations, preserving their executed families.

T06's mixed-width arc is regenerated from the original recipe, rather than
keeping its old y coordinates while spreading x. Values outside the published
normalization domain are disclosed and never expand that normalization.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_v2_resolution_20261102'
REMOTE = r'''
import copy,fcntl,gzip,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_legacy_exact_probes_20261102');root.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(item):
 p=Path('/proc',str(item['pid']),'cmdline')
 return p.exists() and str(Path(item['folder'])/'config.json').encode() in p.read_bytes()
def state(path):
 raw=path.read_bytes();return json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw)
def measurement(s,t,native):
 fs=s['frames'];assert len(fs)==210
 frames=fs[5:t['end_frame_index']+1]
 key='original_exterior_contacts'if native else'contacts'
 contacts=[]
 for f in frames:
  if native and f['frame_index']>=s['render']['pre_static_frames']:items=f[key]
  else:items=f.get('contacts',[])
  contacts.extend(dict(c,frame=f['frame_index'])for c in items)
 if t['clip_id'].startswith('T06'):
  pairs=s['experiment']['required_contact_pairs']
  first=[min((c['frame']for c in contacts if{c['entity_a'],c['entity_b']}==set(pair)),default=None)for pair in pairs]
  return dict(label=int(all(f is not None for f in first)),first_contact_frames=first)
 top=s['experiment']['supported_book_names'];table='frozen_tabletop_collision_slab'
 hits=[c for c in contacts if any({c['entity_a'],c['entity_b']}=={n,table}for n in top)]
 return dict(label=int(any(c['frame']==t['end_frame_index']for c in hits)),
  ever_contacts=int(bool(hits)),first_contact_frame=min((c['frame']for c in hits),default=None))
if ACTION=='collect':
 rows=[]
 for p in sorted(root.glob('*/DISPATCH.json')):
  item=json.loads(p.read_text());dest=Path(item['folder']);t=next(t for t in TARGETS if t['clip_id']==item['clip_id'])
  result=dest/'physics.json'
  if alive(item)or not result.exists():
   rows.append(dict(item,status='running'if alive(item)else'failed',log_tail=(dest/'run.log').read_text(errors='replace')[-700:]));continue
  cfg=json.loads((dest/'config.json').read_text());assert sha(dest/'config.json')==item['config_sha256']
  s=state(result);specs={o['name']:o.get('spec',o)for o in s['dynamic_objects']}
  assert specs=={o['name']:o for o in cfg['dynamic_objects']}
  expected=t['released_point']['original_solver'];lighting={'raytracing_env_encoding','raytracing_env_euler','raytracing_env_map','raytracing_lights','raytracing_env_map_required'}
  diff={k for k in set(expected)|set(s['scene_overrides'])if expected.get(k)!=s['scene_overrides'].get(k)}
  assert not diff-lighting
  assert s['render']['fps']==cfg['render']['fps']==30
  assert s['render']['physics_steps_per_render_frame']==cfg['render']['physics_steps_per_render_frame']
  strip=lambda forces:[{k:v for k,v in f.items()if k!='profile'}for f in forces]
  assert strip(s.get('runtime_forces',[]))==strip(cfg.get('runtime_forces',[]))
  backend=json.loads((dest/'runtime_backend.json').read_text());assert backend['backend']=='gpu32'
  assert backend['actual_init_seed']==cfg['seed']%(2**31-1)
  source=state(Path(t['released_point']['state_path']));m=measurement(s,t,True);old=measurement(source,t,False)
  errors={}
  for f,g in zip(source['frames'],s['frames']):
   other={o['name']:o for o in g['objects']}
   for o in f['objects']:
    errors[o['name']]=max(errors.get(o['name'],0),math.dist(o['position'],other[o['name']]['position']))
  peak=max((dict(c,frame=f['frame_index'])for f in s['frames'][5:t['end_frame_index']+1]for c in f.get('contacts',[])),key=lambda c:c.get('penetration_m',0),default={})
  rows.append(dict(item,status='completed',state_path=str(result),state_sha256=sha(result),
   actual_objects_solver_seed_control_and_clock_verified=True,measurement=m,source_measurement=old,
   source_position_error_m=errors if item['source_repeat']else None,backend=backend,
   native_depth_diagnostic=peak,formal_admission=False))
  del s,source
 print(json.dumps(dict(points=rows,status='completed'if len(rows)==10 and all(r['status']=='completed'for r in rows)else'pending',
  frozen_inputs_modified=False,normalization_domains_unchanged=True)));raise SystemExit
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
known={str(i['pid']):i for p in root.glob('*/DISPATCH.json')for i in[json.loads(p.read_text())]}
live=0
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 pid=p.findtext('pid');assert pid in known and alive(known[pid]),'Foreign GPU compute: do not interfere';live+=1
free=int(g.findtext('fb_memory_usage/free').split()[0]);started=[];pending=[]
project=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
renderer=project/'scripts/render_sample.py';bootstrap=Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_cpu_exact_20261029/native_bootstrap.py')
assert sha(renderer)=='89189629b1924b8beba41ace57f3ec18bade43e3b2685e17a4779c4437bd2256'
assert sha(bootstrap)=='1a4b48ec891a8518d2f535d4a3af2898b855af3c46c464bec29b0b586f4e18dc'
for t in TARGETS:
 point=t['released_point'];cp=Path(point['original_config_path']);assert sha(cp)==point['original_config_sha256']
 cfg=json.loads(cp.read_text());assert {o['name']:o for o in cfg['dynamic_objects']}==point['original_specs']
 assert cfg['seed']==point['original_seed']
 values=[t['theta'],.12,.1225]if t['clip_id'].startswith('T06')else[t['theta'],4.25,4.45,4.5]
 for theta in values:
  dest=root/(t['clip_id']+'_'+format(theta,'.12g'));receipt=dest/'DISPATCH.json'
  if receipt.exists():continue
  if live>=8 or free<12000:pending.append(dict(clip_id=t['clip_id'],theta=theta));continue
  c=copy.deepcopy(cfg);source_repeat=theta==t['theta']
  if not source_repeat and t['clip_id'].startswith('T06'):
   obs=sorted([o for o in c['dynamic_objects']if o['name'].startswith('t06_book_')],key=lambda o:o['name'])
   for i,o in enumerate(obs):o['pose']['position'][0]+=(i-(len(obs)-1)/2)*(theta-t['theta'])
   half=(obs[-1]['pose']['position'][0]-obs[0]['pose']['position'][0])/2
   for o in obs:o['pose']['position'][1]=round(.025*(1-(o['pose']['position'][0]/half)**2),7)
   slab=next(o for o in c['dynamic_objects']if o['name']=='frozen_tabletop_collision_slab')
   assert all(abs(o['pose']['position'][0]-slab['pose']['position'][0])<slab['size'][0]/2 for o in obs),'Initial COM outside support'
  elif not source_repeat:
   for f in c['runtime_forces']:
    if f['target']==c['experiment']['extracted_book_name']:f['force_world']=[v*theta/t['theta']for v in f['force_world']]
  c['experiment']['parameter']['parameter_value']=theta
  dest.mkdir(exist_ok=False);c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_video=str(dest/'unused.mp4'),save_first_rgb=None,save_last_rgb=None,save_rgb_frames=False,save_depth_frames=False,save_seg_frames=False)
  c['annotations'].update(enabled=True,save_path=str(dest/'physics.json'));path=dest/'config.json';path.write_text(json.dumps(c,indent=2))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,CORE100_BACKEND='gpu32',CORE100_NO_RGB='1',CORE100_NUMERIC_ONLY='1',PYOPENGL_PLATFORM='egl',TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
  with(dest/'run.log').open('xb')as log:
   process=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(bootstrap),str(renderer),'--config',str(path)],cwd=project.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  item=dict(clip_id=t['clip_id'],theta=theta,source_repeat=source_repeat,pid=process.pid,folder=str(dest),gpu_uuid=gpu,
   config_sha256=sha(path),source_config_sha256=sha(cp),source_state_sha256=point['state_decoded_sha256'],reference_video_sha256=t['reference_video_sha256'],
   source_hashes={str(p):sha(p)for p in[renderer,bootstrap,cp,project/'scripts/build_project.py']},
   normalization_domain=t['normalization_domain'],outside_published_parameter_domain=not(t['normalization_domain'][0]<=theta<=t['normalization_domain'][1]),
   original_family_preserved=True,formal_admission=False,frozen_inputs_modified=False)
  receipt.write_text(json.dumps(item,indent=2));started.append(item);live+=1;free-=1100
print(json.dumps(dict(started=started,pending=pending,duplicate_launched=False)))
'''


def main():
    p = argparse.ArgumentParser();p.add_argument('action', choices=['launch', 'collect']);args=p.parse_args()
    data,_=load();targets=[]
    for cid in ['T06_C02','T06_C03','T09_C01']:
        row=next(r for r in data['cases'] if r['clip_id']==cid)
        pointer=json.loads((WORK/(cid+'_RELEASED_AXIS.json')).read_text())
        path=ROOT/pointer['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
        records=json.loads(path.read_text());point=next(r for r in records['points']if r.get('sample_id')==records['source_sample_id'])
        assert point['executed_object_specs_match_config'] and point['physics_settings_match_config']
        targets.append({k:row[k]for k in ['clip_id','theta','end_frame_index','normalization_domain','reference_video_sha256']}|dict(released_point=point))
    payload='ACTION='+repr(args.action)+'\nTARGETS='+repr(targets)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('legacy_exact_'+args.action+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('LEGACY_EXACT_'+args.action.upper()+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps({k:result[k]for k in ['status','pending','duplicate_launched']if k in result}))
    for r in result.get('started',result.get('points',[])):
        print(json.dumps({k:r.get(k)for k in ['clip_id','theta','pid','status','measurement']}))


if __name__=='__main__':main()
