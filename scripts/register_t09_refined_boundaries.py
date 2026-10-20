"""Collect completed original-backend T09 intervals and retain unfinished ones."""
import json
import hashlib
import csv
import subprocess

from scripts.export_original_boundary_distances import ROOT, distances


def main():
    launch=json.loads((ROOT/'t09_geometry_drop_refinement_launch.json').read_text(encoding='utf-8'))
    code='''import pathlib,json,hashlib
root=pathlib.Path(ROOT);path=root/'status.json';rows=json.loads(path.read_text()) if path.exists() else []
project=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
for row in rows:
 if row['status']!='refined_local_interval':continue
 for p in row['probes']:
  config=project/'configs'/root.name/row['job_id']/(format(p['theta'],'.12g')+'.json')
  if hashlib.sha256(config.read_bytes()).hexdigest()!=p['config_sha256']:raise ValueError('supplemental config changed')
  if hashlib.sha256(pathlib.Path(p['state_path']).read_bytes()).hexdigest()!=p['state_sha256']:raise ValueError('supplemental state changed')
print(json.dumps(rows))
'''.replace('ROOT',repr(launch['root']))
    p=subprocess.run(['ssh','-o','BatchMode=yes',launch['host'],'python3 -'],input=code.encode(),capture_output=True,timeout=120)
    p.check_returncode();results=json.loads(p.stdout)
    source=ROOT/'t09_original_backend_refinement_evidence.json';source.write_text(json.dumps(results,indent=2),encoding='utf-8')
    completed={r['fixed_context_sha256']:r for r in results if r['status']=='refined_local_interval'}
    out=ROOT/'original_value_distance_ledger'
    base_source=out/'t09_geometry_drop_sample_distances.jsonl'
    rows=[json.loads(line) for line in base_source.read_text(encoding='utf-8').splitlines()]
    for row in rows:
        result=completed.get(row['fixed_context_sha256'])
        if result is None:row['refinement_status']='original_scan_interval_retained';continue
        d=distances(row['theta'],bracket=result['bracket'])
        row.update(original_scan_interval=row['original_boundary_interval'],original_boundary_interval=result['bracket'],**d,
            normalized_distance_lower=d['distance_lower']/row['normalization_span'],normalized_distance_upper=d['distance_upper']/row['normalization_span'],
            refinement_status='original_backend_fixed_seed_interval',refinement_job_id=result['job_id'],refinement_source_seed=result['seed'],refinement_evidence=str(source.resolve()),
            original_reference_kind='supplemental_original_backend_fixed_seed_local_interval',
            seed_scope='Conditional reference interval at the recorded source seed. Other published seeds remain recorded; no globally unique boundary claim.')
    (out/'t09_bound_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    with (out/'t09_bound_sample_distances.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['sample_id','family_id','theta','parameter_unit','drop_threshold_m','original_boundary_interval','distance_lower','distance_upper','reference_label','refinement_status','refinement_source_seed']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    summary=dict(completed_intervals=len(completed),failed_intervals=sum(r['status']=='failed' for r in results),planned_intervals=launch['planned_intervals'],
        base_distance_source_sha256=hashlib.sha256(base_source.read_bytes()).hexdigest(),
        refined_sample_records=sum(r['refinement_status']=='original_backend_fixed_seed_interval' for r in rows),retained_scan_records=sum(r['refinement_status']=='original_scan_interval_retained' for r in rows))
    (out/'t09_refinement_binding_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
