"""Recover T01's friction/gap/friction task definitions and registered distances."""
import json
from pathlib import Path
OUT=Path('review/original_search_tasks_20261018')

def main():
 sources=json.loads((OUT/'p25_records.json').read_text(encoding='utf-8'))
 if (OUT/'t01_contract_source.json').exists():sources.append(json.loads((OUT/'t01_contract_source.json').read_text(encoding='utf-8')))
 c=next(s for s in sources if s['path'].endswith('manifests/t01_causal_parameter_design_v2.json'))
 contract=json.loads(c['text'])
 m=next(s for s in sources if s['path'].endswith('manifests/formal_52800_v2_full_chain/matrix.json'))
 matrix=json.loads(m['text'])
 published={r['sample_id']:r for r in map(json.loads,Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()) if r['engine']=='genesis' and r['event_id']=='T01'}
 fields={'A':'ramp_friction','B':'gap_12_m','C':'chain_friction'}
 rows=[]
 for r in matrix['rows']:
  family=r.get('counterfactual_group')
  row={'sample_id':r['sample_id'],'release_sample_id_match':r['sample_id'] in published,
       'original_design':r['design'],'manifest_sha256':m['sha256'],'contract_sha256':c['sha256'],
       'family':family,'gravity_id':r['gravity_id'],'background_id':r['background_id'],
       'status':'global_no_automatic_boundary_assignment','near_bin':None}
  if family in fields:
   task=contract['counterfactual_groups'][family]
   triplet=task.get('triplets_by_gravity',{}).get(r['gravity_id'],task.get('triplet'))
   row.update(parameter_name=task['controlled_variable'],theta=r[fields[family]],
     original_calibrated_star=triplet['theta_star'],distance_to_original_calibrated_star=abs(r[fields[family]]-triplet['theta_star']),
     original_triplet=triplet,original_boundary_event=task['boundary'],
     fixed_manifest_values_match=all(r.get(k)==v for k,v in task['fixed'].items()),
     branch_parameter_matches=r[fields[family]]==triplet[r['parameter_region']],
     status='original_task_linked_pending_release_bytes_and_evidence_validation',exact_threshold_claim=False)
  rows.append(row)
 (OUT/'t01_original_family_bindings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'total':len(rows),'counterfactual':sum(r['family'] in fields for r in rows),
   'parameter_mismatches':sum(r.get('branch_parameter_matches') is False for r in rows),
   'fixed_mismatches':sum(r.get('fixed_manifest_values_match') is False for r in rows)}))
if __name__=='__main__':main()
