"""Resume infrastructure failures and independently replay source mismatches.

Never erase failed receipts or change published event labels/configurations.
"""
import base64
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    base='/data_cached/wangzijun_p25/liyuhan/t18_table_contact_search_20261020'
    files={n:base64.b64encode(Path('scripts',n).read_bytes()).decode() for n in
           ['t18_table_contact_boundary_worker.py','audit_t18_source_failures.py']}
    code=r'''
import pathlib,json,collections,subprocess,base64,hashlib,os,shutil
b=pathlib.Path(BASE);marker=b/'disk_recovery_20261025.json'
if marker.exists():
 print(marker.read_text());raise SystemExit
roots=[b/n for n in ['run','legacy_run','asset_retry_run']]+sorted(b.glob('resource_parallel_20261022_*'))
done=set();failed={}
for r in roots:
 for p in r.glob('*/result.json'):
  if json.loads(p.read_text())['status']=='conditional_event_search_completed':done.add(p.parent.name)
 s=r/'status.json'
 if s.exists():
  for x in json.loads(s.read_text()):
   if x['status']=='failed':failed[x['job_id']]=dict(x,root=str(r))
failed={k:v for k,v in failed.items() if k not in done}
counts=collections.Counter(x['error'] for x in failed.values())
if set(counts)-{'disk reserve below 20GiB','published source event did not reproduce'}:raise ValueError('inspect new failure class before resuming')
plans={j['job_id']:j for j in json.loads((b/'inputs/plan_all567.json').read_text())}
if set(failed)-set(plans):raise ValueError('unknown source job')
if shutil.disk_usage(b).free<25*1024**3:raise ValueError('insufficient storage for recovery')
for name,encoded in FILES.items():
 p=b/('recovery_20261025_'+name)
 if p.exists():raise ValueError('unexpected existing recovery helper')
 p.write_bytes(base64.b64decode(encoded))
worker=b/'recovery_20261025_t18_table_contact_boundary_worker.py'
python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
out=[]
for r in sorted(b.glob('resource_parallel_20261022_*')):
 selected=[plans[k] for k,v in failed.items() if v['error']=='disk reserve below 20GiB' and v['root']==str(r)]
 if not selected:continue
 # The same task root may only be resumed after its previous worker exited.
 import fcntl
 lock=(r/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 history=r/'status_before_disk_recovery_20261025.json';history.write_bytes((r/'status.json').read_bytes())
 plan=b/'inputs'/('disk_recovery_20261025_'+r.name+'.json');plan.write_text(json.dumps(selected))
 lock.close()
 with (r/'disk_recovery_20261025.log').open('w') as log:
  proc=subprocess.Popen([python,str(worker),'--plan',str(plan),'--root',str(r),'--gpu','auto','--renderer-timeout-seconds','1800','--minimum-free-memory-mib','8192'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
 out.append(dict(host='p25',root=str(r),pid=proc.pid,active_plan=str(plan),planned_contexts=len(selected),gpu='auto',worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),status_history=str(history)))
selected=[plans[k] for k,v in failed.items() if v['error']=='published source event did not reproduce']
r=b/'source_retry_20261025_0';r.mkdir(exist_ok=False)
plan=b/'inputs/source_retry_20261025.json';plan.write_text(json.dumps(selected))
with (r/'worker.log').open('w') as log:
 proc=subprocess.Popen([python,str(worker),'--plan',str(plan),'--root',str(r),'--gpu','auto','--renderer-timeout-seconds','1800','--minimum-free-memory-mib','8192'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
out.append(dict(host='p25',root=str(r),pid=proc.pid,active_plan=str(plan),planned_contexts=len(selected),gpu='auto',fresh_source_replay=True))
# CPU diagnosis uses original failed receipts, independent of new GPU attempts.
audit=b/'failure_audit_20261025';audit.mkdir(exist_ok=False)
with (audit/'worker.log').open('w') as log:
 proc=subprocess.Popen([python,str(b/'recovery_20261025_audit_t18_source_failures.py'),'--base',str(b),'--out',str(audit)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
result=dict(failure_counts=dict(counts),completed_before=len(done),queues=out,audit_pid=proc.pid,audit_root=str(audit),original_labels_changed=0)
marker.write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''.replace('BASE',repr(base)).replace('FILES',repr(files))
    result=json.loads(remote_text('p25',code,timeout=90))
    (ROOT/'t18_disk_recovery_20261025.json').write_text(json.dumps(result,indent=2))
    for i,launch in enumerate(result['queues']):
        (ROOT/f't18_disk_recovery_{i}_launch_20261025.json').write_text(json.dumps(launch,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
