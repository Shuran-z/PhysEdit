"""Append-only T04 scoring-readiness audit using frozen thresholds and existing annotations."""
import collections,csv,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'annotation_site'));from input_contract import matches_frozen_input
from protocol_rules import observation_evidence_problem
O=ROOT/'review/t04_critical_followup';snapshot=json.loads((O/'TASKS.json').read_text(encoding='utf8'));tasks=snapshot['tasks'];policy=json.loads((O/'source_site/core100_final_input_policy.json').read_text(encoding='utf8'));readback=json.loads((O/'ORIGINAL_STATE_READBACK.json').read_text(encoding='utf8'));sources={r['clip_id']:r for r in readback['cases']};registry=json.loads((O/'source_site/core100_active_distance_bindings.json').read_text(encoding='utf8'));cases={r['clip_id']:r for r in registry['cases']};admission=json.loads((O/'source_site/core100_admission.json').read_text(encoding='utf8'));window=json.loads((O/'source_site/reference_window_admission.json').read_text(encoding='utf8'));protocol=json.loads((ROOT/'docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md').read_text(encoding='utf8')) if False else None
near_upper=admission['frozen_policy']['near_upper'];tol=admission['frozen_policy']['pair_distance_tolerance'];assert near_upper==.05 and tol==.02
rows=[];casegaps=[]
for t in tasks:
 p=t['payload'];cid=p['clip_id'];human=None
 if t['state']=='resolved':
  a=t['annotations'];key='adjudication' if a.get('adjudication',{}).get('submitted') else 'primary';human=a[key]['payload'] if a.get(key,{}).get('submitted') else None
 expected=sources[cid]['reference_label'];input_ok=matches_frozen_input(p,policy);native=p['duration_s']>=5.;exact=p['window_s']==5.;q=human.get('quality',{}).get('status') if human else None;event=human.get('events',{}).get('original_full_chain',{}) if human else {};label=event.get('label');issues=[];measurement=None
 if not input_ok:issues.append('actual_frozen_input_mismatch')
 if not native:issues.append('native_duration_below_5s')
 if not human:issues.append('final_human_annotation_missing')
 if human and (human.get('video_sha256')!=p['video_sha256'] or human.get('protocol_sha256')!=p.get('protocol_sha256')):issues.append('human_video_or_protocol_identity_mismatch')
 inherited_negative=bool(human and native and p['window_s']>5. and q=='pass' and label=='no')
 if not exact and not inherited_negative:issues.append('exact_5s_annotation_missing')
 if q=='pass' and label in ['yes','no']:
  measurement=observation_evidence_problem(event,p['protocol']['events']['original_full_chain'],p,require_actor_ids=False)
  if measurement:issues.append('original_metric_measurement_or_calibration_missing')
 elif q=='pass':issues.append('binary_original_event_label_missing')
 known=None;kind=None
 # This is a label-agreement diagnostic only; missing measurement is never admitted as a formal physical score.
 if input_ok and native and (exact or inherited_negative) and human:
  if q=='failure':known=0;kind='confirmed_quality_failure_diagnostic'
  elif q=='pass' and label in ['yes','no']:known=int(int(label=='yes')==expected);kind='unverified_human_label_agreement' if exact else 'negative_ever_event_inherited_from_longer_window_diagnostic'
 validated=p.get('machine',{}).get('media_verified',{});media=validated.get('sha256')==p['video_sha256']
 rows.append(dict(task_id=t['id'],clip_id=cid,model=p['model'],seed=p['seed'],prompt_variant=p['prompt_variant'],video_sha256=p['video_sha256'],reference_label=expected,state=t['state'],human_quality=q,human_original_event_label=label,native_duration_s=p['duration_s'],annotated_window_s=p['window_s'],input_matches=input_ok,native_5s_covers=native,exact_5s_annotation=exact,negative_ever_label_inherited=inherited_negative,registered_media_sha_verified=media,registered_measurement_issue=measurement,diagnostic_label_agreement=known,diagnostic_kind=kind,NearAcc=None,PairAcc=None,ordinary_branch_formal_accuracy=None,blockers=issues))
