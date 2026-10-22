"""Resume owned T18 queues, preserving successful probes and prior error history."""
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t18_resource_recovery_launch_20261021.json'
    if marker.exists():raise RuntimeError('resource recovery already performed')
    names=['t18_table_contact_search_launch_20261020.json','t18_legacy_search_launch_20261020.json']
    launches={name:json.loads((ROOT/name).read_text()) for name in names}
    base='/data_cached/wangzijun_p25/liyuhan/t18_table_contact_search_20261020'
    remote_text('p25',"import pathlib\np=pathlib.Path("+repr(base+'/worker_resource_recovery.py')+")\nassert not p.exists(), 'resource worker already exists'")
    subprocess.run(['scp','-q',str(Path('scripts/t18_table_contact_boundary_worker.py').resolve()),'p25:'+base+'/worker_resource_recovery.py'],check=True,timeout=120)
    code=r'''
import pathlib,json,subprocess,signal,os,time,hashlib
base=pathlib.Path(BASE);launches=LAUNCHES;out={}
for name,l in launches.items():
 r=pathlib.Path(l['root']);pid=l['pid'];p=pathlib.Path('/proc')/str(pid)/'cmdline'
 if p.exists():
  if str(base).encode() not in p.read_bytes() or os.getpgid(pid)!=pid:raise ValueError('owned T18 process identity changed')
  os.killpg(pid,signal.SIGTERM)
  for _ in range(50):
   if not subprocess.run(['pgrep','-g',str(pid)],capture_output=True).stdout:break
   time.sleep(.2)
  else:raise RuntimeError('old T18 group still active')
 before=r/'status_before_resource_recovery_20261021.json'
 if before.exists():raise ValueError('prior status backup already exists')
 before.write_bytes((r/'status.json').read_bytes());rows=json.loads(before.read_text())
 legacy=r.name=='legacy_run';gpu=1 if legacy else 2;plan=base/'inputs'/('supplement_plan.json' if legacy else 'plan.json')
 command=['python3',str(base/'worker_resource_recovery.py'),'--plan',str(plan),'--root',str(r),'--gpu',str(gpu),'--renderer-timeout-seconds','1800']
 with (r/'resource_recovery_worker.log').open('w') as log:p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (r/'resource_status.json').write_text(json.dumps(dict(status='running_resource_recovery',gpu=gpu,pid=p.pid,planned=len(json.loads(plan.read_text())))))
 out[name]=dict(l,pid=p.pid,gpu=gpu,prior_pid=pid,resource_recovery=True,renderer_timeout_seconds=1800,worker_sha256=hashlib.sha256((base/'worker_resource_recovery.py').read_bytes()).hexdigest(),prior_resource_failures=sum(x['status']=='failed' and 'GPU free-memory' in x.get('error','') for x in rows),status_history=str(before))
print(json.dumps(out))
'''.replace('BASE',repr(base)).replace('LAUNCHES',repr(launches))
    recovered=json.loads(remote_text('p25',code,timeout=60))
    for name,launch in recovered.items():
        (ROOT/(name+'.pre_resource_recovery')).write_text(json.dumps(launches[name],indent=2))
        (ROOT/name).write_text(json.dumps(launch,indent=2))
    marker.write_text(json.dumps(recovered,indent=2));print(json.dumps({name:dict(pid=l['pid'],gpu=l['gpu'],prior_resource_failures=l['prior_resource_failures']) for name,l in recovered.items()}))


if __name__=='__main__':main()
