"""Separate, provenance-bound native-window reviews; never edit task annotations."""
import collections
import copy
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def registered_pair_results(formal):
    """Every pre-registered pair is shown, including incomplete pairs.

    Context-specific results do not replace the full-scene denominator.
    """
    from formal_critical_cohorts import aggregate
    output = []
    for cohort in formal['cohorts']:
        for pair in cohort['pairs']:
            ids = set(pair['clips'])
            refs = [r for r in cohort['references'] if r['clip_id'] in ids]
            assert len(refs) == 2 and {r['reference_label'] for r in refs} == {0, 1}
            rows = [r for r in cohort['outputs'] if r['clip_id'] in ids]
            models = sorted({m['model'] for m in cohort['per_model']})
            for model in models:
                score = aggregate(rows, refs, [pair], model)
                output.append(dict(cohort_id=cohort['cohort_id'], pair_id=pair['pair_id'],
                    clips=pair['clips'], model=model, horizon_s=refs[0]['horizon_s'],
                    registered=score['matching_registered'], scored=score['known'],
                    NearAcc=score['NearAcc'], coupled_PairAcc=score['coupled_PairAcc'],
                    pair_slots=score['pair_slots'], known_pair_slots=score['known_pair_slots'],
                    status=score['status'],
                    scope='pre_registered_context_pair_only_not_full_scene_or_Core100',
                    independent_PairAcc=None))
    return output


def review_problem(record, reference, task=None, root=None):
    for key in ('clip_id', 'reference_video_sha256', 'target_event', 'horizon_s'):
        if record[key] != reference[key]: return key + '_mismatch'
    if record['reviewer_type'] != 'Codex_visual_review_not_independent_human_gold':
        return 'reviewer_provenance_missing'
    media = record['media']
    if media['sha256'] != record['video_sha256']: return 'native_video_mismatch'
    if (media['frames']-1)/media['fps']+1e-6 < reference['horizon_s']: return 'native_horizon_insufficient'
    if record['end_frame'] != int(reference['horizon_s']*media['fps']+1e-6): return 'frame_window_mismatch'
    if not record.get('artifacts'): return 'review_artifact_missing'
    for item in record['artifacts']:
        if any(i < 0 or i > record['end_frame'] for i in item['frames']): return 'witness_outside_window'
        if root is not None:
            p = (root/item['path']).resolve()
            if not p.is_relative_to(root.resolve()) or not p.is_file(): return 'review_artifact_unavailable'
            if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']: return 'review_artifact_changed'
    if task is not None:
        p = task['payload']
        if p['video_sha256'] != record['video_sha256']: return 'old_task_video_mismatch'
        if p['protocol_sha256'] != record['protocol_sha256']: return 'old_task_protocol_mismatch'
        if digest(p['protocol']['events'][record['target_event']]) != record['event_definition_sha256']:
            return 'old_event_definition_mismatch'
        if p['prompt_variant'] != record['prompt_variant'] or p['seed'] != record['seed']: return 'old_slot_mismatch'
    else:
        if record['reference_release_version'] != reference['reference_release_version']: return 'release_mismatch'
        if record['condition_sha256'] != reference['condition_sha256']: return 'condition_mismatch'
        if record['condition_frame_index'] != reference['condition_frame_index']: return 'condition_frame_mismatch'
        variant = record['prompt_variant']
        if variant not in (1, 2, 3): return 'prompt_variant_invalid'
        text = reference['prompt_variants_en'][variant-1]
        if record['prompt_sha256'] != hashlib.sha256(text.encode()).hexdigest(): return 'prompt_mismatch'
        if record['generation_receipt']['sha256'] != record['video_sha256']: return 'generation_receipt_mismatch'
        for key in ('prompt_sha256', 'condition_sha256', 'reference_video_sha256', 'reference_release_version'):
            if record['generation_receipt'][key] != record[key]: return 'generation_receipt_' + key + '_mismatch'
    if record['decision']['quality'] == 'failure':
        if not record['decision'].get('failure_type') or not record['decision'].get('reason'): return 'failure_evidence_missing'
        if not any(any(n+1 in a['frames'] for n in a['frames']) for a in record['artifacts']):
            return 'adjacent_witness_missing'
    return None