for cid,r in sources.items():
 c=cases[cid];bins=[];gap=[]
 for b in c['boundary_records']:
  a,z=b['bracket'];theta=c['theta'];span=c['normalization_domain'][1]-c['normalization_domain'][0];lo=max(a-theta,theta-z,0)/span;hi=max(abs(theta-a),abs(theta-z))/span;assert [lo,hi]==b['distance']['normalized_absolute_interval'];bins.append(dict(event=b['event'],bracket=[a,z],normalized_distance_interval=[lo,hi],certified_near=hi<=near_upper,existing_bin=b['distance']['bin']))
 if not bins:gap.append('no_original_full_chain_opposite_consensus_endpoint_interval')
 if not any(b['certified_near'] for b in bins):gap.append('no_certified_near_point_at_existing_0p05_cutoff')
 if any(p['consensus_label'] is None for p in r['point_observations']):gap.append('same_parameter_repeats_have_conflicting_reference_labels')
 if not any(x.get('clip_id')==cid for x in window['references']):gap.append('reference_RGB_observability_and_5s_window_not_admitted_for_T04')
 own=[x for x in rows if x['clip_id']==cid];gap+=sorted({b for x in own for b in x['blockers']});gap.append('no_registered_legal_T04_pair')
 casegaps.append(dict(clip_id=cid,original_event='original_full_chain',reference_label=r['reference_label'],source_state_and_active_reference_match=r['registered_source_state_matches'],source_theta=r['theta'],observed_points=r['matched_points'],distinct_parameter_values=len(r['point_observations']),all_auxiliary_clearance_labels_one=all(all(x==1 for x in p['support_clearance_labels'])for p in r['point_observations']),distance_details=bins,NearAcc=None,PairAcc=None,blockers=gap,registered_outputs=len(own),resolved=sum(x['state']=='resolved' for x in own),exact_5s_annotations=sum(x['exact_5s_annotation'] for x in own),native_5s_covers=sum(x['native_5s_covers'] for x in own),measurement_missing=sum('original_metric_measurement_or_calibration_missing' in x['blockers'] for x in own)))
pairs=[]
for l,r in [('T04_C03','T04_C04'),('T04_C04','T04_C05'),('T04_C03','T04_C05')]:
 a,b=cases[l],cases[r];same=a['fixed_context_sha256']==b['fixed_context_sha256'];opposite=sources[l]['reference_label']!=sources[r]['reference_label'];details=[]
 for boundary in a['boundary_records']:
  lo,hi=boundary['bracket'];x,y=a['theta'],b['theta'];separated=(min(x,y)<=lo and max(x,y)>=hi);span=a['normalization_span'];pivots=[lo,hi]+[v for v in [x,y] if lo<=v<=hi];asym=max(abs(abs(x-v)-abs(y-v))/span for v in pivots);details.append(dict(bracket=[lo,hi],opposite_parameter_sides_guaranteed=separated,worst_distance_asymmetry=asym,original_tolerance=tol,symmetry_guaranteed=asym<=tol))
 legal=same and opposite and any(d['opposite_parameter_sides_guaranteed'] and d['symmetry_guaranteed'] for d in details);assert not legal
 pairs.append(dict(clips=[l,r],same_fixed_geometry_context=same,opposite_reference_labels=opposite,boundary_checks=details,legal_registered_pair=False,PairAcc=None,registered_score_combinations=0))
