"""Recompute boundary distances and live coverage without inventing truth.

Numerical results are separate from reference and model-score admission.
All generated outputs remain registered; unknown and pending are never zero.
"""
import collections
import csv
import hashlib
import io
import json
import time
from pathlib import Path
from workflow import final_annotation
from event_metrics import event_metrics
from scoped_critical import calculate_scoped
from input_contract import matches_frozen_input
from window_contract import window_binding

RES = Path(__file__).parent/'resources'


def calculate(tasks):
    admission=json.loads((RES/'core100_admission.json').read_text(encoding='utf-8'))
    policy=json.loads((RES/'core100_final_input_policy.json').read_text(encoding='utf-8'))
    physical_path=RES/'core100_physical_windows_20261027.json'
    physical=json.loads(physical_path.read_text(encoding='utf-8')) if physical_path.exists() else {'cases':{}}
    grouped=collections.defaultdict(list)
    for t in tasks:grouped[t['payload']['clip_id']].append(t)
    records=[];points=[];output_rows=[]
    for point in admission['points']:
        clip=point['clip_id'];own=grouped[clip]
        for source in point['numerical_distance_records']:
            a,b=source['original_boundary_interval'];theta=source['theta'];span=source['normalization_span']
            if not (a<=b and span>0):raise ValueError('invalid frozen numerical interval: '+clip)
            lower=max(a-theta,theta-b,0)/span
            upper=max(abs(theta-a),abs(theta-b))/span
            bucket='near' if upper<=.05 else 'mid' if lower>.05 and upper<=.15 else 'far' if lower>.15 else None
            if bucket!=source['bin']:raise ValueError('frozen distance classification changed: '+clip)
            records.append({**source,'raw_absolute_distance_interval':[lower*span,upper*span],
                            'normalized_distance_interval':[lower,upper],'bin':bucket})
        input_rule=policy['tasks'][clip]
        for t in own:
            p=t['payload'];human=final_annotation(t)
            prompt=p.get('source',{}).get('generation_metadata',{}).get('prompt')
            expected=input_rule['prompt_variant_sha256'][int(p['prompt_variant'])-1]
            match=matches_frozen_input(p,policy)
            output_rows.append(dict(task_id=t['id'],clip_id=clip,model=p['model'],seed=p['seed'],prompt_variant=p['prompt_variant'],
                expected_input_version=input_rule['input_version'],final_input_matches=match,video_sha256=p['video_sha256'],
                machine_status=p.get('machine',{}).get('pipeline_status','missing'),human_state=t['state'],
                human_submitted=any(a.get('submitted') for a in t['annotations'].values()),human_final=human is not None,
                human_quality=human.get('quality',{}).get('status') if human else None,
                human_events={k:v.get('label') for k,v in human.get('events',{}).items()} if human else {},
                physical_window=window_binding(p,physical['cases']),NearAcc=None,PairAcc=None))
        outputs=[r for r in output_rows if r['clip_id']==clip]
        numeric=[r for r in records if r['clip_id']==clip]
        blockers=[b for b in point['blockers'] if b not in ('site_outputs_not_exact_frozen_v6_inputs','human_review_pending')]
        if any(not r['final_input_matches'] for r in outputs):blockers.append('final_per_case_input_replacement_pending')
        if any(not r['human_final'] for r in outputs):blockers.append('human_review_pending')
        if clip in physical['cases']:
            blockers=[b for b in blockers if b!='reference_to_generated_window_not_frozen']
            if any(r['physical_window']['status']=='annotation_window_recheck_required' for r in outputs):
                blockers.append('generated_annotation_window_recheck_required')
            if any(not r['physical_window']['native_covers'] for r in outputs):
                blockers.append('some_models_have_insufficient_native_horizon')
        points.append(dict(clip_id=clip,registered_outputs=len(own),original_contract_ready=point['original_contract_ready'],
            numerical_records=len(numeric),distance_bins=sorted({r['bin'] or 'interval_crosses_bucket' for r in numeric}),
            near_candidate=any(r['bin']=='near' for r in numeric),input_version=input_rule['input_version'],
            input_matches=sum(r['final_input_matches'] for r in outputs),human_submitted=sum(r['human_submitted'] for r in outputs),
            human_final=sum(r['human_final'] for r in outputs),NearAcc=None,PairAcc=None,blockers=blockers,
            physical_window=physical['cases'].get(clip)))
    pairs=[]
    for source in admission['candidate_pairs']:
        a,b=source['boundary_interval'];span=source['normalization_span']
        # For two fixed points, the distance difference is piecewise linear
        # in the unknown boundary. Evaluate endpoints and interior breakpoints.
        theta=[next(r['theta'] for r in records if r['clip_id']==clip and r['canonical_event']==source['target_event'] and r['original_boundary_interval']==[a,b]) for clip in source['clips']]
        pivots=[a,b]+[x for x in theta if a<=x<=b]
        worst=max(abs(abs(theta[0]-x)-abs(theta[1]-x))/span for x in pivots)
        blocks=[v for v in source['blockers'] if v!='site_outputs_not_exact_frozen_v6_inputs']
        if any(p['input_matches']!=p['registered_outputs'] for p in points if p['clip_id'] in source['clips']):blocks.append('final_per_case_input_replacement_pending')
        pairs.append({**source,'worst_case_normalized_distance_asymmetry':worst,
                      'distance_symmetry_guaranteed':worst<=source['pair_tolerance'],'blockers':blocks,'PairAcc':None})
    per_model=[]
    for model in sorted({r['model'] for r in output_rows}):
        own=[r for r in output_rows if r['model']==model]
        near=[r for r in own if next(p['near_candidate'] for p in points if p['clip_id']==r['clip_id'])]
        per_model.append(dict(model=model,registered=len(own),input_matches=sum(r['final_input_matches'] for r in own),
            human_final=sum(r['human_final'] for r in own),near_candidate_outputs=len(near),
            near_human_final=sum(r['human_final'] for r in near),NearAcc=None,PairAcc=None,
            note='No admitted reference/window/pair package; numerical candidates are not model scores.'))
    scoped=calculate_scoped(tasks)
    admitted=json.loads((RES/'reference_window_admission.json').read_text(encoding='utf-8')) if (RES/'reference_window_admission.json').exists() else None
    if admitted:
        for r in records:r['evaluation_horizon_s']=None
        for ref in admitted['references']:
            row=dict.fromkeys(records[0])
            row.update(clip_id=ref['clip_id'],theta=ref['theta'],family_id=ref['family_id'],canonical_event=ref['target_event'],source_event=ref['target_event'],
                reference_label=ref['reference_label'],reference_state_sha256=ref['reference_state_sha256'],fixed_context_sha256=ref['fixed_context_sha256'],
                original_boundary_interval=ref['boundary_interval'],normalization_domain=ref['normalization_domain'],normalization_span=ref['normalization_span'],
                normalized_distance_interval=ref['normalized_distance_interval'],raw_absolute_distance_interval=[v*ref['normalization_span'] for v in ref['normalized_distance_interval']],
                bin=ref['bin'],formal_admitted=True,registered_boundary_status='verified_exact_source_seed_local_interval',
                evaluation_horizon_s=ref['horizon_s'],ledger_source='reference_window_admission.json')
            records.append(row)
            point=next(p for p in points if p['clip_id']==ref['clip_id'])
            point.update(reference_admission=ref['reference_admission'],registered_horizon_s=ref['horizon_s'])
            point['numerical_records']+=1
            point['blockers']=[b for b in point['blockers'] if b not in ('reference_RGB_observability_not_admitted','reference_to_generated_window_not_frozen')]
            point['blockers'].append('per_model_native_horizon_and_final_annotation_coverage')
        for new in admitted['pairs']:
            pair=next(p for p in pairs if p['clips']==new['clips'])
            pair.update(original_scan_boundary_interval=pair['boundary_interval'],boundary_interval=new['boundary_interval'],
                worst_case_normalized_distance_asymmetry=new['worst_case_normalized_distance_asymmetry'],distance_symmetry_guaranteed=True,
                normalized_distance_intervals=[next(r['normalized_distance_interval'] for r in admitted['references'] if r['clip_id']==clip) for clip in new['clips']],
                evaluation_horizon_s=6.4,status=new['status'],blockers=['per_model_native_horizon_and_final_annotation_coverage'])
        by_model={m['model']:m for m in scoped['per_model']}
        for m in per_model:
            sr=by_model[m['model']]
            m.update(NearAcc=sr['NearAcc'],PairAcc=sr['PairAcc'],admitted_cohort_registered=sr['registered'],admitted_cohort_status=sr['status'],
                     formal_scope=sr['scope'],NearAcc_bounds=sr['NearAcc_bounds'],PairAcc_bounds=sr['PairAcc_bounds'],
                     note='仅已准入T17接触子集；时域不足与未决人审分别报告，不代表完整100条成绩。')
    events=event_metrics(tasks)
    from contact_protocol import calculate as contact_calculate
    contact_amendment=contact_calculate(tasks)
    from execution_readiness import calculate as execution_calculate
    execution=execution_calculate(tasks)
    summary=dict(registered_outputs=len(tasks),source_definition_cases=contact_amendment['summary']['target_definition_cases'],original_terminal_definition_cases=sum(p['original_contract_ready'] for p in points),
        numerical_cases=sum(p['numerical_records']>0 for p in points),numerical_records=len(records),
        near_candidate_cases=sum(p['near_candidate'] for p in points),pair_candidates=len(pairs),
        final_input_matches=sum(r['final_input_matches'] for r in output_rows),
        input_replacements_pending=sum(not r['final_input_matches'] for r in output_rows),
        human_submitted=sum(r['human_submitted'] for r in output_rows),human_final=sum(r['human_final'] for r in output_rows),
        disputed=sum(t['state']=='disputed' for t in tasks),near_human_final=sum(r['near_human_final'] for r in per_model),
        machine_statuses=dict(collections.Counter(r['machine_status'] for r in output_rows)),NearAcc=None,PairAcc=None)
    summary.update(admitted_reference_cases=scoped.get('reference_cases',0),admitted_reference_pairs=scoped.get('reference_pairs',0))
    summary['physical_windows_repaired']=len(physical['cases'])
    # Replacement references form a new input version. Existing T19 outputs and
    # labels remain historical and cannot acquire the new truth by clip_id alone.
    from physedit.core100_release import status as reference_release_status
    active_reference_release=reference_release_status(tasks,RES/'active_reference_release.json')
    if active_reference_release['status']=='active':
        summary.update(active_reference_release_version=active_reference_release['version'],
            active_T19_reference_cases=active_reference_release['replaced_cases'],
            active_near_reference_cases=scoped.get('reference_cases',0)+active_reference_release['near_reference_cases'],
            active_reference_pairs=scoped.get('reference_pairs',0)+active_reference_release['registered_cross_boundary_pairs'])
    recovered_path=RES/'core100_recovered_numerical_bindings.json'
    recovered=[]
    if recovered_path.exists():
        from physedit.core100_release import load as load_reference_release
        _,_,current_conditions,_=load_reference_release(RES/'active_reference_release.json')
        condition_by_id={c['clip_id']:c for c in current_conditions['tasks']}
        for row in json.loads(recovered_path.read_text(encoding='utf8'))['records']:
            condition=condition_by_id[row['clip_id']]
            reference=condition.get('reference',{})
            expected=reference.get('sha256') or condition['source_video_sha256']
            if row['reference_video_sha256']!=expected:
                raise ValueError('recovered_numerical_reference_identity_changed')
            from physedit.boundary import distance
            measured=distance(row)
            if measured!=row['distance']:raise ValueError('recovered_numerical_distance_changed')
            record={**row,'ledger_source':recovered_path.name,'evaluation_horizon_s':row['evaluation_horizon_s'],
                'registered_boundary_status':'same_source_isaac_fixed_seed_local_search',
                'raw_absolute_distance_interval':[v*row['normalization_span'] for v in measured['normalized_absolute_interval']]}
            for old in records:
                if old['clip_id']==row['clip_id'] and old['canonical_event']==row['canonical_event']:
                    old['superseded_by_recovered_binding']=True
            records.append(record);recovered.append(record)
            point=next(p for p in points if p['clip_id']==row['clip_id'])
            point.update(numerical_records=point['numerical_records']+1,distance_bins=[measured['bin']],
                         near_candidate=measured['bin']=='near',latest_numerical_binding=record)
        summary.update(numerical_records=len(records),recovered_numerical_bindings=len(recovered))
    # Active all100 bookkeeping supersedes the old historical numerical-union
    # count. It never manufactures generated labels or bypasses score admission.
    from physedit.core100_bindings import load as load_distance_bindings
    active_distance_registry=load_distance_bindings()
    active_by_id={r['clip_id']:r for r in active_distance_registry['cases']}
    for point in points:point['active_distance_binding']=active_by_id[point['clip_id']]
    summary.update(active_reference_distance_ready=active_distance_registry['summary']['distance_ready'],
        active_reference_interval_ready=active_distance_registry['summary'].get('interval_reference_cases'),
        active_reference_calibration_values=active_distance_registry['summary'].get('recorded_calibration_reference_cases',0),
        active_reference_distance_not_applicable=active_distance_registry['summary']['not_applicable_in_registered_scan'],
        active_reference_distance_pending=active_distance_registry['summary']['incomplete'])
    from core100_connection import calculate as connect_all
    all_connection=connect_all(active_distance_registry,tasks,policy,admitted or {})
    return dict(schema='critical-calculation-v2',calculated_at=time.time(),status='admitted_cohort_scoring_live' if admitted else 'numerical_complete_formal_admission_pending',
        summary=summary,points=points,distance_records=records,candidate_pairs=pairs,core100_connection=all_connection,
        model_window_diagnostics=admission['model_window_diagnostics'],per_model=per_model,outputs=output_rows,
        vlm_human_agreement=events,admitted_cohort=scoped,reference_window_admission=admitted,contact_amendment=contact_amendment,execution_readiness=execution,
        physical_window_registry=physical,
        active_reference_release=active_reference_release,
        recovered_numerical_bindings=recovered,
        active_distance_registry=active_distance_registry,
        provenance={'admission_sha256':hashlib.sha256((RES/'core100_admission.json').read_bytes()).hexdigest(),
                    'final_input_policy_sha256':hashlib.sha256((RES/'core100_final_input_policy.json').read_bytes()).hexdigest(),
                    'tasks_sha256':hashlib.sha256(json.dumps(tasks,sort_keys=True,ensure_ascii=False).encode()).hexdigest()},
        note='Distances recomputed from frozen source intervals. Reference eligibility and human coverage remain explicit. VLM agreement is not generation accuracy; disputed/unreviewed labels are not zeros.')


def csv_bytes(result):
    stream=io.StringIO(newline='');rows=result['outputs']
    fields=list(dict.fromkeys(k for row in rows for k in row))
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    return ('\ufeff'+stream.getvalue()).encode('utf-8')

# FORMAL_BOUNDARY_EVALUATION_V1
_calculate_before_formal_boundary = calculate
def calculate(tasks):
    from formal_boundary_evaluation import attach
    from formal_critical_cohorts import attach as attach_explicit
    from scoped_window_completion import attach_scoped
    return attach(attach_explicit(attach_scoped(_calculate_before_formal_boundary(tasks), tasks), tasks), tasks)