def apply(result, tasks, registry, root=None):
    """Update current explicit cohorts only; keep legacy scores and DB tasks intact."""
    formal = result['formal_critical_cohorts']
    if formal.get('scoped_native_completion', {}).get('review_registry_sha256') == digest(registry): return result
    task_by = {t['id']:t for t in tasks}
    reference_by = {r['clip_id']:r for r in formal['references']}
    cohort_by = {r['clip_id']:c for c in formal['cohorts'] for r in c['references']}
    receipts = []
    from formal_critical_cohorts import aggregate
    for record in registry['reviews']:
        ref = reference_by.get(record['clip_id'])
        if ref is None: continue  # No review creates a new reference admission.
        task = None if record['kind'] == 'supplemental_generation' else task_by.get(record['id'])
        if record['kind'] != 'supplemental_generation' and task is None: continue
        problem = review_problem(record, ref, task, root)
        if problem: raise ValueError(record['id'] + ': ' + problem)
        cohort = cohort_by[record['clip_id']]
        if task:
            row = next((r for r in cohort['outputs'] if r['task_id'] == record['id']), None)
            if row is None or not row['input_matches'] or row.get('historical_input_excluded'): continue
        else:
            if any(r['task_id'] == record['id'] for r in cohort['outputs']): raise ValueError('duplicate supplemental id')
            row = dict(task_id=record['id'], clip_id=record['clip_id'], model=record['model'], seed=record['seed'],
                prompt_variant=record['prompt_variant'], video_sha256=record['video_sha256'], input_matches=True,
                historical_input_excluded=False, reference_video_sha256=ref['reference_video_sha256'],
                reference_label=ref['reference_label'], horizon_s=ref['horizon_s'], final_correct=None, blockers=[],
                supplemental_new_version_generation=True)
            cohort['outputs'].append(row)
        before = copy.deepcopy(row)
        # The source T19 protocol sends uncertain grazing contact to review.
        # Never silently turn it into a negative event, or a known zero.
        known_failure = record['decision']['quality'] == 'failure'
        row.update(final_correct=0 if known_failure else None,
            blockers=[] if known_failure else [record['decision']['pending_reason']],
            native_media_verified=True, verified_native_span_s=(record['media']['frames']-1)/record['media']['fps'],
            window_binding='separate_exact_native_window_review',
            observation_source=record['reviewer_type'], scoped_review_id=record['id'],
            original_human_labels_changed=False, observed_label=record['decision'].get('event_label'),
            quality=record['decision']['quality'], review_reason=record['decision']['reason'])
        receipts.append(dict(id=record['id'], previous_current_row=before if task else None,
            new_final_correct=row['final_correct'], blockers=row['blockers']))
    models = sorted({t['payload']['model'] for t in tasks} | {r['model'] for r in registry['reviews']})
    for c in formal['cohorts']:
        c['per_model'] = [aggregate(c['outputs'], c['references'], c['pairs'], m) for m in models]
    formal['outputs'] = [dict(r, cohort_id=c['cohort_id']) for c in formal['cohorts'] for r in c['outputs']]
    scene_models = []
    for scene in sorted({r['clip_id'][:3] for r in formal['references']}):
        refs = [r for r in formal['references'] if r['clip_id'].startswith(scene)]
        for model in models:
            rows = [r for r in formal['outputs'] if r['clip_id'].startswith(scene) and r['model']==model and not r.get('historical_input_excluded')]
            values = [r['final_correct'] for r in rows if r['final_correct'] is not None]
            points = []
            for ref in refs:
                own = [r['final_correct'] for r in rows if r['clip_id']==ref['clip_id']]
                points.append(sum(own)/len(own) if own and all(v is not None for v in own) else None)
            scene_models.append(dict(scene=scene, model=model, reference_cases=len(refs), registered=len(rows),
                known=len(values), correct=sum(values), pending=len(rows)-len(values),
                TargetAccuracy=sum(points)/len(points) if points and all(v is not None for v in points) else None,
                accuracy_on_scored=sum(values)/len(values) if values else None,
                fixed_denominator_bounds=[sum(values)/len(rows),(sum(values)+len(rows)-len(values))/len(rows)] if rows else None))
    formal['per_scene_model'] = scene_models
    formal['scoped_native_completion'] = dict(review_registry_sha256=digest(registry), reviewed=len(receipts),
        supplemental_generations=sum(r['kind']=='supplemental_generation' for r in registry['reviews']),
        scored=sum(r['new_final_correct'] is not None for r in receipts),
        pending=sum(r['new_final_correct'] is None for r in receipts), receipts=receipts,
        original_human_labels_changed=False, historical_results_preserved=True,
        note='Separate Codex native-window observations, not independent human gold. Unresolved T19 contact and uncertified T05 metric estimates remain pending, never filled as zero.')
    return result


def attach(result, tasks):
    root = Path(__file__).parent
    path = root/'resources/scoped_native_completion_20261101.json'
    if not path.exists(): return result
    apply(result, tasks, json.loads(path.read_text(encoding='utf8')), root)
    formal = result['formal_critical_cohorts']
    formal['registered_pair_results'] = registered_pair_results(formal)
    boundary = result.get('formal_boundary_evaluation')
    if boundary is not None:
        # Current event table has a separate generation denominator; legacy
        # T17 NearAcc/PairAcc fields stay unchanged.
        boundary['explicit_formal_cohorts'] = formal
        boundary['current_per_scene_model'] = formal['per_scene_model']
        boundary['scoped_native_completion'] = formal['scoped_native_completion']
    return result
