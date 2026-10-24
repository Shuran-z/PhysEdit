"""Resume ended owned queues with original workers, plans and cached receipts."""
import base64
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    names=['conditional_contacts_launch_20261023.json','conditional_t03_repaired_launch_20261023.json','conditional_library_recovery_launch_20261023.json']
    names+=['t18_parallel_'+str(i)+'_launch_20261022.json' for i in range(4)]
    names+=['t12_remaining_grid_'+str(i)+'_launch_20261022.json' for i in range(2)]
    launches={n:json.loads((ROOT/n).read_text()) for n in names}
    code=r'''
import pathlib,json,base64,hashlib,subprocess,os,shutil
launches=LAUNCHES;common=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/disk_recovery_20261023');common.mkdir(exist_ok=True)
supervisor=common/'gpu_wait_queue.py';raw=base64.b64decode(SOURCE)
if supervisor.exists() and supervisor.read_bytes()!=raw:raise ValueError('frozen recovery supervisor changed')
supervisor.write_bytes(raw);python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python';out={}
if shutil.disk_usage(common).free<25*1024**3:raise ValueError('insufficient disk headroom after recovery')
for name,l in launches.items():
 root=pathlib.Path(l['root']);scope=l.get('pipeline_root',str(root.parent));proc=pathlib.Path('/proc')/str(l['pid'])/'cmdline'
 if proc.exists() and (str(root).encode() in proc.read_bytes() or scope.encode() in proc.read_bytes()):out[name]=dict(l,recovery_status='existing_worker_left_running');continue
 marker=root/'disk_recovery_launch_20261023.json'
 if marker.exists():out[name]=json.loads(marker.read_text());continue
 if 'conditional_' in name:
  base=pathlib.Path(l['pipeline_root']);found=[]
  for p in base.glob('*manifest*.json'):
   m=json.loads(p.read_text())
   if isinstance(m,dict) and m.get('root')==str(root) and 'argv' in m:found.append(m)
  if len(found)!=1:raise ValueError('ambiguous original scheduler manifest')
  manifest=found[0]
 else:
  base=root.parent;plan=pathlib.Path(l['active_plan'])
  if hashlib.sha256(plan.read_bytes()).hexdigest()!=l['active_plan_sha256']:raise ValueError('original plan changed')
  workers=[p for p in base.glob('*.py') if hashlib.sha256(p.read_bytes()).hexdigest()==l['worker_sha256']]
  if not workers:raise ValueError('original worker unavailable')
  worker=workers[0];argv=[python,str(worker),'--plan',str(plan),'--root',str(root),'--gpu','{GPU}']
  if name.startswith('t18_'):argv+=['--renderer-timeout-seconds','1800','--minimum-free-memory-mib','8192']
  else:argv+=['--source',l['source']]
  manifest=dict(root=str(root),hours=336,minimum_free_memory_mib=8192,argv=argv,
   source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [plan,worker]})
 for p,d in manifest['source_sha256'].items():
  if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=d:raise ValueError('frozen input changed: '+p)
 manifest['startup_gpu_reservation_seconds']=30;manifest['source_sha256'][str(supervisor)]=hashlib.sha256(raw).hexdigest()
 path=root/'disk_recovery_manifest_20261023.json';path.write_text(json.dumps(manifest))
 status=root/'status.json';history=root/'status_before_disk_recovery_20261023.json'
 if status.exists() and not history.exists():history.write_bytes(status.read_bytes())
 env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
 lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 with (root/'disk_recovery_supervisor.log').open('a') as log:
  child=subprocess.Popen([python,str(supervisor),'--manifest',str(path)],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 result=dict(l,previous_pid=l['pid'],pid=child.pid,gpu='auto',pipeline_root=scope,
  disk_recovery='same original worker, plan, source and cached states; wait for an available GPU')
 marker.write_text(json.dumps(result));out[name]=result
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches)).replace('SOURCE',repr(base64.b64encode(Path('scripts/gpu_wait_queue.py').read_bytes()).decode()))
    result=json.loads(remote_text('p25',code,timeout=90,python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))
    for name,l in result.items():(ROOT/name).write_text(json.dumps(l,indent=2))
    (ROOT/'disk_recovery_queues_20261023.json').write_text(json.dumps(result,indent=2))
    marker=ROOT/'conditional_family_launches_20261023.json';all=json.loads(marker.read_text());updates={(l['host'],l['root']):l for l in result.values()}
    marker.write_text(json.dumps([updates.get((l['host'],l['root']),l) for l in all],indent=2))
    print(json.dumps({n:dict(pid=l['pid'],status=l.get('recovery_status','resumed')) for n,l in result.items()}))


if __name__=='__main__':main()
