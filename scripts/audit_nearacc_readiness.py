"""Count completed NearAcc registrations separately from distance-only evidence."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
from scripts.reference_visual_admission import apply_review,load_reviews
OUT=Path('review/scene_family_completion_20261018')
def readiness(e):
 if not e:return False,['no_completed_event_specific_boundary_registration'],None
 reasons=list(e.get('blocking_reasons',[]))
 boundary=e.get('boundary',{})
 if boundary.get('status')!='verified':reasons.append('boundary_not_verified')
 if not boundary.get('normalization_span'):reasons.append('normalization_not_registered')
 if e.get('numerical_reference_verified') is False:reasons.append('numerical_checks_failed')
 if type(e.get('reference_label')) is not int or e.get('reference_label') not in (0,1):reasons.append('reference_event_label_not_bound')
 result=e.get('distance',{})
 if boundary.get('status')=='verified':
  try:result=distance(e)
  except (ValueError,KeyError,TypeError):reasons.append('invalid_boundary_registration')
 if result and result.get('bin')!='near':reasons.append('near_bin_not_resolved')
 reasons=sorted(set(reasons))
 return not reasons,reasons,result

def main():
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 known={}
 for name in ['t02_runtime_distance_registry.json','isaac_original_distance_registry.json','isaac_repair_distance_registry.json','t10_probe_distance_registry.json']:
  for r in json.loads((OUT/name).read_text(encoding='utf-8')):known[(r['engine'],r['sample_id'])]=r
 t14={r['reference_sample_id']:r for r in json.loads((OUT/'t14_formal_probe_distance_registry.json').read_text(encoding='utf-8'))}
 for sid,r in t14.items():known[('genesis',sid)]={**r,'distance':r['pipeline_distance'],'blocking_reasons':['repeat_and_reference_state_binding_pending','normalization_not_registered']}
 t04_path=OUT/'t04_probe_distance_registry.json'
 if t04_path.exists():
  for r in json.loads(t04_path.read_text(encoding='utf-8')):
   source=Path(r['bracket_evidence'])
   if digest(source)!=r['bracket_evidence_sha256']:raise ValueError('T04 bracket evidence changed')
   known[('genesis',r['sample_id'])]={**r,'engine':'genesis','target_event':'stack_motion',
    'distance':r['computed_distance'],'boundary':{'status':'pending_repeatability','normalization_span':r['normalization_basis']['normalization_span'],'source':str(source)},
    'blocking_reasons':['boundary_repeatability_pending','reference_rgb_observability_pending']}
 # Verified truth/normalization records supersede distance-only registrations.
 for name in ['isaac_verified_numerical_registry.json','t02_published_scoring_registry.json']:
  path=OUT/name
  if path.exists():
   for r in json.loads(path.read_text(encoding='utf-8')):known[(r['engine'],r['sample_id'])]=r
 t07_path=OUT/'t07_original_search_distance_registry.json'
 if t07_path.exists():
  for r in json.loads(t07_path.read_text(encoding='utf-8')):
   if digest(r['boundary']['source'])!=r['bracket_evidence_sha256']:raise ValueError('T07 search evidence changed')
   known[('genesis',r['sample_id'])]=r
 reviews=load_reviews()
 known={k:apply_review(v,reviews.get(k)) for k,v in known.items()}
 rows=[]
 for r in inventory:
  e=known.get((r['engine'],r['sample_id']))
  eligible,reasons,result=readiness(e)
  rows.append(dict(scene_id=r['event_id'],engine=r['engine'],sample_id=r['sample_id'],revision=r.get('revision'),
   measured_interval_distance_available=bool(e and e.get('distance')),
   formal_near_eligible=eligible,
   numerical_reference_verified=bool(e and e.get('numerical_reference_verified')),
   near_numerical_eligible=bool(e and e.get('near_numerical_eligible')),
   reference_label=e.get('reference_label') if e else None,
   target_event=e.get('target_event') if e else None,
   normalization_basis=e.get('normalization_basis') if e else None,
   reasons=reasons,distance=result,
   note='pending does not mean unusable; historical inventory only; no denominator filtering'))
 with (OUT/'nearacc_readiness_ledger.jsonl').open('w',encoding='utf-8') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 scenes=[]
 for i in range(1,21):
  sid=f'T{i:02}';items=[r for r in rows if r['scene_id']==sid]
  scenes.append(dict(scene_id=sid,historical_reference_trajectories=len(items),
   measured_interval_distance_registered=sum(r['measured_interval_distance_available'] for r in items),
   numerical_reference_verified=sum(r['numerical_reference_verified'] for r in items),
   near_numerical_eligible=sum(r['near_numerical_eligible'] for r in items),
   completed_formal_near_registrations=sum(r['formal_near_eligible'] for r in items)))
 score=json.loads((OUT/'h3_supplemental_refined_score.json').read_text(encoding='utf-8'))
 additional=json.loads((OUT/'t20_original_source_distances.json').read_text(encoding='utf-8'))
 summary=dict(additional_t20_source_distances_outside_historical_inventory=len(additional),scope='completed registrations in this recovered ledger, not an estimate of ultimately usable dataset size',
  total_historical_trajectories=len(rows),measured_interval_distance_registered=sum(r['measured_interval_distance_available'] for r in rows),
  numerical_reference_verified=sum(r['numerical_reference_verified'] for r in rows),
  near_numerical_eligible=sum(r['near_numerical_eligible'] for r in rows),
  completed_formal_near_reference_registrations=sum(r['formal_near_eligible'] for r in rows),generated_h3_registered=score['registered'],generated_h3_observed_bound=score['boundary_binding']['observed_bound'],
  completed_formal_near_scored_outputs=0,near_accuracy=score['near_accuracy'],scenes=scenes,
  reasons='Numerical qualification includes event truth, version mapping and frozen normalization. Formal visual qualification also requires event observability; pending references remain in the ledger. Counts are reference trajectories, not generated outputs or final held-out split counts.',
  ledger_sha256=digest(OUT/'nearacc_readiness_ledger.jsonl'))
 (OUT/'nearacc_readiness_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in summary.items() if k!='scenes'}))
if __name__=='__main__':main()
