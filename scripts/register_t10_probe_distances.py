"""Register measured T10 pen-displacement transitions, not inferred folder support loss."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
from physedit.boundary_recovery import recover
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=OUT/'t06_t09_t10_kinematic_probe.json';rows=json.loads(source.read_text());groups=collections.defaultdict(list)
 for r in rows:
  if r['scene_id']=='T10':groups[r['parameter']['parameter_name']].append(r)
 registry=[];summary={}
 for name,items in groups.items():
  points=[]
  for r in items:
   threshold=r['original_event_thresholds']['support_ejection_threshold_m']
   points.append(dict(sample_id=r['sample_id'],theta=r['parameter']['parameter_value'],label=int(r['metrics']['t10_support_pen']['max_displacement_m']>=threshold),valid=r['frame_count']==210))
  rec=recover(points);summary[name]=rec
  for r,p in zip(items,points):
   if not rec['intervals']:continue
   x=dict(sample_id=r['sample_id'],scene_id='T10',engine='genesis',family_id=name,theta=p['theta'],target_event='support_pen_displacement_ge_0p04m',reference_label=p['label'],reference_state_sha256=r['state_sha256'],measurement_definition='maximum 3D center displacement relative to frame 0 over 210 frames; original declared threshold 0.04 m; not a label for folder support loss',boundary=dict(status='observed',source=str(source.resolve()),source_sha256=digest(source),intervals=rec['intervals']),blocking_reasons=['event_definition_and_replay_release_equivalence_pending','normalization_not_registered'])
   x['distance']=distance(x);registry.append(x)
 (OUT/'t10_probe_distance_registry.json').write_text(json.dumps(registry,indent=2),encoding='utf-8')
 (OUT/'t10_probe_interval_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(dict(registered=len(registry),intervals={k:v['intervals'] for k,v in summary.items()})))
if __name__=='__main__':main()
