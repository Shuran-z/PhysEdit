"""Versioned formal boundary scoring entry; numerical evidence never grants admission."""
import collections,copy,hashlib,json
from core100_connection import axes
from protocol_rules import observation_evidence_problem
from workflow import final_annotation

def same_admission(ref,name,axis,boundary,entry):
    # The original T17 admission used its sampler family name. Its later
    # canonical parameter spelling denotes the same coordinate; identity,
    # source value, event, window, domain and exact bracket still all match.
    family=name
    if ref['clip_id']in('T17_C04','T17_C05')and name=='can_initial_speed_mps':family='initial_speed'
    return (entry['clip_id']==ref['clip_id']
        and entry['target_event']==boundary['event']
        and entry.get('reference_state_sha256')==ref['source_state_sha256']
        and entry['horizon_s']==ref['horizon_s']
        and entry['family_id']==family and entry['theta']==axis['theta']
        and entry['reference_label']==axis['reference_events'][boundary['event']]
        and entry['boundary_interval']==boundary['bracket']
        and entry['normalization_domain']==axis['normalization_domain']
        and entry.get('visual_observability','').startswith('passed')
        and entry.get('reference_admission','').startswith('admitted'))

def summarize(rows):
    known=[r for r in rows if r['correct']is not None];n=len(rows);k=len(known);success=sum(r['correct']for r in known)
    return dict(registered=n,scored=k,pending=n-k,correct=success,
        accuracy_on_scored=success/k if k else None,
        complete_cohort_accuracy=success/n if n and k==n else None,
        fixed_denominator_bounds=[success/n,(success+n-k)/n]if n else None,
        blockers=dict(collections.Counter(b for r in rows for b in r['blockers'])))

def explicit_admission(ref,name,axis,boundary,entry):
    family='impact_eccentricity_contact'if ref['clip_id'].startswith('T19')and name=='impact_eccentricity_m'else name
    return bool(entry.get('distance_admitted',True)
        and entry['clip_id']==ref['clip_id'] and entry['family_id']==family
        and entry['reference_video_sha256']==ref['reference_video_sha256']
        and entry.get('reference_state_sha256')==ref['source_state_sha256']
        and entry['reference_release_version']==ref['reference_release_version']
        and entry['target_event']==boundary['event'] and entry['horizon_s']==ref['horizon_s']
        and entry['theta']==axis['theta'] and entry['reference_label']==axis['reference_events'][boundary['event']]
        and (entry['boundary_interval']==boundary['bracket'] or boundary['bracket']in entry.get('verified_original_boundary_intervals',[]))
        and entry['normalization_span']==axis['normalization_span']
        and (not entry.get('normalization_domain')or entry['normalization_domain']==axis['normalization_domain'])
        and (entry.get('end_frame_index')is None or entry['end_frame_index']==ref['end_frame_index']))

