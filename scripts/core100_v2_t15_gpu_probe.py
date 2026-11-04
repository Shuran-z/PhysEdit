"""Bounded original V11 GPU64 source/low-domain probes, isolated from releases."""
import argparse
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE_ROOT='/data_cached/wangzijun_p25/liyuhan/core100_v2_t15_gpu_20261102'
LAUNCH=r'''
import copy,hashlib,json,os,subprocess
from pathlib import Path
root=Path(REMOTE_ROOT)
if (root/'DISPATCH.json').exists():
 print((root/'DISPATCH.json').read_text());raise SystemExit
base=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
backend=base/'scripts/t15_v11_physics.py';backend_sha=hashlib.sha256(backend.read_bytes()).hexdigest()
assert backend_sha=='d12b8c736b6345ae2661b6244919d214cc9db6b68aaa34f6873e5f4c29788ffc'
uuid='GPU-a1763893-4894-cb56-2d97-06d695d6f419'
lines=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).decode().splitlines()
assert not any(line.startswith(uuid+',')for line in lines),'GPU4 has a compute process; do not interfere'
free=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode().strip()
assert int(free)>10000
root.mkdir(exist_ok=False)
manifest=json.loads((base/'configs/v11_20260914/delivery/manifest.json').read_text())
rows=[];bindings=[]
for t in TARGETS:
 source=next(r for r in manifest if r['sample_id']==t['sample_id']);cp=Path(source['config']);raw=cp.read_bytes();c=json.loads(raw)
 sp=Path(source['output'])/'metadata/physics.json';s=json.loads(sp.read_text());profile=s['physical_provenance']
 assert hashlib.sha256(sp.read_bytes()).hexdigest()==t['source_state_sha256']
 assert hashlib.sha256(raw).hexdigest()==profile['config_sha256']and s['dynamic_objects']==c['dynamic_objects']
 assert profile['implementation_sha256']==backend_sha and profile['precision_bits']==64 and profile['constraint_timeconst']==.002
 assert profile['solver_dt_s']==1/3840 and profile['settle_seconds']==1 and profile['contact_sol_params']is None
 assert profile['integrator']=='approximate_implicitfast'and profile['box_box_detection']
 driver=next(o for o in c['dynamic_objects']if o['name']=='t15v4_driver_book');assert driver['motion']['initial_velocity']==[t['theta'],0.,0.]
 for kind,theta in [('source',t['theta']),('low',t['normalization_domain'][0])]:
  dest=root/(t['clip_id']+'_'+kind);dest.mkdir();cfg=copy.deepcopy(c)
  if kind=='low':
   next(o for o in cfg['dynamic_objects']if o['name']=='t15v4_driver_book')['motion']['initial_velocity']=[theta,0.,0.]
   m=cfg['sample_metadata']
   for k in ['initial_velocity_mps','requested_initial_velocity_mps']:m[k]=theta
   for k in ['speed_multiplier','equivalent_force_n','impulse_ns']:m[k]*=theta/t['theta']
  path=dest/'config.json';path.write_text(json.dumps(cfg,indent=2))
  row=dict(sample_id=t['sample_id'],config=str(path),output=str(dest/'output'),clip_id=t['clip_id'],kind=kind,theta=theta)
  rows.append(row)
  bindings.append(dict(row,original_config_path=str(cp),original_config_sha256=hashlib.sha256(raw).hexdigest(),
   source_state_path=str(sp),source_state_sha256=t['source_state_sha256'],profile=profile,reference_label=t['label']))
(root/'manifest.json').write_text(json.dumps(rows,indent=2));(root/'BINDINGS.json').write_text(json.dumps(bindings,indent=2))
cmd=['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(backend),'--manifest',str(root/'manifest.json'),'--steps','128','--box','--settle','--timeconst','.002','--precision','64']
env=dict(os.environ,CUDA_VISIBLE_DEVICES=uuid,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with(root/'run.log').open('wb')as log:
 p=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=str(base))
receipt=dict(pid=p.pid,root=str(root),command=cmd,gpu_uuid=uuid,backend_sha256=backend_sha,
 points=len(rows),source_cases=3,conditional_low_probes=3,scope='No domain expansion or Near targeting; original source and low endpoint only.')
(root/'DISPATCH.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
COLLECT=r'''
import hashlib,json,math
from pathlib import Path
root=Path(REMOTE_ROOT);dispatch=json.loads((root/'DISPATCH.json').read_text());pid=dispatch['pid']
proc=Path('/proc')/str(pid)/'cmdline';alive=proc.exists()and any(str(root/name).encode()in proc.read_bytes()for name in['manifest.json','grouped_worker.py'])
if not(root/'results.json').exists():
 logs={str(p.relative_to(root)):p.read_text()[-800:]for p in root.glob('group*/run.log')}
 print(json.dumps(dict(status='running'if alive else'failed_before_results',pid=pid,completed_group_results=len(list(root.glob('group*/results.json'))),
  log_tail=(root/('grouped_run.log'if dispatch.get('worker')else'run.log')).read_text()[-1500:],group_logs=logs)));raise SystemExit
bindings=json.loads((root/'BINDINGS.json').read_text());points=[]
def measure(s):
 fs=s['frames'][5:155];assert len(fs)==150 and [f['frame_index']for f in fs]==list(range(5,155))
 zs=[next(o['position'][2]for o in f['objects']if o['name']=='t15v4_closed_laptop')for f in fs]
 return dict(label=int(min(zs)<-.15),minimum_laptop_world_z_m=min(zs),first_threshold_frame=next((f['frame_index']for f,z in zip(fs,zs)if z<-.15),None))
