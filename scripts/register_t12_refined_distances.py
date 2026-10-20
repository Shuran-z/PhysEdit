"""Bind completed T12 exact-context intervals; retain all unfinished scan brackets."""
import hashlib
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT, distances


def main():
    launch=json.loads((ROOT/'t12_supplemental_refinement_launch.json').read_text())
    code='''import json,hashlib
from pathlib import Path
r=Path(ROOT);p=r/'status.json';rows=json.loads(p.read_text()) if p.exists() else []
for row in rows:
 if row['status']!='refined_local_interval':continue
 for probe in row['probes']:
  folder=r/row['job_id']/format(probe['theta'],'.12g')
  for key,name in [('config_sha256','config.json'),('state_sha256','physics.json')]:
   if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=probe[key]:raise ValueError('probe source changed')
print(json.dumps(rows))
'''.replace('ROOT',repr(launch['root']))
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=90);p.check_returncode()
    evidence=json.loads(p.stdout);(ROOT/'t12_refinement_evidence_20261020.json').write_text(json.dumps(evidence,indent=2))
    refined={(r['axis'],r['fixed_context_sha256'],tuple(r['source_bracket'])):r for r in evidence if r['status']=='refined_local_interval'}
    out=ROOT/'original_value_distance_ledger';base=out/'t12_supplemental_sample_distances.jsonl'
    rows=[json.loads(l) for l in base.read_text().splitlines()]
    count=0
    for row in rows:
        match=refined.get((row['axis'],row['fixed_context_sha256'],tuple(row['original_boundary_interval'])))
        if match is None:continue
        row['published_scan_interval']=row['original_boundary_interval'];d=distances(row['theta'],bracket=match['bracket'])
        row.update(original_boundary_interval=match['bracket'],**d,refinement_status='original_backend_refined_interval',
                   refinement_job_id=match['job_id'],backend_sha256=match['backend_sha256'],
                   normalized_distance_lower=d['distance_lower']/row['normalization_span'],
                   normalized_distance_upper=d['distance_upper']/row['normalization_span']);count+=1
    (out/'t12_refined_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary=dict(refined_intervals=len(refined),refined_sample_records=count,total_sample_records=len(rows),
                 base_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),failed=sum(r['status']=='failed' for r in evidence))
    (out/'t12_refinement_binding_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
