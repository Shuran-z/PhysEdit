"""Collect fixed-context T07-B grids; preserve original labels and no-flip cases."""
import argparse
import hashlib
import json
import time
import subprocess
import sys
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT, distances


def matching_reference_rows(answers, job):
    # Siblings may share geometry but have different simulator seeds. A fixed
    # source search certifies only its own released reference, not the triplet.
    return [a for a in answers if a['sample_id']==job['sample_id']]


def collect():
    launches=json.loads((ROOT/'t07_B_full_grid_launch_20261027.json').read_text())
    jobs={j['sample_id']:j for j in json.loads((ROOT/'t07_B_full_grid_plan_20261027.json').read_text())}
    answers=json.loads((ROOT/'t07_B_E4_reference_answers_20261022.json').read_text())
    extra=ROOT/'t07_B_original_plus_seed_launch_20261027.json'
    if extra.exists():
        launch=json.loads(extra.read_text());launches.append(launch)
        original=next(a for a in answers if a['sample_id']==launch['sample_id'])
        template=next(j for j in jobs.values() if j['source_group_id']==original['source_group_id'])
        jobs[original['sample_id']]=dict(template,sample_id=original['sample_id'],state_sha256=original['reference_state_sha256'])
    code=r'''
import json,hashlib
from pathlib import Path
results=[]
for launch in LAUNCHES:
 root=Path(launch['root']);p=root/'results.json'
 if not p.exists():continue
 for r in json.loads(p.read_text()):
  if r['status']=='conditional_grid_completed':
   folder=root/r['sample_id']
   for f in folder.glob('*/receipt.json'):
    receipt=json.loads(f.read_text());dest=f.parent
    if hashlib.sha256((dest/'physics.json').read_bytes()).hexdigest()!=receipt['state_sha256']:raise ValueError('state hash changed')
    if hashlib.sha256((dest/'config.json').read_bytes()).hexdigest()!=receipt['config_sha256']:raise ValueError('config hash changed')
   r['verified_source_root']=str(root)
  results.append(r)
print(json.dumps(results))
'''.replace('LAUNCHES',repr(launches))
    results=json.loads(remote_text('p25',code,timeout=60,attempts=1));rows=[]
    for result in results:
        if result['status']!='conditional_grid_completed':continue
        job=jobs[result['sample_id']]
        if result['source_state_sha256']!=job['state_sha256']:raise ValueError('source identity changed')
        lo,hi=job['normalization_domain']
        for a in matching_reference_rows(answers,job):
            for window in result['intervals']:
                rows.append(dict(a,original_boundary_interval=window['bracket'],**distances(a['theta'],bracket=window['bracket']),
                    normalization_span=hi-lo,normalization_domain=[lo,hi],
                    reference_kind='supplemental_fixed_source_E4_grid',source_search_sample_id=job['sample_id'],
                    source_root=result['verified_source_root'],formal_nearacc_eligible=False))
    target=ROOT/'original_value_distance_ledger/t07_B_full_grid_distances.jsonl'
    tmp=target.with_suffix('.tmp');tmp.write_text(''.join(json.dumps(r)+'\n' for r in rows));tmp.replace(target)
    if rows:
        subprocess.run([sys.executable,'-m','scripts.combine_recovered_boundary_distances'],check=True,stdout=subprocess.DEVNULL)
    completed=[r for r in results if r['status']=='conditional_grid_completed']
    summary=dict(planned=len(jobs),completed=len(completed),failed=sum(r['status']=='failed' for r in results),
        pending=len(jobs)-len(results),with_intervals=sum(bool(r['intervals']) for r in completed),
        bound_samples=len({r['sample_id'] for r in rows}),results=results)
    (ROOT/'t07_B_full_grid_summary_20261027.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}),flush=True)
    return len(results)>=len(jobs)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');args=p.parse_args()
    while True:
        try:done=collect()
        except Exception as e:
            if not args.watch:raise
            print(type(e).__name__+': '+str(e),flush=True);done=False
        if done or not args.watch:break
        time.sleep(60)
