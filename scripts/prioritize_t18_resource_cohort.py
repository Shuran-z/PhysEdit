"""Prioritize the exact 200 resource-skipped IDs without changing scene inputs."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t18_resource_priority_launch_20261021.json'
    if marker.exists():raise RuntimeError('cohort priority already installed')
    names=['t18_table_contact_search_launch_20261020.json','t18_legacy_search_launch_20261020.json']
    launches={n:json.loads((ROOT/n).read_text()) for n in names}
    code=r'''
import pathlib,json,os,signal,subprocess,time,hashlib
requests=[];out={}
for name,l in LAUNCHES.items():
 r=pathlib.Path(l['root']);p=pathlib.Path('/proc')/str(l['pid']);history=r/'status_before_resource_recovery_20261021.json'
 if not p.exists() or str(r).encode() not in (p/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned T18 queue identity changed')
 args=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s];source=pathlib.Path(args[args.index('--plan')+1]);jobs=json.loads(source.read_text())
 cohort={x['job_id'] for x in json.loads(history.read_text()) if x['status']=='failed' and 'GPU free-memory' in x.get('error','')}
 complete={p.parent.name for p in r.glob('*/result.json')};original_ids=[j['job_id'] for j in jobs]
 ranked=sorted(enumerate(jobs),key=lambda pair:(0 if pair[1]['job_id'] in complete else 1 if pair[1]['job_id'] in cohort else 2,pair[0]))
 destination=source.with_name('resource_priority_'+r.name+'_20261021.json');destination.write_text(json.dumps([j for _,j in ranked]));args[args.index('--plan')+1]=str(destination)
 if sorted(original_ids)!=sorted(j['job_id'] for _,j in ranked):raise ValueError('priority changes job membership')
 requests.append((name,l,r,args,cohort,source,destination))
for name,l,r,args,cohort,source,destination in requests:
 os.killpg(l['pid'],signal.SIGTERM)
 for _ in range(50):
  if not subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout:break
  time.sleep(.2)
 else:raise RuntimeError('owned T18 group failed to exit')
 with (r/'resource_priority_worker.log').open('w') as log:p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 new=dict(l,pid=p.pid,prior_priority_pid=l['pid'],active_plan=str(destination),active_plan_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),priority_resource_job_ids=sorted(cohort))
 (r/'resource_priority_launch_20261021.json').write_text(json.dumps(new));out[name]=new
 (r/'resource_status.json').write_text(json.dumps(dict(status='running_resource_cohort_first',gpu=l['gpu'],pid=p.pid,priority_jobs=len(cohort))))
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches))
    result=json.loads(remote_text('p25',code,timeout=60))
    for name,l in result.items():(ROOT/name).write_text(json.dumps(l,indent=2))
    marker.write_text(json.dumps(result,indent=2));print(json.dumps({n:dict(pid=l['pid'],priority_jobs=len(l['priority_resource_job_ids'])) for n,l in result.items()}))


if __name__=='__main__':main()
