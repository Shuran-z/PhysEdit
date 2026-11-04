"""Explicit reference cohorts; fixed windows and paired seeds are never mixed."""
import collections
import hashlib
import json
from pathlib import Path
from workflow import final_annotation
from input_contract import matches_frozen_input
from protocol_rules import observation_evidence_problem


def replacement_observation(task, reference):
    p = task['payload']; blockers = []
    for key in ('reference_release_version', 'reference_video_sha256', 'condition_sha256'):
        if p.get(key) != reference[key]: blockers.append(key + '_mismatch')
    generation = p.get('source', {}).get('generation_metadata', {})
    variant = p.get('prompt_variant')
    if variant not in (1, 2, 3) or generation.get('prompt') != reference['prompt_variants_en'][variant-1]:
        blockers.append('frozen_prompt_mismatch')
    if generation.get('condition_frame_index') != reference['condition_frame_index']:
        blockers.append('condition_frame_mismatch')
    return finish_observation(task,reference,blockers)


def existing_reference_observation(task, reference, policy, media_records):
    p=task['payload'];g=p.get('source',{}).get('generation_metadata',{});blockers=[]
    if not matches_frozen_input(p,policy):blockers.append('actual_frozen_input_mismatch')
    sid=g.get('source_video_id','')
    if sid!=reference['sample_id'] and ('__'+reference['sample_id']+'__')not in sid:
        blockers.append('reference_source_identity_mismatch')
    if g.get('condition_frame_index')!=reference['condition_frame_index']:blockers.append('condition_frame_mismatch')
    if p.get('reference_video_sha256') and p['reference_video_sha256']!=reference['reference_video_sha256']:
        blockers.append('reference_video_identity_mismatch')
    return finish_observation(task,reference,blockers,media_records)


def finish_observation(task,reference,blockers,media_records=None):
    p=task['payload'];variant=p.get('prompt_variant');input_matches=not blockers
    human = final_annotation(task)
    event = reference['target_event']
    inherited_negative=bool(reference.get('ever_event') and p['window_s']>reference['horizon_s'] and human
        and human.get('quality',{}).get('status')=='pass' and human.get('events',{}).get(event,{}).get('label')=='no')
    if p['duration_s'] + 1e-6 < reference['horizon_s']: blockers.append('native_horizon_insufficient')
    if abs(p['window_s'] - reference['horizon_s']) > 1e-6 and not inherited_negative: blockers.append('exact_window_review_pending')
    verified = (media_records or {}).get(p['video_sha256']) or p.get('machine', {}).get('media_verified', {})
    native_span=(verified['frames']-1)/verified['fps'] if verified.get('frames',0)>0 and verified.get('fps',0)>0 else None
    if native_span is not None and native_span+1e-6<reference['horizon_s'] and 'native_horizon_insufficient'not in blockers:
        blockers.append('native_horizon_insufficient')
    if not (verified.get('sha256') == p['video_sha256'] and verified.get('frames') == p['frames']
            and abs(verified.get('fps', 0) - p['fps']) < .02
            and verified.get('size') == p.get('remote_media', {}).get('size')):
        blockers.append('native_media_verification_pending')
    correct = None
    if event not in p['protocol']['events']: blockers.append('event_contract_mismatch')
    if not human: blockers.append('final_annotation_pending')
    elif human.get('video_sha256') != p['video_sha256'] or human.get('protocol_sha256') != p.get('protocol_sha256'):
        blockers.append('human_identity_mismatch')
    if not blockers:
        quality = human.get('quality', {}).get('status')
        label = human.get('events', {}).get(event, {}).get('label')
        if quality == 'failure': correct = 0
        elif quality == 'pass' and label in ('yes', 'no'):
            problem=observation_evidence_problem(human['events'][event],p['protocol']['events'][event],p,require_actor_ids=False)
            if problem:blockers.append('original_measurement_evidence_pending')
            else:correct = int(int(label == 'yes') == reference['reference_label'])
        elif quality == 'pass' and label in ('uncertain', 'not_observed'): correct = 0
        else: blockers.append('quality_or_event_judgement_pending')
    return dict(task_id=task['id'], clip_id=p['clip_id'], model=p['model'], seed=p['seed'],
        prompt_variant=variant, video_sha256=p['video_sha256'], input_matches=input_matches,
        reference_video_sha256=reference['reference_video_sha256'],
        reference_label=reference['reference_label'], horizon_s=reference['horizon_s'],
        verified_native_span_s=native_span,
        final_correct=correct, blockers=blockers,
        native_media_verified=not any(b=='native_media_verification_pending'for b in blockers),
        window_binding='negative_ever_event_inherited_from_longer_window'if inherited_negative else'exact_window_required',
        historical_input_excluded=not input_matches)


