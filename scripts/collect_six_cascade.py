"""Combine separate quality calls with retained event calls, preserving retries and locks."""
import json,sys,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from physedit.boundary_triage import route,parse_with_closing_brace_repair
p=root/'review/qwen35_six_quality_20261017';ep=root/'review/qwen35_six_triage_20261017';old=root/'review/qwen35_sam2_six_20261016'
def read(path):return {r['sample_id']:r for r in map(json.loads,path.read_text().splitlines())}
quality=read(p/'event_results.jsonl');events=read(ep/'event_results.jsonl');reg={r['sample_id']:r for r in json.loads((old/'evaluation_registration.json').read_text())}
rows=[];queue=[];pre=[]
for sid,k in reg.items():
 q=quality.get(sid,{});e=events.get(sid,{})
 retry=False
 repair=None
 if e.get('status')!='ok' and sid+'_event_retry' in quality:e=quality[sid+'_event_retry'];retry=True
 if e.get('status')!='ok' and e.get('raw'):
  try:
   judgement,repair=parse_with_closing_brace_repair(e['raw']);e=dict(e,judgement=judgement,status='ok')
  except (ValueError,TypeError):pass
 data={'quality':q.get('judgement',{}).get('quality',{}),'events':e.get('judgement',{}).get('events',{})}
 if q.get('status')=='ok' and e.get('status')=='ok':assert q['frame_indices']==e['frame_indices']
 ids=q.get('frame_indices',e.get('frame_indices',[]));tracks=json.loads((old/sid/'tracks.json').read_text())['frames']
 auto=route(data,ids,{x['frame']:x['bbox_xyxy'] for x in tracks});final=json.loads(json.dumps(auto))
 # Structured identity/support contradictions cannot silently pass quality.
 qq=data['quality']
 if auto['quality']['route']=='preannotated_measurable' and (qq.get('target_integrity')!='intact' or qq.get('support_integrity')!='intact'):
  final['quality']['route']='review';final['quality']['reasons'].append('quality_integrity_fields_not_intact')
  for x in final['events'].values():x.update(route='review',accepted_label=None)
 if k['manual_review_locked']:
  for x in final['events'].values():x.update(route='review',accepted_label=None,review_lock='user_requested_manual_review')
 for event,x in final['events'].items():
  item=dict(sample_id=sid,event=event,**x,human_label=None,reviewer_id=None)
  if x['route']=='review':queue.append(item)
  elif x['route']=='preannotated':pre.append(item)
 rows.append(dict(sample_id=sid,model=k['model'],automatic=auto,final=final,event_retry_used=retry,event_format_repair=repair,quality_call_status=q.get('status'),event_call_status=e.get('status')))
counts={'registered_videos':6,'quality_calls_completed':sum(k in quality for k in reg),'quality_routes':dict(collections.Counter(r['final']['quality']['route'] for r in rows)),
 'final_event_routes':dict(collections.Counter(x['route'] for r in rows for x in r['final']['events'].values())),
 'bad_rejected_of_2':sum(r['final']['quality']['route']=='reject_measurement' for r in rows if r['sample_id'] in ('clip02','clip05')),
 'clear_quality_retained_of_2':sum(r['final']['quality']['route']=='preannotated_measurable' for r in rows if r['sample_id'] in ('clip01','clip04')),
 'clear_descent_preannotated_yes_of_2':sum(r['final']['events']['descent'].get('accepted_label')=='yes' for r in rows if r['sample_id'] in ('clip01','clip04')),
 'independent_gold':False,'inversion_status':'not_run'}
(p/'summary.json').write_text(json.dumps(dict(counts=counts,samples=rows),ensure_ascii=False,indent=2),encoding='utf-8')
for name,items in [('review_queue',queue),('preannotations',pre)]:
 (p/f'{name}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items),encoding='utf-8')
print(json.dumps(counts,indent=2))
