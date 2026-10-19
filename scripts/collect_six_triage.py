import json,sys,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from physedit.boundary_triage import route
p=root/'review/qwen35_six_triage_20261017';old=root/'review/qwen35_sam2_six_20261016'
inputs=[json.loads(l) for l in (p/'inputs.jsonl').read_text().splitlines()]
results={r['sample_id']:r for r in map(json.loads,(p/'event_results.jsonl').read_text().splitlines())}
registration={r['sample_id']:r for r in json.loads((old/'evaluation_registration.json').read_text())}
rows=[];queue=[];pre=[]
for row in inputs:
 sid=row['sample_id'];r=results.get(sid,{});reg=registration[sid]
 if r.get('status')=='ok':
  tracks=json.loads((old/sid/'tracks.json').read_text())['frames'];auto=route(r['judgement'],r['frame_indices'],{x['frame']:x['bbox_xyxy'] for x in tracks})
 else:auto={'quality':{'route':'review'},'events':{e:{'route':'review','reasons':[r.get('error','missing_result')]} for e in ('departure','descent','landing')}}
 final=json.loads(json.dumps(auto))
 if reg['manual_review_locked']:
  for e in final['events'].values():e.update(route='review',accepted_label=None,review_lock='user_requested_manual_review')
 for event,e in final['events'].items():
  item=dict(sample_id=sid,event=event,**e,source_sha256=row['sha256'],human_label=None,reviewer_id=None)
  item['evidence_times_s']=[r['times_s'][i] for i in e.get('normalized_evidence',[]) if i<len(r.get('times_s',[]))]
  if e['route']=='review':queue.append(item)
  elif e['route']=='preannotated':pre.append(item)
 rows.append(dict(sample_id=sid,model=reg['model'],automatic=auto,final=final,manual_review_locked=reg['manual_review_locked'],provisional_expected_gate=reg['provisional_expected_gate']))
counts={'registered_videos':6,'completed_calls':len(results),'quality_routes':dict(collections.Counter(r['automatic']['quality']['route'] for r in rows)),
 'final_event_routes':dict(collections.Counter(e['route'] for r in rows for e in r['final']['events'].values())),
 'bad_rejected_of_2':sum(r['automatic']['quality']['route']=='reject_measurement' for r in rows if r['sample_id'] in ('clip02','clip05')),
 'clear_quality_retained_of_2':sum(r['automatic']['quality']['route']=='preannotated_measurable' for r in rows if r['sample_id'] in ('clip01','clip04')),
 'clear_descent_preannotated_yes_of_2':sum(r['final']['events']['descent'].get('accepted_label')=='yes' for r in rows if r['sample_id'] in ('clip01','clip04')),
 'note':'Assistant provisional comparison, not independent human gold; user locks applied only after inference. No model leaderboard.'}
(p/'summary.json').write_text(json.dumps(dict(counts=counts,samples=rows),ensure_ascii=False,indent=2),encoding='utf-8')
for name,items in [('review_queue',queue),('preannotations',pre)]:
 (p/f'{name}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in items),encoding='utf-8')
print(json.dumps(counts,indent=2))
