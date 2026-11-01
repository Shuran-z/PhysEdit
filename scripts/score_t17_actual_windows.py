"""Re-evaluate original contact vectors on a five-second prefix; preserve old scores."""
import collections,csv,gzip,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'review/t17_window5_20261030'
vectors=json.loads((O/'contact_vectors.json').read_text())
assert all(r['state_sha256'] in (r['compressed_sha256'],r['decoded_sha256']) for r in vectors if r['kind']=='probe')
original={r['clip_id']:r for r in vectors if r['kind']=='original'}
registry=json.loads((R/'annotation_site/resources/reference_window_admission.json').read_text(encoding='utf8'));refs={r['clip_id']:r for r in registry['references']}
for clip,r in original.items():
 assert r['compressed_sha256']==r['source_state_sha256']==refs[clip]['reference_state_sha256']
 assert r['frame_count']==210 and r['contact_field_frames']>0
 r['condition_frame_index']=refs[clip]['condition_frame_index'];r['reference_fps']=refs[clip]['reference_fps']
 r['end_frame_5s']=r['condition_frame_index']+round(5*r['reference_fps'])
 r['label_5s']=int(any(r['condition_frame_index']<i<=r['end_frame_5s'] for i in r['contact_indices']))
 r['first_contact_after_condition_s']=min([(i-r['condition_frame_index'])/r['reference_fps'] for i in r['contact_indices'] if i>r['condition_frame_index']],default=None)
assert {r['label_5s']for r in original.values()}=={0}
tasks=json.load(gzip.open(R/'review/response_cohorts_20261030/live_tasks.json.gz','rt'))
rows=[]
for t in tasks:
 p=t['payload'];ref=original.get(p['clip_id'])
 if not ref:continue
 a=t['annotations'].get('primary',{});h=a.get('payload',{}) if a.get('submitted') else {};label=h.get('events',{}).get('can_tissue_box_contact',{}).get('label');q=h.get('quality',{}).get('status')
 v=p.get('machine',{}).get('media_verified',{});remote=p['remote_media']
 verified=v.get('sha256')==p['video_sha256'] and v.get('frames')==p['frames'] and abs(v.get('fps',0)-p['fps'])<=.02 and v.get('size')==remote['size']
 identity=h.get('video_sha256')==p['video_sha256'] and h.get('protocol_sha256')==p['protocol_sha256']
 end=(p['frames']-1)/p['fps'];assert abs(end-p['duration_s'])<.02
 base=dict(task_id=t['id'],model=p['model'],clip_id=p['clip_id'],prompt_variant=p['prompt_variant'],seed=p['seed'],native_duration_s=end,annotation_window_s=p['window_s'],human_quality=q,human_label=label,reference_label_5s=ref['label_5s'],media_metadata_verified=verified,annotation_identity_matches=identity,state=t['state'])
 # Never reinterpret a full-window positive/failure as a prefix observation.
 correct=None;reason='pending'
 if t['state']!='resolved':reason='disputed_or_unfinished'
 elif not verified or not identity:reason='media_or_annotation_identity_unverified'
 elif end+1e-6<5:reason='retained_for_native_window_only'
 elif abs(p['window_s']-5)<1e-6:
  if q=='failure':correct=0;reason='same_window_quality_failure_end_to_end'
  elif q=='pass' and label in ('yes','no'):correct=int(label=='no');reason='same_window_final_binary'
  else:reason='same_window_binary_pending'
 elif p['window_s']>5 and q=='pass' and label=='no':correct=1;reason='absence_in_longer_window_implies_prefix_absence'
 else:reason='prefix_review_required'
 native_correct=None
 if end<5 and t['state']=='resolved' and verified and identity and abs(p['window_s']-end)<.02:
  if q=='failure':native_correct=0
  elif q=='pass' and label in ('yes','no'):native_correct=int(label=='no')
 rows.append({**base,'five_second_correct':correct,'five_second_status':reason,'native_short_correct':native_correct,'NearAcc':None,'PairAcc':None})
def dumpcsv(name,data):
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
dumpcsv('per_video_scores.csv',rows)
models=[]
for model in sorted({r['model']for r in rows}):
 rr=[r for r in rows if r['model']==model];sc=[r for r in rr if r['five_second_correct']is not None];event=[r for r in sc if r['human_quality']=='pass'];native=[r for r in rr if r['native_short_correct']is not None]
 models.append(dict(model=model,total=len(rr),five_second_scored=len(sc),five_second_correct=sum(r['five_second_correct']for r in sc),five_second_accuracy=sum(r['five_second_correct']for r in sc)/len(sc)if sc else None,event_only_scored=len(event),event_only_correct=sum(r['five_second_correct']for r in event),short_native_scored=len(native),short_native_correct=sum(r['native_short_correct']for r in native),pending_or_not_five_second=len(rr)-len(sc),NearAcc=None,PairAcc=None))
dumpcsv('per_model_scores.csv',models)
probes=[]
for r in vectors:
 if r['kind']=='probe':probes.append({'clip_id':r['clip_id'],'theta':r['theta'],'label_5s':int(any(4<i<=154 for i in r['contact_indices'])),'first_contact_frame':min(r['contact_indices'],default=None),'source_state_sha256':r['decoded_sha256']})
summary={'scope':'T17_C04/C05 only; 5-second ever-contact response; ordinary negative-event accuracy, not NearAcc or PairAcc. Not all Core100. Aggregates include same-window human-confirmed quality failure as end-to-end failure; event-only counts also reported.','reference_clock':'Original admitted condition frame4, 30fps; five-second end frame154. No event or Near threshold changed.','reference_results':list(original.values()),'probe_results':probes,'five_second_boundary':'not_bracketed: all existing 20 probe trajectories negative within5s; 6.4s boundary cannot be transferred','five_second_scored':sum(r['five_second_correct']is not None for r in rows),'short_native_scored':sum(r['native_short_correct']is not None for r in rows),'per_model':models,'blockers':dict(collections.Counter(r['five_second_status']for r in rows)),'source_tasks_sha256':hashlib.sha256((R/'review/response_cohorts_20261030/live_tasks.json.gz').read_bytes()).hexdigest()}
(O/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:summary[k]for k in ['five_second_scored','short_native_scored','per_model','blockers']},ensure_ascii=False,indent=2))
