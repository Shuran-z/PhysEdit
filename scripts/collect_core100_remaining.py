"""Collect completed Core100 receipts; never count an active process as done."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from boundary_ssh import remote_text


def main():
    code='''import json,hashlib
from pathlib import Path
locations={
 'T14_C01':'core100_t14_original_gpu_v2_20261031/T14_C01',
 'T14_C02':'core100_t14_original_gpu_v3_20261031/T14_C02',
 'T16_C02':'core100_t16_c02_transition_20261031'}
for cid in ['T06_C01','T06_C02','T06_C03','T09_C01','T10_C01','T10_C02']:
 locations[cid]='core100_legacy_numeric_original_20261031/'+cid
rows=[]
for cid,name in locations.items():
 root=Path('/data2/liyuhan')/name;case=root/cid
 row=dict(clip_id=cid,root=str(root))
 if(case/'status.json').exists():row['status']=json.loads((case/'status.json').read_text())
 result=case/'result.json'
 sidecar=case/'BOUNDARY_BINDING_RESULT.json'
 if result.exists()or sidecar.exists():
  if not result.exists():
   result=sidecar;envelope=json.loads(sidecar.read_text())
   row['worker_status']=row.get('status')
   row['status']=dict(state='binding_complete_optional_refinement_stopped')
   row['completion_receipt']=envelope['completion_receipt']
   data=envelope['result']
  else:data=json.loads(result.read_text())
  row.update(result=data,result_sha256=hashlib.sha256(result.read_bytes()).hexdigest())
  profile=row['result'].get('profile',0)
  audit=case/('profile_'+str(profile))/'source_audit.json'
  row['source_audit']=json.loads(audit.read_text())
  job=next(j for j in json.loads((root/'jobs.json').read_text())if j['clip_id']==cid)
  row['job']={k:v for k,v in job.items()if k!='base_config'}
  row['source_config_physical_inputs']={k:job['base_config'].get(k)for k in ['seed','random_seed','dynamic_objects','runtime_forces','scene_overrides','experiment','render']}
  # Verify every completed probe's immutable state and configuration hashes.
  import gzip
  for probe in row['result'].get('probes',[])+row['result'].get('invalid_probes',[]):
   p=Path(probe['state_path']);raw=p.read_bytes();raw=gzip.decompress(raw)if p.suffix=='.gz'else raw
   assert hashlib.sha256(raw).hexdigest()==probe['state_sha256'],str(p)
   config=p.parent/'config.json'
   assert hashlib.sha256(config.read_bytes()).hexdigest()==probe['config_sha256'],str(config)
  row['completed_probe_state_hashes_verified']=True
  row['completed_probe_config_hashes_verified']=True
 else:
  row['source_audits']=[json.loads(p.read_text())for p in case.glob('profile_*/source_audit.json')]
  row['rejections']=[json.loads(p.read_text())for p in case.glob('profile_*/rejection.json')]
 rows.append(row)
print(json.dumps(rows))
'''
    text=remote_text('p25',code,timeout=120)
    rows=json.loads(text)
    path=ROOT/'review/core100_binding_20261028/remaining_completed_results_20261031.json'
    path.write_text(json.dumps(rows,indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=r['clip_id'],status=r.get('status',{}).get('state'),
        completed='result'in r,intervals=len(r.get('result',{}).get('intervals',[])))for r in rows]))


if __name__=='__main__':main()