def attach(result,tasks):
    registry=result['active_distance_registry'];admission=result.get('reference_window_admission')or{}
    admission_refs=admission.get('references',[]);connections=result['core100_connection']
    connected={r['task_id']:r for r in connections['outputs']};by_clip=collections.defaultdict(list)
    for task in tasks:by_clip[task['payload']['clip_id']].append(task)
    extra=result.get('formal_critical_cohorts',{})
    explicit=[r for c in extra.get('cohorts',[])if c['cohort_id']!='t17-contact-h6p4' for r in c['references']]
    replacement_outputs={r['task_id']:r for c in extra.get('cohorts',[])if c['cohort_id']!='t17-contact-h6p4' for r in c['outputs']}
    references=[];outputs=[]
    for ref in registry['cases']:
        for name,axis,boundary in axes(ref):
            event=boundary['event'];bucket=boundary['distance']['bin']
            admitted=any(same_admission(ref,name,axis,boundary,a)for a in admission_refs)
            restored=any(explicit_admission(ref,name,axis,boundary,e) for e in explicit)
            admitted=admitted or restored
            key=hashlib.sha256(json.dumps([ref['reference_video_sha256'],ref['source_state_sha256'],name,event,ref['horizon_s'],axis['theta'],boundary['bracket']],sort_keys=True).encode()).hexdigest()
            blocks=[]if admitted else['reference_event_axis_window_admission_pending']
            if bucket is None:blocks.append('distance_interval_crosses_bin')
            references.append(dict(reference_id=key,clip_id=ref['clip_id'],axis=name,event=event,theta=axis['theta'],
                bracket=boundary['bracket'],distance_bin=bucket,normalized_distance_interval=boundary['distance']['normalized_absolute_interval'],
                reference_label=axis['reference_events'][event],reference_video_sha256=ref['reference_video_sha256'],
                source_state_sha256=ref['source_state_sha256'],reference_release_version=ref['reference_release_version'],
                horizon_s=ref['horizon_s'],formal_reference_admitted=admitted,reference_blockers=blocks,
                supplemental_axis=axis.get('binding_kind')=='verified_supplemental_conditional_local_search',solver=axis.get('solver')))
            for task in by_clip[ref['clip_id']]:
                payload=task['payload'];human=final_annotation(task);existing=connected[task['id']]
                # Union-of-all-events diagnostics must not reject a valid selected event.
                problems=[p for p in existing['output_blockers']if not p.startswith(('event_binary_observation_missing:','original_event_measurement_evidence_missing:'))and p not in('boundary_event_not_in_annotation_contract','event_boundary_not_bound')]
                label=(human or{}).get('events',{}).get(event,{});quality=(human or{}).get('quality',{}).get('status')
                if event not in payload['protocol']['events']:problems.append('selected_event_not_in_annotation_contract')
                elif human and quality=='pass':
                    if label.get('label')not in('yes','no','uncertain','not_observed'):problems.append('selected_event_observation_missing')
                    elif label.get('label')in('yes','no')and observation_evidence_problem(label,payload['protocol']['events'][event],payload,require_actor_ids=False):problems.append('selected_event_measurement_evidence_missing')
                correct=None
                if not problems:
                    if quality=='failure':correct=0
                    elif quality=='pass'and label.get('label')in('yes','no'):correct=int(int(label['label']=='yes')==axis['reference_events'][event])
                    elif quality=='pass'and label.get('label')in('uncertain','not_observed'):correct=0
                    else:problems.append('quality_or_event_pending')
                if restored:
                    strict=replacement_outputs.get(task['id'])
                    correct=strict['final_correct'] if strict else None
                    problems=list(strict['blockers']) if strict else ['strict_replacement_observation_missing']
                    if strict and strict.get('scoped_review_id'):
                        quality=strict.get('quality');label={'label':strict.get('observed_label')}
                outputs.append(dict(task_id=task['id'],clip_id=ref['clip_id'],model=payload['model'],prompt_variant=payload['prompt_variant'],seed=payload['seed'],
                    reference_id=key,axis=name,event=event,distance_bin=bucket,quality=quality,observed_label=label.get('label'),
                    diagnostic_correct=correct,correct=correct if admitted and not blocks else None,
                    blockers=sorted(set(problems+blocks)),output_blockers=problems,reference_blockers=blocks,
                    native_media_verified=existing['native_media_verified'],video_sha256=payload['video_sha256'],
                    reference_video_sha256=ref['reference_video_sha256'],reference_horizon_s=ref['horizon_s'],annotation_horizon_s=payload['window_s']))
    for row in outputs:
        proof=replacement_outputs.get(row['task_id'])
        if proof and any(e['clip_id']==row['clip_id'] and e['target_event']==row['event'] for e in explicit):
            row['native_media_verified']=proof.get('native_media_verified',False)
            if proof.get('scoped_review_id'):
                row['observation_source']=proof['observation_source']
                row['scoped_review_id']=proof['scoped_review_id']
                row['scoped_observation_separate_from_original_labels']=True
    # These are author-accepted observations in the admitted 6.4s window. The
    # shared seed/variant pairing is coupled, never independent PairAcc.
    scoped=result.get('completed_scoped_window_scores');source='author_accepted_scoped_window'
    if scoped is None:scoped=result.get('admitted_cohort',{});source='original_admitted_cohort'
    accepted={r['task_id']:r for r in scoped.get('outputs',[])}
    for row in outputs:
        observation=accepted.get(row['task_id'])
        if not observation or row['reference_blockers']:continue
        if observation['clip_id']!=row['clip_id']or observation['horizon_s']!=row['reference_horizon_s']:continue
        if row['event']!='can_tissue_box_contact' or observation.get('final_correct')is None:continue
        if not observation.get('native_media_verified')or not observation.get('input_matches'):continue
        rest=[b for b in row['output_blockers']if b not in ('registered_window_review_missing','final_human_annotation_pending','human_identity_mismatch','quality_measurability_pending','selected_event_observation_missing','selected_event_measurement_evidence_missing')]
        if rest:continue
        row.update(correct=observation['final_correct'],diagnostic_correct=observation['final_correct'],blockers=[],
            output_blockers=[],observation_source=observation['final_status'],scoped_observation_separate_from_original_labels=True)
    model_scores=[]
    for model in sorted({t['payload']['model']for t in tasks}):
        cohort=next((r for r in scoped.get('per_model',[])if r['model']==model),{})
        own=[r for r in outputs if r['model']==model]
        model_scores.append(dict(model=model,formal_scope='T17_C04/T17_C05 original admitted contact, 6.4s',
            NearAcc=cohort.get('NearAcc'),CoupledPairAcc=cohort.get('coupled_PairAcc'),IndependentPairAcc=None,
            registered=cohort.get('registered',0),scored=cohort.get('known',cohort.get('final_known',0)),pending=cohort.get('pending'),
            full_core100_NearAcc=None,full_core100_PairAcc=None,
            axis_event_coverage={bucket:summarize([r for r in own if r['distance_bin']==bucket])for bucket in('near','mid','far')},
            score_source=source))
    summary=dict(registered_outputs=len(tasks),numerical_reference_cases=registry['summary']['distance_ready'],numerical_pending_cases=registry['summary']['incomplete'],
        connected_axis_event_references=len(references),formal_admitted_axis_event_references=sum(r['formal_reference_admitted']for r in references),
        registered_axis_event_outputs=len(outputs),formal_scored_axis_event_outputs=sum(r['correct']is not None for r in outputs),
        formal_reference_pending_cases=len({r['clip_id']for r in references if not r['formal_reference_admitted']}),
        completed_admitted_scope_models=sum(r['NearAcc']is not None for r in model_scores),
        full_core100_NearAcc=None,full_core100_PairAcc=None)
    result['formal_boundary_evaluation']=dict(schema='core100-formal-boundary-evaluation-v1',reference_release_version=registry['reference_release_version'],
        summary=summary,per_model=model_scores,references=references,outputs=outputs,
        coupled_pair_outputs=scoped.get('coupled_pairs',[]),source_observation_sha256=scoped.get('observation_sha256'),
        definition=dict(NearAcc='Macro mean of target-event accuracy on the two admitted near points; fixed registered outputs, pending never zero.',
            CoupledPairAcc='Both endpoints correct at the same registered prompt variant and seed; not independent repetitions.',
            full_core100_scores='Pending until matching reference, selected axis, event, native window and accepted observations are admitted.',
            supplemental_axes='Separate conditional slices; never minimize over axes or silently replace the original coordinate.'),
        original_human_labels_changed=False,old_score_fields_changed=False)
    result['formal_boundary_evaluation']['explicit_formal_cohorts']=extra
    result['formal_boundary_evaluation']['current_per_scene_model']=extra.get('per_scene_model',[])
    result['formal_boundary_evaluation']['summary'].update(current_formal_near_points=extra.get('summary',{}).get('formally_registered_near_points'),current_formal_pairs=extra.get('summary',{}).get('formally_registered_pairs'))
    return result
