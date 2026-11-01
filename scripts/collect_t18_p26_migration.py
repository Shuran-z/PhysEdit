"""Verify relocated T18 probes on p26 and feed the existing distance registrar."""
import argparse
import inspect
import json
import subprocess
import sys
import time
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT
from scripts.probe_verification_cache import verify_probe_files

def merge_completed_rows(rows, completed):
    by_id={r['job_id']:r for r in rows}
    for r in completed:
        if r['status']=='conditional_event_search_completed':by_id[r['job_id']]=r
    return list(by_id.values())


REMOTE=r'''
import json,gzip,hashlib,os,time
from pathlib import Path
VERIFY
MERGE_FUNCTION
base=Path('/21231_data1/liyuhan_t18_migration_20261027')
cachefile=base/'collector_cache.json';cache=json.loads(cachefile.read_text()) if cachefile.exists() else {}
last_checkpoint=time.monotonic()
def checkpoint():
 temp=cachefile.with_name(cachefile.name+'.'+str(os.getpid())+'.tmp')
 temp.write_text(json.dumps(cache));temp.replace(cachefile)
results=[];progress=[]
launch=json.loads((base/'launch.json').read_text())
for root in [Path(row['root']) for row in launch]:
 status=root/'status.json';rows=json.loads(status.read_text()) if status.exists() else []
 rows=merge_completed_rows(rows,[json.loads(path.read_text()) for path in root.glob('*/result.json')])
 progress.append(dict(root=str(root),finished=len(rows),failed=sum(r['status']=='failed' for r in rows)))
 for r in rows:
  if r['status']!='conditional_event_search_completed':
   if r['status']=='failed':results.append(dict(r,source_root=str(root),computation_host='p26'))
   continue
  receipts=[]
  for path in (root/r['job_id']).glob('*/receipt.json'):
   v=json.loads(path.read_text());v['state_path']=verify_probe_files(v,path.parent,cache)
   if time.monotonic()-last_checkpoint>3:
    checkpoint();last_checkpoint=time.monotonic()
   v.pop('contact_evidence',None);receipts.append(v)
  r.pop('probes',None)
  results.append(dict(r,verified_probe_receipts=receipts,source_root=str(root),computation_host='p26'))
checkpoint()
deployment=base/'deployment_status.json'
print(json.dumps(dict(results=results,progress=progress,deployment=json.loads(deployment.read_text()) if deployment.exists() else None)))
'''


def collect():
    code=REMOTE.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('MERGE_FUNCTION',inspect.getsource(merge_completed_rows))
    payload=json.loads(remote_text('p26',code,timeout=300,attempts=1))
    target=ROOT/'t18_p26_verified_results_20261027.json';tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload));tmp.replace(target)
    print(json.dumps(dict(completed=sum(r['status']=='conditional_event_search_completed' for r in payload['results']),
        failed=sum(r['status']=='failed' for r in payload['results']),progress=payload['progress'],deployment=payload['deployment'])),flush=True)
    return payload


def finish_handoff(payload):
    """Stop only the original owned queue after p26 produces a verified result."""
    marker=ROOT/'t18_p26_handoff_20261027.json'
    if marker.exists() or not any('/run_0' in r['source_root'] or '/run_1' in r['source_root'] for r in payload['results']):return
    code=r'''
import pathlib,json,os,signal
pid=2310060
root='/data_cached/wangzijun_p25/liyuhan/t18_table_contact_search_20261020/resource_parallel_20261022_2'
p=pathlib.Path('/proc')/str(pid)/'cmdline'
if p.exists():
 if root.encode() not in p.read_bytes() or os.getpgid(pid)!=pid:raise ValueError('owned queue identity changed')
 os.killpg(pid,signal.SIGTERM)
print(json.dumps(dict(previous_host='p25',previous_pid=pid,previous_root=root,new_host='p26',reason='verified p26 completed source-context result; preserve all old receipts')))
'''
    receipt=remote_text('p25',code,timeout=45,attempts=1);marker.write_text(receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--collect-only',action='store_true');args=p.parse_args();last=-1
    while True:
        try:
            result=collect();finish_handoff(result);n=len(result['results'])
            if n>last and n and not args.collect_only:
                subprocess.run([sys.executable,'-m','scripts.register_t18_table_contact_distances'],check=True)
                subprocess.run([sys.executable,'-m','scripts.combine_recovered_boundary_distances'],check=True)
            last=n
            deployment=result.get('deployment') or {}
            planned=sum(q['planned'] for q in deployment.get('queues',[]))
            if deployment.get('status')=='failed' or planned and sum(q['finished'] for q in result['progress'])>=planned:
                break
        except Exception as e:
            if not args.watch:raise
            print(type(e).__name__+': '+str(e),flush=True)
        if not args.watch:break
        time.sleep(120)