def aggregate(rows, references, pairs, model):
    own = [r for r in rows if r['model'] == model]
    matching = [r for r in own if not r.get('historical_input_excluded')]
    near = [r for r in references if r.get('bin', 'near') == 'near']
    all_points = []
    for ref in references:
        values = [r for r in matching if r['clip_id'] == ref['clip_id']]
        known = [r['final_correct'] for r in values if r['final_correct'] is not None]
        all_points.append(dict(clip_id=ref['clip_id'], registered=len(values), known=len(known),
            reference_label=ref['reference_label'],
            accuracy=sum(known)/len(values) if values and len(known) == len(values) else None))
    near_ids={r['clip_id']for r in near};points=[r for r in all_points if r['clip_id']in near_ids]
    complete = bool(points) and all(p['accuracy'] is not None for p in points)
    balanced = len({p['reference_label'] for p in points}) == 2
    paired = []
    for pair in pairs:
        left, right = pair['clips']
        records = [r for r in matching if r['clip_id'] in (left, right)]
        keys = sorted({(r['prompt_variant'], r['seed']) for r in records})
        for variant, seed in keys:
            a = [r for r in records if r['clip_id'] == left and (r['prompt_variant'],r['seed']) == (variant,seed)]
            b = [r for r in records if r['clip_id'] == right and (r['prompt_variant'],r['seed']) == (variant,seed)]
            known = len(a) == len(b) == 1 and a[0]['final_correct'] is not None and b[0]['final_correct'] is not None
            paired.append(dict(clips=[left,right], prompt_variant=variant, seed=seed,
                               both_correct=int(a[0]['final_correct'] and b[0]['final_correct']) if known else None))
    pair_known = [r['both_correct'] for r in paired if r['both_correct'] is not None]
    registered_pair_ids = {tuple(r['clips']) for r in paired}
    pair_complete = bool(pairs) and all(tuple(p['clips']) in registered_pair_ids for p in pairs) and len(pair_known) == len(paired)
    return dict(model=model, matching_registered=len(matching), historical_excluded=len(own)-len(matching),
        known=sum(r['final_correct'] is not None for r in matching),
        status='awaiting_matching_generation' if not matching else 'complete' if all_points and all(p['accuracy']is not None for p in all_points) else 'coverage_or_review_pending',
        NearAcc=sum(p['accuracy'] for p in points)/len(points) if complete and balanced else None,
        OneSidedNearTargetAccuracy=sum(p['accuracy']for p in points)/len(points)if complete and not balanced else None,
        TargetAccuracy=sum(p['accuracy']for p in all_points)/len(all_points)if all_points and all(p['accuracy']is not None for p in all_points)else None,
        coupled_PairAcc=sum(pair_known)/len(paired) if pair_complete else None,
        independent_PairAcc=None, pair_slots=len(paired), known_pair_slots=len(pair_known),
        points=points,all_reference_points=all_points, paired_outputs=paired,
        blockers=dict(collections.Counter(b for r in matching for b in r.get('blockers', []))))


