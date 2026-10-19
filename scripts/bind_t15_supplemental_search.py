"""Bind original-family supplemental intervals without asserting a unique threshold."""
import json
from pathlib import Path
from physedit.boundary import digest,read_rows
from physedit.boundary_recovery import recover,observed_distances
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=OUT/'t15_original_backend_extended.json'
 runs=[r for r in json.loads(source.read_text(encoding='utf-8')) if r['family']=='cfA']
 runs+=json.loads((OUT/'t15_original_backend_refined.json').read_text(encoding='utf-8-sig'))
 context_source=OUT/'t15_resolve_context.json'
 contexts=json.loads(context_source.read_text(encoding='utf-8'))
 registry=[]
 targets={'cfA':['laptop_falls_to_floor'],'cfB':['laptop_crosses_support_boundary','laptop_falls_to_floor','laptop_contacts_phone'],'cfC':['laptop_contacts_phone']}
 for run in runs:
  family=run['family'];states=[r for r in contexts if r['family']==family]
  source=OUT/('t15_original_backend_extended.json' if family=='cfA' else 't15_original_backend_refined.json')
  assert len(states)==len(run['outcomes'])
  for event in targets[family]:
   points=[]
   for p,s in zip(run['outcomes'],states):
    assert p['theta']==s['theta']
    frame=p['event_frames'].get(event);label=int(isinstance(frame,(int,float)) and frame>=0)
    valid=p['valid'] and (event!='laptop_falls_to_floor' or label==s['raw_fall'])
    points.append(dict(sample_id=s['sample_id'],theta=p['theta'],label=label,valid=valid))
   record=recover(points)
   record.update(scene='T15',family=family,parameter=run['parameter_field'],target_event=event,
    background='bg01_home_ase',gravity='g03_earth',source_file=source.name,source_sha256=digest(source),
    context_file=context_source.name,context_sha256=digest(context_source),
    solver_script_sha256=run['solver_script_sha256'],evidence_kind='original_backend_repeated_supplemental_scan',
    invalid_points=sum(not p['valid'] for p in points),observed_points=len(points),
    completeness='sampled transitions only; unknown points retained; narrower unobserved transitions not excluded')
   registry.append(record)
 dest=OUT/'t15_supplemental_intervals.json';dest.write_text(json.dumps(registry,indent=2),encoding='utf-8')
 answers=Path('review/h3_delivery_audit_20261016/recomputed_with_cv2/evaluation/answers.jsonl')
 keys=read_rows(answers);audit_path=Path('review/t15_boundary_pilot_20261014/reference_audit.json')
 audit={r['sample_id']:r for r in json.loads(audit_path.read_text(encoding='utf-8'))['rows']}
 a=next(r for r in registry if r['family']=='cfA');speed_contexts={r['speed_context_hash'] for r in contexts if r['family']=='cfA'}
 assert len(speed_contexts)==1
 bindings=[]
 for k in keys:
  ref=audit[k['reference_sample_id']]
  assert ref['state_sha256']==k['reference_state_sha256'] and ref['speed_context_hash']==k['source_group_id'] and ref['speed']==k['theta']
  if k['source_group_id'] not in speed_contexts or k['target_event']!=a['target_event']:continue
  row={f:k[f] for f in ('sample_id','reference_sample_id','reference_state_sha256','source_group_id','target_event','theta')}
  row.update(source_file=dest.name,source_sha256=digest(dest),mapping_status='matched',
   mapping_evidence='Original reference state SHA256, speed and physical-contract hash match; supplemental config/state contexts independently recomputed; raw z<-0.15 agrees with original cached event. This binds conditional speed response, not the reference sample original family label.',
   parameter_name='initial_book_speed',parameter_unit='m/s',boundary={'status':'observed','intervals':a['intervals']},
   reason='Multiple sampled transitions; QA-invalid points retained; no unique or exhaustive exact boundary claimed')
  bindings.append(row)
 (OUT/'h3_supplemental_bindings.json').write_text(json.dumps(dict(answers_sha256=digest(answers),bindings=bindings),indent=2),encoding='utf-8')
 print(json.dumps(dict(bound=len(bindings),families=[dict(family=r['family'],event=r['target_event'],intervals=r['intervals'],invalid=r['invalid_points']) for r in registry])))
if __name__=='__main__':main()
