"""Attach existing measured search intervals to exact delivered T16/T19 identities."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=Path('review/release_boundary_binding_20261018/matched_registry.json')
 records=json.loads(source.read_text(encoding='utf-8'));rows=[];groups=collections.defaultdict(list)
 for r in records:
  if r['route']!='matched_search_visual_review_pending':continue
  p=r['parameter'];prod=r['production']
  if 'withdrawal_distance_m' in p:name='withdrawal_distance_m';theta=p[name];unit='m'
  else:name=p['source_parameter']['name'];theta=p['value'];unit=p['source_parameter']['unit']
  row=dict(sample_id=r['sample_id'],scene_id=r['scene_id'],engine='isaac',family_id='d'+str(prod['boundary_depth']),
   parameter_name=name,parameter_unit=unit,theta=theta,target_event='propagation_depth_ge_'+str(prod['boundary_depth']),
   reference_label=int(r['depth']>=prod['boundary_depth']),reference_depth=r['depth'],
   config_sha256=r['config_sha256'],event_sha256=r['event_sha256'],source_output=r['source_output'],
   boundary=dict(status='observed',source=str(source.resolve()),source_sha256=digest(source),intervals=[dict(bracket=prod['measured_bracket'])]),
   cell=prod['cell'],repeat=prod['repeat'],level=prod['level'],
   formal_near_eligible=False,blocking_reasons=['original_admission_pending_repeated_boundary_and_visual_qa','normalization_not_registered'])
  row['distance']=distance(row);rows.append(row);groups[(row['cell'],row['family_id'],row['repeat'])].append(row)
 for key,items in groups.items():
  labels={r['reference_label'] for r in items}
  for r in items:
   r['same_repeat_both_outcomes']=labels=={0,1}
   if labels!={0,1}:r['blocking_reasons'].append('repeat_does_not_straddle_target_event')
 (OUT/'isaac_original_distance_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 summary=dict(total=len(rows),scene_counts=dict(collections.Counter(r['scene_id'] for r in rows)),
  repeat_groups=len(groups),straddling_repeat_groups=sum({r['reference_label'] for r in g}=={0,1} for g in groups.values()),
  formal_near_eligible=sum(r['formal_near_eligible'] for r in rows))
 (OUT/'isaac_original_distance_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
