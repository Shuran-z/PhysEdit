"""Repeat only T04's existing .125 endpoint, preserving physics and seed."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,fcntl,hashlib,json,math,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
old=Path('/data2/liyuhan/core100_continue_original_20261031/T04_C02')
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v3_t04_rechecks_20261103');root.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def alive(i):
 p=Path('/proc',str(i['pid']),'cmdline')
 return p.exists()and str(Path(i['folder'])/'config.json').encode()in p.read_bytes()
if ACTION in ['status','collect']:
 rows=[]
 for p in sorted(root.glob('*/DISPATCH.json')):
  i=json.loads(p.read_text());d=p.parent;s=d/'physics.json'
  row=dict(i,alive=alive(i),state_bytes=s.stat().st_size if s.exists()else 0,
    log_tail=(d/'run.log').read_text(errors='replace')[-400:])
  if ACTION=='collect'and not row['alive']and s.exists():
   state=json.loads(s.read_text());cfg=json.loads((d/'config.json').read_text())
   original_cfg=json.loads((old/'T04_C02/profile_0/0.125/config.json').read_text())
   def physical(c):
    c=copy.deepcopy(c);c['annotations'].pop('save_path',None)
    for k in ['save_video','save_first_rgb','save_last_rgb']:c['render'].pop(k,None)
    return c
   assert sha(d/'config.json')==i['config_sha256']and physical(cfg)==physical(original_cfg)
   assert {o['name']:o.get('spec',o)for o in state['dynamic_objects']}=={o['name']:o for o in cfg['dynamic_objects']}
   assert state['scene_overrides']==cfg['scene_overrides']and len(state['frames'])==210
   backend=json.loads((d/'runtime_backend.json').read_text())
   assert backend['backend']=='gpu32'and backend['actual_init_seed']==i['original_seed']
   frames=state['frames'][4:155];track=[next(o for o in f['objects']if o['name']=='t04v3_chain_mug')for f in frames]
   q=track[0]['quaternion_xyzw'];disp=max(math.dist(track[0]['position'],o['position'])for o in track)
   angle=max(math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(x*x for x in q)*sum(x*x for x in o['quaternion_xyzw'])))))for o in track)
   hits=[f['frame_index']for f in frames if any({c['entity_a'],c['entity_b']}=={'t04v3_chain_can_2','t04v3_chain_mug'}for c in f.get('original_exterior_contacts',f.get('contacts',[])))]
   row.update(status='completed',state_sha256=sha(s),state_path=str(s),backend=backend,
    physical_input_seed_solver_and_clock_verified=True,
    measurement=dict(label=int(bool(hits)and(disp>=.04 or angle>=18)),mug_maximum_displacement_m=disp,mug_maximum_angle_deg=angle,contact_frames=hits))
  elif ACTION=='collect':row['status']='running'if row['alive']else'failed_without_state'
  rows.append(row)
 print(json.dumps(dict(rows=rows)));raise SystemExit
lock=(root/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
dep=json.loads((old/'deployment.json').read_text())
for p,digest in dep['sources'].items():assert sha(p)==digest
original=(old/'native_bootstrap.py').read_text()
prelude="import runpy as _resource_handoff\n_resource_handoff.run_path('/data2/liyuhan/core100_continue_20261031_device_policy/device_handoff.py')\n"
assert original.startswith(prelude)
bootstrap=root/'native_bootstrap_fixed_device.py';source=original[len(prelude):]
if bootstrap.exists():assert bootstrap.read_text()==source
else:bootstrap.write_text(source)
gpu='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
g=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x','-i',gpu],universal_newlines=True)).find('gpu')
known={str(i['pid']):i for p in root.glob('*/DISPATCH.json')for i in[json.loads(p.read_text())]}
for p in g.findall('processes/process_info'):
 if p.findtext('type')=='G':continue
 assert p.findtext('pid')in known and alive(known[p.findtext('pid')]),'Foreign compute left untouched'
assert int(g.findtext('fb_memory_usage/free').split()[0])>=12000
import sys
sys.path.insert(0,'/data2/liyuhan/core100_continue_20261031_device_policy')
from egl_uuid_identity import matching_egl_index
egl=matching_egl_index(gpu)
cfg_path=old/'T04_C02/profile_0/0.125/config.json';cfg=json.loads(cfg_path.read_text())
assert sha(cfg_path)==EXPECTED_CONFIG_SHA
assert cfg['seed']==1212927170
assert cfg['experiment']['parameter']['commanded_extraction_speed_mps']==.125
started=[]
for repeat in [1,2]:
 dest=root/('endpoint_0p125_repeat'+str(repeat));receipt=dest/'DISPATCH.json'
 if receipt.exists():continue
 dest.mkdir(exist_ok=False);c=copy.deepcopy(cfg)
 c['annotations']['save_path']=str(dest/'physics.json')
 c['render'].update(save_video=str(dest/'unused.mp4'),save_first_rgb=None,save_last_rgb=None)
 config_path=dest/'config.json';config_path.write_text(json.dumps(c,indent=2))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,EGL_DEVICE_ID=str(egl),CUDA_DEVICE_ORDER='PCI_BUS_ID',
   CORE100_BACKEND='gpu32',CORE100_NUMERIC_ONLY='1',TI_OFFLINE_CACHE='0',
   PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
 with(dest/'run.log').open('xb')as log:
  command=[dep['python'],str(bootstrap),dep['renderer'],'--config',str(config_path)]+dep.get('extra_args',[])
  p=subprocess.Popen(command,cwd=dep['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 i=dict(clip_id='T04_C02',theta=.125,repeat=repeat,pid=p.pid,folder=str(dest),config_sha256=sha(config_path),
  original_endpoint_config_sha256=EXPECTED_CONFIG_SHA,original_seed=1212927170,gpu_uuid=gpu,egl_index=egl,
  original_bootstrap_sha256=sha(old/'native_bootstrap.py'),candidate_bootstrap_sha256=sha(bootstrap),
  removed_prelude=prelude,physical_bootstrap_body_identical=True,
  source_contract_sha256=SOURCE_CONTRACT_SHA,original_sources_modified=False,formal_admission=False)
 receipt.write_text(json.dumps(i,indent=2));started.append(i)
print(json.dumps(dict(started=started,duplicate_launched=False)))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','status','collect']);args=p.parse_args()
    pointer=json.loads((WORK/'T04_SOURCE_CONTRACT.json').read_text());proof=ROOT/pointer['path']
    assert hashlib.sha256(proof.read_bytes()).hexdigest()==pointer['sha256']
    assert json.loads(proof.read_text())['source_physical_contract_attested']
    old=json.loads((WORK/'t04_original_receipts.json').read_text())
    endpoint=next(p for p in old['receipts']if p['theta']==.125)
    payload='ACTION='+repr(args.action)+'\nEXPECTED_CONFIG_SHA='+repr(endpoint['config_sha256'])+'\nSOURCE_CONTRACT_SHA='+repr(pointer['sha256'])+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    r=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(r,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();target=WORK/('t04_recheck_'+args.action+'_'+digest[:12]+'.json');target.write_bytes(raw)
    (WORK/('T04_RECHECK_'+args.action.upper()+'.json')).write_text(json.dumps(dict(path=target.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(r if args.action=='launch'else[dict(clip_id=p['clip_id'],repeat=p['repeat'],alive=p['alive'],status=p.get('status'),measurement=p.get('measurement'),log_tail=p['log_tail'][-150:])for p in r['rows']]))


if __name__=='__main__':main()
