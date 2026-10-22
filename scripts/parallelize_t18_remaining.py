"""Partition pending T18 contexts; reuse probes and stop only owned workers."""
import inspect
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def partition(jobs, cohort, count=4):
    if count<1:raise ValueError('positive queue count required')
    ids=[j['job_id'] for j in jobs]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate job IDs')
    ranked=sorted(jobs,key=lambda j:(j['job_id'] not in cohort,j['job_id']))
    return [ranked[i::count] for i in range(count)]


def main():
    marker=ROOT/'t18_parallelization_20261022.json'
    if marker.exists():raise RuntimeError('T18 parallelization already performed')
    launches={n:json.loads((ROOT/n).read_text()) for n in ['t18_table_contact_search_launch_20261020.json','t18_legacy_search_launch_20261020.json']}
    base=str(Path(launches['t18_table_contact_search_launch_20261020.json']['root']).parent).replace('\\','/')
    worker=Path('scripts/t18_table_contact_boundary_worker.py')
    subprocess.run(['scp','-q',str(worker.resolve()),'p25:'+base+'/worker_parallel_20261022.py'],check=True,timeout=60)
    code=r'''
import pathlib,json,os,signal,subprocess,time,hashlib
PARTITION
base=pathlib.Path(BASE);old=LAUNCHES;manifest=base/'parallel_queues_20261022.json'
if manifest.exists():raise ValueError('parallel queues already exist')
for l in old.values():
 p=pathlib.Path('/proc')/str(l['pid'])
 if not p.exists() or str(base).encode() not in (p/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned process group identity changed')
plans=json.loads((base/'inputs/plan_all567.json').read_text());roots=[base/n for n in ['run','legacy_run','asset_retry_run']]
cohort=set();completed=set()
for r in roots:
 h=r/'status_before_resource_recovery_20261021.json'
 if h.exists():cohort.update(x['job_id'] for x in json.loads(h.read_text()) if x['status']=='failed' and 'GPU free-memory' in x.get('error',''))
 completed.update(p.parent.name for p in r.glob('*/result.json') if json.loads(p.read_text())['status']=='conditional_event_search_completed')
# Preserve published-event mismatch failures; these need diagnosis, not silent reclassification.
failed=set()
for r in roots:
 p=r/'status.json'
 if p.exists():failed.update(x['job_id'] for x in json.loads(p.read_text()) if x['status']=='failed' and x.get('error')=='published source event did not reproduce')
failed-=completed
pending=[j for j in plans if j['job_id'] not in completed|failed]
queues=partition(pending,cohort)
if len(cohort)!=200 or len(completed|failed|{j['job_id'] for j in pending})!=len(plans):raise ValueError('T18 cohort or coverage changed')
for l in old.values():
 r=pathlib.Path(l['root']);snapshot=r/'status_before_parallel_20261022.json'
 if snapshot.exists():raise ValueError('unexpected previous parallelization snapshot')
 snapshot.write_bytes((r/'status.json').read_bytes())
for l in old.values():os.killpg(l['pid'],signal.SIGTERM)
for l in old.values():
 for _ in range(100):
  live=subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout
  if not live:break
  time.sleep(.1)
 else:raise RuntimeError('owned process group did not stop')
# Recheck completions after termination to avoid losing a just-finished result.
completed.update(p.parent.name for r in roots for p in r.glob('*/result.json') if json.loads(p.read_text())['status']=='conditional_event_search_completed')
pending=[j for j in pending if j['job_id'] not in completed];queues=partition(pending,cohort)
out=[];worker=base/'worker_parallel_20261022.py'
for i,(jobs,gpu) in enumerate(zip(queues,[1,2,3,5])):
 r=base/('resource_parallel_20261022_'+str(i));r.mkdir(exist_ok=False)
 for j in jobs:
  choices=[x/j['job_id'] for x in roots if (x/j['job_id']).is_dir()]
  source=max(choices,key=lambda p:len(list(p.glob('*/receipt.json')))) if choices else roots[0]/j['job_id']
  source.mkdir(exist_ok=True);(r/j['job_id']).symlink_to(source,target_is_directory=True)
 plan=base/'inputs'/('parallel_20261022_'+str(i)+'.json');plan.write_text(json.dumps(jobs))
 command=['python3',str(worker),'--plan',str(plan),'--root',str(r),'--gpu',str(gpu),'--renderer-timeout-seconds','1800','--minimum-free-memory-mib','8192']
 with (r/'worker.log').open('w') as log:p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 out.append(dict(host='p25',root=str(r),pid=p.pid,gpu=gpu,planned_contexts=len(jobs),resource_cohort_jobs=sum(j['job_id'] in cohort for j in jobs),
   active_plan=str(plan),active_plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
   minimum_free_memory_mib=8192,disjoint_pending_partition=True,original_physics_and_seeds_preserved=True))
result=dict(queues=out,completed_before_partition=len(completed),failed_before_partition=len(failed),pending=len(pending),cohort_total=len(cohort),previous_launches=old)
manifest.write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''.replace('PARTITION',inspect.getsource(partition)).replace('BASE',repr(base)).replace('LAUNCHES',repr(launches))
    result=json.loads(remote_text('p25',code,timeout=90))
    for i,l in enumerate(result['queues']):(ROOT/('t18_parallel_'+str(i)+'_launch_20261022.json')).write_text(json.dumps(l,indent=2))
    for name,l in launches.items():
        l['superseded_by']='t18_parallelization_20261022.json';(ROOT/name).write_text(json.dumps(l,indent=2))
    marker.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['queues','previous_launches']}))


if __name__=='__main__':main()
