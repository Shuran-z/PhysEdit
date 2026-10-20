"""Overlay completed T09 table-contact refinements, retaining every scan bracket."""
import hashlib
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances


def main():
    launch=json.loads((ROOT/'t09_table_contact_refinement_launch_20261020.json').read_text())
    code='''import json,hashlib
from pathlib import Path
r=Path(ROOT);p=r/'status.json';rows=json.loads(p.read_text()) if p.exists() else []
for row in rows:
 if row['status']!='refined_local_interval':continue
 if row['target_event']!='upper_nonpulled_book_on_table_at_end':raise ValueError('wrong event')
 for probe in row['probes']:
  if hashlib.sha256(Path(probe['state_path']).read_bytes()).hexdigest()!=probe['state_sha256']:raise ValueError('state changed')
print(json.dumps(rows))
'''.replace('ROOT',repr(launch['root']))
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=90);p.check_returncode()
    evidence=json.loads(p.stdout);(ROOT/'t09_table_contact_refinement_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    completed={r['job_id']:r for r in evidence if r['status']=='refined_local_interval'}
    out=ROOT/'original_value_distance_ledger';base=out/'t09_table_contact_sample_distances.jsonl';rows=[json.loads(l) for l in base.read_text().splitlines()]
    count=0
    for row in rows:
        result=completed.get(row['refinement_job_id'])
        if result is None:continue
        if row['original_boundary_interval']!=result['source_bracket']:raise ValueError('source interval mismatch')
        d=distances(row['theta'],bracket=result['bracket'])
        row.update(published_scan_interval=row['original_boundary_interval'],original_boundary_interval=result['bracket'],**d,
                   normalized_distance_lower=d['distance_lower']/row['normalization_span'],normalized_distance_upper=d['distance_upper']/row['normalization_span'],
                   refinement_source_seed=result['seed'],refinement_status='original_backend_fixed_seed_event_interval');count+=1
    (out/'t09_table_contact_refined_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary=dict(refined_intervals=len(completed),refined_records=count,base_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),failed=sum(r['status']=='failed' for r in evidence))
    (out/'t09_table_contact_refinement_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
