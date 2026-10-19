"""Keep raw model outputs, export event-level human queue and preannotations."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from physedit.boundary_dual_judge import route_dual
p=root/'review/qwen35_dual_20261017'
inputs=[json.loads(l) for l in (p/'inputs.jsonl').read_text().splitlines()]
results={r['sample_id']:r for r in map(json.loads,(p/'event_results.jsonl').read_text().splitlines())}
pre=[];queue=[];allrows=[]
for row in inputs:
 sid=row['sample_id'];r=results.get(sid,{})
 track=json.loads((root/'review/other_scene_window_probe_20261016'/f"{row.get('tracking_id',sid)}_tracks.json").read_text())
 try:
  if r.get('status')!='ok':raise ValueError(r.get('error','missing_result'))
  out=route_dual(r['judgement'],r['frame_indices'],{x['frame']:x['bbox_xyxy'] for x in track['frames']})
 except Exception as exc:
  out={'quality':{'route':'review'},'events':{e:{'route':'review','reasons':[str(exc)]} for e in ('departure','descent','landing')},'retain_in_denominator':True}
 allrows.append(dict(sample_id=sid,**out))
 for event,d in out['events'].items():
  item=dict(sample_id=sid,event=event,**d,source_sha256=row['sha256'],window_end_s=row['duration_s'],video=row['video'],human_label=None,reviewer_id=None)
  item['evidence_times_s']=[r['times_s'][i] for i in d.get('evidence',[]) if type(i) is int and 0<=i<len(r.get('times_s',[]))]
  (pre if d['route']=='preannotated' else queue).append(item)
for name,rows in [('preannotations',pre),('review_queue',queue)]:
 (p/f'{name}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
summary={'registered_videos':len(inputs),'completed_calls':len(results),'registered_event_decisions':len(inputs)*3,'preannotated_events':len(pre),'non_preannotated_events':len(queue),'samples':allrows}
(p/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