models=[]
for model in sorted({x['model']for x in rows}):
 own=[x for x in rows if x['model']==model];sub=[x for x in own if x['clip_id']in ['T04_C03','T04_C04','T04_C05']];known=[x['diagnostic_label_agreement']for x in sub if x['diagnostic_label_agreement'] is not None];perpoint=[]
 for cid in ['T04_C03','T04_C04','T04_C05']:
  z=[x for x in sub if x['clip_id']==cid];kk=[x['diagnostic_label_agreement']for x in z if x['diagnostic_label_agreement']is not None];perpoint.append(dict(clip_id=cid,registered=len(z),known_diagnostic=len(kk),correct_diagnostic=sum(kk),diagnostic_label_agreement=sum(kk)/len(kk) if kk else None,formal_accuracy=None))
 models.append(dict(model=model,T04_registered=len(own),C03_C05_registered=len(sub),C03_C05_resolved=sum(x['state']=='resolved' for x in sub),C03_C05_exact5_and_native_covers=sum(x['exact_5s_annotation'] and x['native_5s_covers']for x in sub),C03_C05_label_diagnostic_scored=len(known),C03_C05_label_diagnostic_correct=sum(known),label_agreement_diagnostic=sum(known)/len(known)if known else None,NearAcc=None,PairAcc=None,per_point=perpoint))
def dump(name,data):(O/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,data):
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:
  fields=list(dict.fromkeys(k for r in data for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(list,dict)) else v for k,v in r.items()})
dump('OUTPUT_READINESS_180.json',rows);csvout('OUTPUT_READINESS_180.csv',rows);dump('CASE_GAPS_5.json',casegaps);csvout('CASE_GAPS_5.csv',casegaps);dump('PAIR_ADMISSION_CHECKS.json',pairs);dump('MODEL_RESULTS_12.json',models);csvout('MODEL_RESULTS_12.csv',models)
summary=dict(snapshot_utc=snapshot['snapshot_utc'],source_states_read=readback['state_files_read'],registered_T04_outputs=len(rows),C03_C05_outputs=108,resolved=sum(x['state']=='resolved'for x in rows),input_matches=sum(x['input_matches']for x in rows),native_5s_covers=sum(x['native_5s_covers']for x in rows),exact_5s_annotations=sum(x['exact_5s_annotation']for x in rows),diagnostic_label_rows=sum(x['diagnostic_label_agreement']is not None for x in rows),formal_NearAcc_eligible_points=sum(any(d['certified_near']for d in x['distance_details'])for x in casegaps),formal_legal_pairs=0,NearAcc=None,PairAcc=None,blocker_counts=dict(collections.Counter(b for x in rows for b in x['blockers'])),new_thresholds=0,source_reference_prompts_human_labels_or_existing_scores_changed=False)
summary['negative_ever_labels_reused_without_reannotation']=sum(x['negative_ever_label_inherited'] for x in rows)
requests=[]
for x in rows:
 if not x['blockers']:continue
 actions=[]
 if not x['native_5s_covers']:actions.append('原视频不能补出5秒；保留登记。若补生成须另记新产物；若另设短窗须有对应参考和边界，不改当前5秒协议。')
 elif 'exact_5s_annotation_missing' in x['blockers']:actions.append('仅补5秒前缀观察记录，旧全窗质量/事件标签保留；不安排全量双审。')
 if 'final_human_annotation_missing' in x['blockers']:actions.append('完成原已分配任务，不另外增加一轮全量复审。')
 if 'original_metric_measurement_or_calibration_missing' in x['blockers']:actions.append('补原事件所需的公制位移/姿态/接触证据及标定来源；不增加事件阈值，不重开时间和理由表单。')
 if 'binary_original_event_label_missing' in x['blockers']:actions.append('补原full_chain的可判断标签；不可判断保留原状态，不填为未发生。')
 requests.append(dict(task_id=x['task_id'],clip_id=x['clip_id'],model=x['model'],seed=x['seed'],prompt_variant=x['prompt_variant'],video_sha256=x['video_sha256'],native_duration_s=x['native_duration_s'],existing_annotation_window_s=x['annotated_window_s'],reasons=x['blockers'],actions=actions,old_records_preserved=True,automatically_assigned=False))
dump('OUTPUT_FOLLOWUP_REQUESTS.json',requests);csvout('OUTPUT_FOLLOWUP_REQUESTS.csv',requests)
dump('SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=True,indent=2));print(json.dumps(models,ensure_ascii=True)[:6500])
