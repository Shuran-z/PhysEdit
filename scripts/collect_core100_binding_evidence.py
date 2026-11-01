"""Recover completed Core100 numerical receipts; no simulation or job launch."""
import base64
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_binding_20261028'
REMOTE=r'''
import json,hashlib,gzip
from pathlib import Path
requests=REQUESTS;out=[]
def pick(d,cid):
 if isinstance(d,list):
  return next((r for r in d if isinstance(r,dict)and r.get('clip_id',r.get('job_id'))==cid),None)
 if isinstance(d,dict):
  if d.get('clip_id',d.get('job_id'))==cid:return d
  if isinstance(d.get('source'),dict)and d['source'].get('clip_id')==cid:return d['source']
  for key in ['jobs','cases','requests']:
   v=pick(d.get(key),cid)
   if v:return v
 return None
for request in requests:
 p=Path(request['path']);cid=request['clip_id']
 if not p.exists():out.append(dict(clip_id=cid,path=str(p),missing=True));continue
 raw=p.read_bytes();d=json.loads(raw);jobs=[];audits=[];seen=set()
 for parent in list(p.parents)[:6]:
  for name in ['jobs.json','job.json','plan.json','request.json']:
   q=parent/name
   if q.exists():
    try:
     job=pick(json.load(open(q)),cid)
     if job:jobs.append(dict(path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest(),data=job))
    except Exception:pass
 for pattern in ['source_audit.json','source_window_audit.json','*/source_audit.json','*/source_window_audit.json','profile_*/source_audit.json']:
  for q in p.parent.glob(pattern):
   if str(q)in seen:continue
   seen.add(str(q))
   try:audits.append(dict(path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest(),data=json.load(open(q))))
   except Exception:pass
 out.append(dict(clip_id=cid,path=str(p),sha256=hashlib.sha256(raw).hexdigest(),
                 version=request['version'],data=d,jobs=jobs,source_audits=audits))
print(json.dumps(out))
'''


def main():
    snapshot=json.loads((WORK/'core100_live_execution_20261029.json').read_text(encoding='utf8'))
    targets={'p25':[],'sg88':[]}
    for case in snapshot['cases']:
        if case['clip_id'].startswith('T19'):continue
        selected=case['interval_candidate_versions']or case['finite_grid_no_flip_versions']
        if selected:
            row=selected[-1]
            targets[row['host']].append(dict(clip_id=case['clip_id'],path=row['path'],version=row['version']))
        if case['clip_id'].startswith(('T16','T17')):
            for row in case['other_results']:
                if row['version']=='core100_t16_t17_window_exact_20261030':
                    targets[row['host']].append(dict(clip_id=case['clip_id'],path=row['path'],version=row['version']))
    def collect(item):
        host,requests=item
        ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
        ssh+=(['-i','C:/Users/24511/.ssh/id_ed25519_sg88n5','yangkaiyuan@172.25.72.115'] if host=='sg88' else[host])
        code=REMOTE.replace('REQUESTS',repr(requests))
        p=subprocess.run(ssh+['python3','-'],input=code,encoding='utf8',capture_output=True,timeout=110)
        p.check_returncode()
        rows=json.loads(p.stdout)
        return host,rows
    with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
        result=dict(pool.map(collect,targets.items()))
    out=dict(collected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hosts=result,
             simulations_started=0)
    (WORK/'current_binding_evidence_20261031.json').write_text(json.dumps(out,indent=2),encoding='utf8')
    print(json.dumps({host:dict(records=len(rows),jobs_found=sum(bool(r.get('jobs'))for r in rows))for host,rows in result.items()}))


if __name__=='__main__':main()