def calculate(registry, result, tasks, policy=None, media_records=None):
    models = sorted({t['payload']['model'] for t in tasks}); cohorts = []
    for cohort in registry['cohorts']:
        refs = cohort['references']; ids = {r['clip_id'] for r in refs}
        if cohort['scoring_adapter'] == 'existing_scoped_outputs':
            scoped = result.get('completed_scoped_window_scores') or result['admitted_cohort']
            rows = scoped['outputs']
        elif cohort['scoring_adapter']=='strict_replacement_inputs':
            by = {r['clip_id']:r for r in refs}
            rows = [replacement_observation(t, by[t['payload']['clip_id']]) for t in tasks if t['payload']['clip_id'] in ids]
        else:
            by={r['clip_id']:r for r in refs}
            rows=[existing_reference_observation(t,by[t['payload']['clip_id']],policy or {},media_records or {})for t in tasks if t['payload']['clip_id']in ids]
        cohorts.append(dict(cohort_id=cohort['cohort_id'], reference_cases=len(refs),
            near_points=sum(r.get('bin','near')=='near' for r in refs), reference_pairs=len(cohort['pairs']),
            horizon_s=refs[0]['horizon_s'], references=refs, pairs=cohort['pairs'], outputs=rows,
            per_model=[aggregate(rows,refs,cohort['pairs'],m) for m in models]))
    all_outputs=[dict(r,cohort_id=c['cohort_id']) for c in cohorts for r in c['outputs']]
    scene_models=[]
    for scene in sorted({r['clip_id'][:3]for c in cohorts for r in c['references']}):
        refs=[r for c in cohorts for r in c['references']if r['clip_id'].startswith(scene)]
        for model in models:
            selected=[r for r in all_outputs if r['model']==model and r['clip_id'].startswith(scene)and not r.get('historical_input_excluded')]
            known=[r['final_correct']for r in selected if r['final_correct']is not None]
            point_accuracies=[]
            for ref in refs:
                values=[r['final_correct']for r in selected if r['clip_id']==ref['clip_id']]
                point_accuracies.append(sum(values)/len(values)if values and all(x is not None for x in values)else None)
            scene_models.append(dict(scene=scene,model=model,reference_cases=len(refs),registered=len(selected),
                known=len(known),correct=sum(known),pending=len(selected)-len(known),
                TargetAccuracy=sum(point_accuracies)/len(point_accuracies)if point_accuracies and all(x is not None for x in point_accuracies)else None,
                accuracy_on_scored=sum(known)/len(known)if known else None,
                fixed_denominator_bounds=[sum(known)/len(selected),(sum(known)+len(selected)-len(known))/len(selected)]if selected else None))
    return dict(schema='explicit-formal-critical-results-v1', summary=registry['summary'], cohorts=cohorts,
        per_scene_model=scene_models,
        references=[dict(r,cohort_id=c['cohort_id']) for c in cohorts for r in c['references']],
        outputs=all_outputs,
        note='Only explicit admitted cohorts. Windows are scored separately. PairAcc here uses matched '
             'prompt variant and seed; no Cartesian product or independent-seed inference. '
             'Missing new-version generations are N/A, never inherited from old T19 labels.')