for b in bindings:
 sp=Path(b['output'])/'metadata/physics.json';s=json.loads(sp.read_text());cfg=json.loads(Path(b['config']).read_text())
 assert s['dynamic_objects']==cfg['dynamic_objects']and s['physical_provenance']['config_sha256']==hashlib.sha256(Path(b['config']).read_bytes()).hexdigest()
 differences={k:[v,s['physical_provenance'].get(k)]for k,v in b['profile'].items()if k!='config_sha256'and s['physical_provenance'].get(k)!=v}
 assert not differences
 source=json.loads(Path(b['source_state_path']).read_text());sourcecfg=json.loads(Path(b['original_config_path']).read_text())
 old={o['name']:o for o in sourcecfg['dynamic_objects']};new={o['name']:o for o in cfg['dynamic_objects']}
 new['t15v4_driver_book']['motion']['initial_velocity']=old['t15v4_driver_book']['motion']['initial_velocity']
 assert old==new and cfg['scene_overrides']==sourcecfg['scene_overrides']
 assert s['time_diagnostic']==source['time_diagnostic']
 delta=max(math.dist(a['position'],z['position'])for f,g in zip(source['frames'],s['frames'])for a,z in zip(f['objects'],g['objects']))if b['kind']=='source'else None
 points.append(dict(b,stored_state_sha256=hashlib.sha256(sp.read_bytes()).hexdigest(),config_sha256=hashlib.sha256(Path(b['config']).read_bytes()).hexdigest(),
  measurement=measure(s),source_measurement=measure(source),source_maximum_position_difference_m=delta,
  original_physical_inputs_except_declared_speed_verified=True,original_profile_seed_and_clock_verified=True,
  original_profile_differences=differences,
  all_contact_peak_penetration_m=max((c['penetration_m']for f in s['frames']for c in f.get('contacts',[])),default=0),
  scope='Original V11 GPU64/seed15/128steps/timeconst0.002, fixed simulator predicate; not a claim of real-physics convergence or exact full-trajectory reproduction.'))
print(json.dumps(dict(status='completed',process_alive=alive,dispatch=dispatch,points=points,results_sha256=hashlib.sha256((root/'results.json').read_bytes()).hexdigest())))
'''
RETRY=r'''
import json,os,subprocess
from pathlib import Path
root=Path(REMOTE_ROOT);old=json.loads((root/'DISPATCH.json').read_text())
if(root/'GROUPED_DISPATCH.json').exists():print((root/'GROUPED_DISPATCH.json').read_text());raise SystemExit
proc=Path('/proc',str(old['pid']),'cmdline')
assert not(proc.exists()and str(root/'manifest.json').encode()in proc.read_bytes())
assert not(root/'results.json').exists()and "('t15v4_floor_phone', 'friction')"in(root/'run.log').read_text()
assert not list(root.glob('*/output/metadata/physics.json'))
uuid=old['gpu_uuid']
lines=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).decode().splitlines()
assert not any(line.startswith(uuid+',')for line in lines)
rows=json.loads((root/'manifest.json').read_text());commands=[]
for cid in ['T15_C01','T15_C02','T15_C03']:
 d=root/('group_'+cid);d.mkdir(exist_ok=False);m=d/'manifest.json';m.write_text(json.dumps([r for r in rows if r['clip_id']==cid],indent=2))
 cmd=list(old['command']);cmd[cmd.index('--manifest')+1]=str(m);commands.append(cmd)
worker=root/'grouped_worker.py'
worker.write_text('import json,subprocess\nfrom pathlib import Path\ncommands='+repr(commands)+'\nroot=Path('+repr(str(root))+')\nresults=[]\nfor cmd in commands:\n p=Path(cmd[cmd.index("--manifest")+1])\n with p.with_name("run.log").open("wb")as log:\n  subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=3600)\n results.extend(json.loads(p.with_name("results.json").read_text()))\n(root/"results.json").write_text(json.dumps(results,indent=2))\n')
env=dict(os.environ,CUDA_VISIBLE_DEVICES=uuid,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with(root/'grouped_run.log').open('wb')as log:
 p=subprocess.Popen([old['command'][0],str(worker)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(old,pid=p.pid,worker=str(worker),grouped_commands=commands,
 previous_failed_pid=old['pid'],previous_failure='Native shared material assertion: moon phone friction differs. No physical parameter was altered; source/low grouped by original case.')
(root/'DISPATCH_failed_material_batch.json').write_text(json.dumps(old,indent=2))
(root/'GROUPED_DISPATCH.json').write_text(json.dumps(receipt,indent=2));(root/'DISPATCH.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['launch','collect','retry_grouped']);args=p.parse_args()
    data,_=load();targets=[]
    for r in data['cases']:
        if r['clip_id']in ['T15_C01','T15_C02','T15_C03']:
            targets.append(dict(clip_id=r['clip_id'],sample_id=r['sample_id'],theta=r['theta'],normalization_domain=r['normalization_domain'],
                source_state_sha256=r['source_state_sha256'],label=r['reference_events']['laptop_reaches_original_fall_criterion']))
    result=rpc(P21_OPTIONS,'p25','REMOTE_ROOT='+repr(REMOTE_ROOT)+'\nTARGETS='+repr(targets)+'\n'+dict(launch=LAUNCH,collect=COLLECT,retry_grouped=RETRY)[args.phase])
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t15_gpu_'+args.phase+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/('T15_GPU_'+('RESULT'if args.phase=='collect'else'DISPATCH')+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k!='points'}))
    if isinstance(result.get('points'),list):print(json.dumps([dict(clip_id=r['clip_id'],kind=r['kind'],theta=r['theta'],measurement=r['measurement'],source_maximum_position_difference_m=r['source_maximum_position_difference_m'])for r in result['points']]))


if __name__=='__main__':main()
