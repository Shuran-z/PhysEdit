"""Recover event-specific measured intervals from original audits, preserve calibrated centers separately."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
from physedit.boundary_recovery import recover
OUT=Path('review/scene_family_completion_20261018')
def main():
 binding_source=Path('review/original_search_tasks_20261018/t02_original_family_bindings.json')
 bindings=json.loads(binding_source.read_text(encoding='utf-8'))
 audit_source=OUT/'t02_calibration_actual_files.json';audits={r['path']:r for r in json.loads(audit_source.read_text(encoding='utf-8'))}
 context_source=OUT/'t02_runtime_context_comparison.json';contexts={r['sample_id']:r for r in json.loads(context_source.read_text(encoding='utf-8'))}
 events={'A':'A1_striker_book_contact','B':'E4_blocked_marble_contacts_book','C':'C2_signal_displaced_0p05m'}
 rows=[];groups={}
 for r in bindings:
  assert contexts[r['sample_id']]['all_contexts_match']
  event=events[r['family']];points=[]
  for t in r['calibrated_triplet'].values():
   a=audits[t['audit']]['data'];assert event in a['event_frames']
   frame=a['event_frames'][event]
   points.append(dict(sample_id=t['sample_id'],theta=t['parameter_value'],label=int(isinstance(frame,(int,float)) and frame>=0),valid=a['status']=='PASS'))
  record=recover(points);groups[(r['gravity_id'],r['family'])]=record
  row=dict(sample_id=r['sample_id'],scene_id='T02',engine='genesis',family_id=r['family'],gravity_id=r['gravity_id'],
   theta=r['theta'],parameter_name=r['parameter_name'],parameter_unit='m' if r['family']=='A' else 'm/s',
   target_event=event,original_calibrated_star=r['original_calibrated_star'],distance_to_original_calibrated_star=r['distance_to_original_calibrated_star'],
   context_source_sha256=digest(context_source),audit_source_sha256=digest(audit_source),
   boundary=dict(status='observed',source=str(audit_source.resolve()),source_sha256=digest(audit_source),intervals=record['intervals']),
   formal_near_eligible=False,blocking_reasons=['published_reference_state_and_event_binding_pending','normalization_not_registered'],
   event_scope_note='B evaluates blocked-probe contact, not unobserved analytic toppling threshold; C uses original 0.05m displacement event')
  if record['intervals']:row['distance']=distance(row)
  else:row['blocking_reasons'].append('no_binary_event_transition_in_triplet');row['distance']=None
  rows.append(row)
 (OUT/'t02_runtime_distance_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 summary=dict(total=len(rows),with_intervals=sum(r['distance'] is not None for r in rows),groups=len(groups),groups_with_intervals=sum(bool(r['intervals']) for r in groups.values()),formal_near_eligible=0)
 (OUT/'t02_runtime_distance_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