def attach(result, tasks):
    root = Path(__file__).parent
    path = root/'resources/core100_formal_cohorts.json'
    registry = json.loads(path.read_text(encoding='utf8'))
    policy=json.loads((root/'resources/core100_final_input_policy.json').read_text(encoding='utf8'))
    media={};media_path=root/'resources/core100_additional_media_verification.json'
    if registry.get('additional_media_registry_sha256'):
        assert hashlib.sha256(media_path.read_bytes()).hexdigest()==registry['additional_media_registry_sha256']
        media={r['sha256']:r for r in json.loads(media_path.read_text(encoding='utf8'))['rows']if r['status']=='verified'}
    result['formal_critical_cohorts'] = calculate(registry, result, tasks,policy,media)
    result['formal_critical_cohorts']['registry_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    registered = {r['clip_id']:r for c in registry['cohorts'] for r in c['references']}
    pairs = [p for c in registry['cohorts'] for p in c['pairs']]
    connection = result.get('core100_connection', {})
    progress_path=root/'resources/core100_reference_observability_progress.json'
    progress={}
    if registry.get('reference_progress_registry_sha256'):
        assert hashlib.sha256(progress_path.read_bytes()).hexdigest()==registry['reference_progress_registry_sha256']
        progress=json.loads(progress_path.read_text(encoding='utf8'))
        result['formal_critical_cohorts']['all100_reference_progress']=progress
    for row in connection.get('cases', []):
        ref = registered.get(row['clip_id'])
        admitted = bool(ref and ref['reference_video_sha256'] == row['reference_video_sha256']
                        and ref['horizon_s'] == row['horizon_s'] and ref['theta'] == row['theta']
                        and (ref['target_event'] in row['boundary_events'] or ref.get('distance_admitted') is False))
        row['current_reference_formal_admitted'] = admitted
        distance_admitted=admitted and ref.get('distance_admitted',True)
        row['current_distance_formal_admitted']=distance_admitted
        media_progress=next((r for r in progress.get('cases',[])if r['clip_id']==row['clip_id']and r['video_sha256']==row['reference_video_sha256']),{})
        row['original_reference_media_audit']=media_progress.get('original_media_audit','not_checked')
        row['reference_progress_reason']=media_progress.get('reference_pending_reason')
        row['current_formal_pair_peers'] = [cid for p in pairs if row['clip_id'] in p['clips']
                                           for cid in p['clips'] if cid != row['clip_id']] if admitted else []
        if distance_admitted:
            row['reference_blockers'] = [b for b in row['reference_blockers']
                if b != 'current_boundary_reference_event_window_admission_pending'
                and not (b == 'current_boundary_legal_pair_admission_pending' and row['current_formal_pair_peers'])]
        elif admitted:
            row['reference_blockers'].append('ordinary_target_admitted_distance_solver_context_pending'
                if row['clip_id']=='T16_C04' else 'ordinary_target_admitted_distance_evidence_pending')
    summary = registry['summary']
    by_case = {r['clip_id']:r for r in connection.get('cases', [])}
    for output in connection.get('outputs', []):
        output['reference_blockers'] = by_case[output['clip_id']]['reference_blockers']
        proof=media.get(output['video_sha256'])
        if proof and proof['frames']==proof['registered_frames']and abs(proof['fps']-proof['registered_fps'])<.02:
            output['native_media_verified']=True
            output['output_blockers']=[b for b in output['output_blockers']if b!='native_media_verification_pending']
    for case in connection.get('cases',[]):
        own=[r for r in connection['outputs']if r['clip_id']==case['clip_id']]
        case['output_blockers']=dict(collections.Counter(b for r in own for b in r['output_blockers']))
        case['current_window_output_ready']=sum(not r['output_blockers']for r in own)
    connection.setdefault('summary',{})['current_window_output_ready']=sum(not r['output_blockers']for r in connection.get('outputs',[]))
    result['summary'].update(current_formal_reference_cases=summary['formally_registered_reference_cases'],
        current_formal_near_points=summary['formally_registered_near_points'],
        current_formal_pairs=summary['formally_registered_pairs'])
    connection.setdefault('summary', {}).update(formal_reference_cases=summary['formally_registered_reference_cases'],
        formal_near_points=summary['formally_registered_near_points'], formal_pairs=summary['formally_registered_pairs'],
        restored_previously_admitted_reference_cases=summary['restored_website_admitted_references'])
    connection['summary']['newly_formal_admitted_cases']=summary.get('newly_admitted_reference_cases',0)
    from scoped_native_completion import attach as attach_scoped_native
    return attach_scoped_native(result, tasks)
