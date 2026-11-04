"""All100 current boundary connections. No implicit formal admission or relabeling."""
import collections
from input_contract import matches_frozen_input
from workflow import final_annotation
from protocol_rules import observation_evidence_problem


def axes(reference):
    result = []
    if reference['boundary_records']:
        result.append((reference['parameter'], reference))
    for name, axis in reference.get('conditional_axes', {}).items():
        result.append((name, axis))
    seen = set()
    for name, axis in result:
        for boundary in axis['boundary_records']:
            key = (name, boundary['event'], tuple(boundary['bracket']))
            if key not in seen:
                seen.add(key)
                yield name, axis, boundary


def calculate(registry, tasks, policy, admission):
    refs = {r['clip_id']: r for r in registry['cases']}
    assert len(refs) == 100
    by_clip = collections.defaultdict(list)
    for task in tasks:
        by_clip[task['payload']['clip_id']].append(task)
    cases, outputs, boundaries = [], [], []
    formal_refs = admission.get('references', [])
    for clip, ref in sorted(refs.items()):
        own = by_clip[clip]
        records = list(axes(ref))
        events = sorted({b['event'] for _, _, b in records})
        formal_windows = [dict(target_event=r['target_event'], horizon_s=r['horizon_s'],
                               reference_label=r['reference_label'],
                               boundary_interval=r['boundary_interval'])
                          for r in formal_refs if r['clip_id'] == clip]
        for axis_name, axis, boundary in records:
            boundaries.append(dict(clip_id=clip, parameter=axis_name, theta=axis['theta'],
                event=boundary['event'], reference_label=axis['reference_events'][boundary['event']],
                bracket=boundary['bracket'], endpoint_labels=boundary['endpoint_labels'],
                normalized_distance_interval=boundary['distance']['normalized_absolute_interval'],
                distance_bin=boundary['distance']['bin'], normalization_domain=axis['normalization_domain'],
                horizon_s=ref['horizon_s'], reference_video_sha256=ref['reference_video_sha256'],
                endpoint_repeatability=boundary.get('endpoint_repeatability'),
                endpoint_checks_allow_numerical_use=boundary.get('endpoint_repeatability',{}).get('status','reproduced')=='reproduced',
                numerical_only=True, formal_admission=False))
        blockers = []
        if not records:
            blockers.append('recorded_calibration_only' if ref.get('original_calibration_reference') else 'boundary_missing')
        original_ready = ref['status'] == 'distance_ready' and bool(
            ref['boundary_records'] or ref.get('original_calibration_reference') or any(
                a.get('boundary_records') and a.get('binding_kind') != 'verified_supplemental_conditional_local_search'
                for a in ref.get('conditional_axes', {}).values()))
        if (ref.get('parameter') == 'joint_global_configuration' and
                not ref['boundary_records'] and not ref.get('original_calibration_reference')):
            original_path = ref.get('conditional_axes', {}).get('original_G_global_path', {})
            original_ready = bool(ref['status'] == 'distance_ready' and
                original_path.get('boundary_records') and
                original_path.get('original_registered_family') == 'joint_global_configuration')
        if not original_ready:
            blockers.append('original_family_boundary_pending')
        # A previous explicit admission is shown in its own original window;
        # it cannot approve another event/window merely by matching the clip ID.
        if records:
            blockers.append('current_boundary_reference_event_window_admission_pending')
        blockers.append('current_boundary_legal_pair_admission_pending')
        case_outputs = []
        for task in own:
            p = task['payload']; human = final_annotation(task)
            problems = []
            if not matches_frozen_input(p, policy): problems.append('actual_input_mismatch')
            generation = p.get('source', {}).get('generation_metadata', {})
            source_id = generation.get('source_video_id', '')
            if source_id and source_id != ref['sample_id'] and ('__' + ref['sample_id'] + '__') not in source_id:
                problems.append('reference_source_identity_mismatch')
            if generation.get('condition_frame_index') != ref['condition_frame_index']:
                problems.append('condition_frame_mismatch')
            if clip.startswith('T19') and p.get('reference_video_sha256') != ref['reference_video_sha256']:
                problems.append('replacement_reference_not_generated')
            if p['duration_s'] + 1e-6 < ref['horizon_s']: problems.append('native_window_short')
            if abs(p['window_s'] - ref['horizon_s']) > 1e-6: problems.append('registered_window_review_missing')
            if not human: problems.append('final_human_annotation_pending')
            elif human.get('video_sha256') != p['video_sha256'] or human.get('protocol_sha256') != p.get('protocol_sha256'):
                problems.append('human_identity_mismatch')
            verified = p.get('machine', {}).get('media_verified', {})
            media_ok = (verified.get('sha256') == p['video_sha256'] and verified.get('frames') == p['frames']
                        and abs(verified.get('fps', 0) - p['fps']) < .02
                        and verified.get('size') == p.get('remote_media', {}).get('size'))
            if not media_ok: problems.append('native_media_verification_pending')
            if not records: problems.append('event_boundary_not_bound')
            labels = {}; missing_events = []
            for event in events:
                label = (human or {}).get('events', {}).get(event, {}).get('label')
                labels[event] = label
                if event not in p['protocol']['events']: missing_events.append(event)
                elif human and human.get('quality', {}).get('status') == 'pass':
                    if label not in ('yes', 'no'):
                        problems.append('event_binary_observation_missing:' + event)
                    elif observation_evidence_problem(human.get('events', {}).get(event, {}),
                            p['protocol']['events'][event], p, require_actor_ids=False):
                        problems.append('original_event_measurement_evidence_missing:' + event)
            if human and human.get('quality', {}).get('status') not in ('pass', 'failure'):
                problems.append('quality_measurability_pending')
            if missing_events: problems.append('boundary_event_not_in_annotation_contract')
            row = dict(task_id=task['id'], clip_id=clip, model=p['model'], seed=p['seed'],
                prompt_variant=p['prompt_variant'], video_sha256=p['video_sha256'],
                reference_video_sha256=ref['reference_video_sha256'], boundary_events=events,
                observed_event_labels=labels, quality=(human or {}).get('quality', {}).get('status'),
                boundary_event_contract_missing=missing_events, native_duration_s=p['duration_s'],
                annotation_horizon_s=p['window_s'], reference_horizon_s=ref['horizon_s'],
                native_media_verified=media_ok, output_blockers=problems,
                reference_blockers=blockers, numerical_boundary_count=len(records),
                NearAcc=None, PairAcc=None, formal_scores_scope='Existing admitted cohorts remain separate')
            outputs.append(row); case_outputs.append(row)
        cases.append(dict(clip_id=clip, scene=ref['scene_id'], parameter=ref['parameter'],
            theta=ref['theta'], reference_video_sha256=ref['reference_video_sha256'],
            reference_release_version=ref['reference_release_version'], horizon_s=ref['horizon_s'],
            distance_status=ref['status'], reason=ref['reason'], boundary_records=len(records),
            endpoint_recheck_blocked_intervals=sum(b.get('endpoint_repeatability',{}).get('status','reproduced')!='reproduced'for _,_,b in records),
            connected_axes=sorted({name for name, _, _ in records}), boundary_events=events,
            registered_outputs=len(own), final_human=sum(bool(final_annotation(t)) for t in own),
            current_window_output_ready=sum(not r['output_blockers'] for r in case_outputs),
            output_blockers=dict(collections.Counter(b for r in case_outputs for b in r['output_blockers'])),
            reference_blockers=blockers, existing_explicit_admitted_windows=formal_windows,
            NearAcc=None, PairAcc=None))
    scenes = []
    for scene in sorted({r['scene'] for r in cases}):
        own = [r for r in cases if r['scene'] == scene]
        scenes.append(dict(scene=scene, cases=len(own),
            numerical_ready=sum(r['distance_status'] == 'distance_ready' for r in own),
            pending=sum(r['distance_status'] == 'incomplete' for r in own),
            boundary_records=sum(r['boundary_records'] for r in own),
            registered_outputs=sum(r['registered_outputs'] for r in own)))
    return dict(schema='core100-all-boundary-connection-v1', summary=dict(cases=len(cases),
        scenes=len(scenes), registered_outputs=len(outputs), boundary_records=len(boundaries),
        connected_parameter_axes=sum(len(r['connected_axes']) for r in cases),
        endpoint_recheck_blocked_intervals=sum(not r['endpoint_checks_allow_numerical_use']for r in boundaries),
        numerical_ready=registry['summary']['distance_ready'],
        numerical_pending=registry['summary']['incomplete'],
        original_family_ready=registry['summary'].get('original_family_distance_ready'),
        current_window_output_ready=sum(not r['output_blockers'] for r in outputs),
        newly_formal_admitted_cases=0), cases=cases, scenes=scenes, outputs=outputs,
        boundaries=boundaries, note='All100 and every registered parameter axis connected. '
        'No new thresholds or formal admission; old scores, annotations and windows remain unchanged.')
