"""Link all original T02 parameter families, preserving actual calibration provenance."""
import json,collections
from pathlib import Path
OUT=Path('review/original_search_tasks_20261018')

def main():
 sources=json.loads((OUT/'p26_records.json').read_text())+json.loads((OUT/'t02_family_sources.json').read_text())
 bypath={r['path']:r for r in sources}
 original=next(r for r in sources if r['path'].endswith('manifests/t02_full_causal_chain_parameter_design_v2.json'))
 contract=json.loads(original['text'])
 source=next(r for r in sources if r['path'].endswith('manifests/formal_52800_r006_p26_480p/matrix.json'))
 matrix=json.loads(source['text'])
 published={r['sample_id']:r for r in map(json.loads,Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text().splitlines()) if r['event_id']=='T02' and r['engine']=='genesis'}
 out=[]
 for m in matrix['rows']:
  family=m['causal_parameter_group'];g=m['gravity_id'];task=contract['gravity_specific_parameter_registry'][g][family]
  report=bypath.get(task['calibration_report'])
  matches=bool(report) and report.get('sha256','').lower()==task['calibration_report_sha256'].lower()
  # Explicit fields in the original manifest, not inferred from a name.
  fixed_values={'striker_initial_speed_mps':m['striker_speed_mps'],'striker_lateral_offset_m':m['striker_lateral_offset_m'],'probe_initial_speed_mps':m['probe_speed_mps']}
  fixed_match=all(k in fixed_values and abs(fixed_values[k]-v)<1e-9 for k,v in task['fixed'].items())
  star=task['triplet']['theta_star']['parameter_value']
  out.append(dict(sample_id=m['sample_id'],family=family,gravity_id=g,background_id=m['background_id'],
    parameter_name=m['changed_variable'],theta=m['parameter_value'],original_calibrated_star=star,
    distance_to_original_calibrated_star=abs(m['parameter_value']-star),
    calibrated_triplet=task['triplet'],original_fixed_parameters=task['fixed'],fixed_manifest_values_match=fixed_match,
    calibration_report_hash_match=matches,release_sample_id_match=m['sample_id'] in published,
    calibration_report=task['calibration_report'],calibration_report_sha256=task['calibration_report_sha256'],
    manifest_sha256=source['sha256'],contract_sha256=original['sha256'],
    original_design=m['design'],original_cf_group=m['cf_group'],
    status='original_task_linked_pending_release_byte_and_solver_validation' if matches and fixed_match and m['sample_id'] in published else 'requires_review',
    near_bin=None,exact_threshold_claim=False))
 (OUT/'t02_original_family_bindings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'total':len(out),'matched_report_and_fixed_manifest':sum(r['status'].startswith('original_task_linked') for r in out),'families':dict(collections.Counter(r['family'] for r in out))}))

if __name__=='__main__':main()
