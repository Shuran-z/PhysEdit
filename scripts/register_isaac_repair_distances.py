"""Bind repaired Isaac deliveries to their frozen search and production records."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
from physedit.boundary_recovery import recover
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=OUT/'isaac_repair_search_records.json';records=json.loads(source.read_text(encoding='utf-8'))
 calibrations={};production={}
 for r in records:
  if r['path'].endswith('/status_calibrate.json'):
   for group,g in json.loads(r['text'])['groups'].items():calibrations[(str(Path(r['path']).parent),group)]=g
  if r['path'].endswith('/status_produce.json'):
   for group,g in json.loads(r['text'])['groups'].items():
    for o in g.get('outputs',[]):production[o['output']]=dict(group=group,root=str(Path(r['path']).parent),record=o,production_status=g['status'])
 deliveries=json.loads(Path('review/release_boundary_binding_20261018/matched_registry.json').read_text())
 rows=[]
 for d in deliveries:
  if not 'repair_' in str(d.get('source_output')):continue
  p=production.get(d['source_output'])
  if not p:continue
  o=p['record'];g=calibrations[(p['root'],p['group'])]
  matched=d['config_sha256']==o['input_sha256'] and d['qa_sha256']==o['qa_sha256'] and d['depth']==o['depth'] and d['delivery_hashes_match'] and d['source_config_matches']
  if not matched:continue
  points=[dict(sample_id=x['output'],theta=x['value'],label=int(x['depth']>=g['depth']),valid=x['physics']=='PASS' and x['camera']=='PASS') for x in g['observations']]
  recovered=recover(points)
  param=d['parameter'];theta=param.get('value',param.get('withdrawal_distance_m'))
  assert abs(theta-o['value'])<1e-9
  row=dict(sample_id=d['sample_id'],scene_id=d['scene_id'],engine='isaac',source_group_id=p['group'],family_id='d'+str(g['depth']),parameter=param,theta=theta,target_event='propagation_depth_ge_'+str(g['depth']),reference_label=int(d['depth']>=g['depth']),reference_depth=d['depth'],config_sha256=d['config_sha256'],event_sha256=d['event_sha256'],source_output=d['source_output'],original_calibration_status=g['status'],production_status=p['production_status'],boundary=dict(status='observed',source=str(source.resolve()),source_sha256=digest(source),intervals=recovered['intervals']),blocking_reasons=['repair_context_and_reference_admission_pending','normalization_not_registered'])
  row['distance']=distance(row) if recovered['intervals'] else None
  if not row['distance']:row['blocking_reasons'].append('no_valid_transition_in_recovered_search')
  rows.append(row)
 (OUT/'isaac_repair_distance_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 summary=dict(matched_deliveries=len(rows),with_intervals=sum(bool(r['distance']) for r in rows),scenes={s:dict(matched=sum(r['scene_id']==s for r in rows),with_intervals=sum(r['scene_id']==s and bool(r['distance']) for r in rows)) for s in ['T16','T17','T18','T19']},search_groups=len(calibrations),group_status_counts=dict(collections.Counter(g['status'] for g in calibrations.values())))
 (OUT/'isaac_repair_distance_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
