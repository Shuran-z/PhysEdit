"""Collect fixed-seed pull-event refinements without dropping coarse scan rows."""
import hashlib
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances


def main():
    launch=json.loads((ROOT/'t09_pull_refinement_launch_20261020.json').read_text())
    plan={j['job_id']:j for j in json.loads((ROOT/'t09_pull_supplemental_search_plan_20261020.json').read_text())}
    code=r'''
import pathlib,json,gzip,hashlib
r=pathlib.Path(ROOT_DIRECTORY);p=r/'status.json';rows=json.loads(p.read_text()) if p.exists() else []
sha=lambda b:hashlib.sha256(b).hexdigest()
for row in rows:
 if row['status']!='refined_local_interval':continue
 if json.loads((r/row['job_id']/'result.json').read_text())!=row:raise ValueError('canonical result mismatch')
 for name,digest in row['backend_sources'].items():
  if sha(pathlib.Path(name).read_bytes())!=digest:raise ValueError('backend changed')
 for probe in row['probes']:
  raw=pathlib.Path(probe['state_path']).read_bytes()
  if sha(raw)!=probe['stored_state_sha256'] or sha(gzip.decompress(raw))!=probe['state_sha256']:raise ValueError('state changed')
  if sha(pathlib.Path(probe['config_path']).read_bytes())!=probe['config_sha256']:raise ValueError('config changed')
print(json.dumps(rows))
'''.replace('ROOT_DIRECTORY',repr(launch['root']))
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    evidence=json.loads(p.stdout);completed={}
    for row in evidence:
        if row['status']!='refined_local_interval':continue
        job=plan[row['job_id']]
        if row['source_bracket']!=job['bracket'] or row['seed']!=job['base_config']['seed'] or row['target_event']!=job['target_event']:raise ValueError('source context mismatch')
        labels={p['theta']:p['label'] for p in row['probes']}
        a,b=row['bracket'];lo,hi=job['bracket']
        if not lo<=a<b<=hi or b-a>.000500001 or labels.get(a)==labels.get(b) or a not in labels or b not in labels:raise ValueError('invalid solved endpoints')
        completed[row['job_id']]=row
    out=ROOT/'original_value_distance_ledger';base=out/'t09_pull_supplemental_sample_distances.jsonl'
    rows=[json.loads(l) for l in base.read_text().splitlines()];count=0
    for row in rows:
        result=completed.get(row['refinement_job_id'])
        if result is None:continue
        if row['original_boundary_interval']!=result['source_bracket']:raise ValueError('coarse bracket mismatch')
        d=distances(row['theta'],bracket=result['bracket'])
        row.update(published_scan_interval=row['original_boundary_interval'],original_boundary_interval=result['bracket'],**d,
                   normalized_distance_lower=d['distance_lower']/row['normalization_span'],normalized_distance_upper=d['distance_upper']/row['normalization_span'],
                   refinement_source_seed=result['seed'],refinement_status='original_backend_fixed_seed_event_interval',formal_nearacc_eligible=False)
        count+=1
    (out/'t09_pull_refined_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary=dict(refined_intervals=len(completed),planned=len(plan),failed=sum(r['status']=='failed' for r in evidence),pending=len(plan)-len(evidence),refined_records=count,records=len(rows),base_sha256=hashlib.sha256(base.read_bytes()).hexdigest())
    (ROOT/'t09_pull_refinement_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    (out/'t09_pull_refinement_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
