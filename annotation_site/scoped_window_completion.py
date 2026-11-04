"""Attach already accepted T17 window observations; preserve original labels.

Restores the bridge present in the deployed annotation service. These Codex
observations are a separate view, never independent human gold or new truth.
"""
import copy
import hashlib
import json
from pathlib import Path


def coupled_pairs(outputs, pairs):
    by = {(r['model'], r['clip_id'], r['prompt_variant'], r['seed']): r for r in outputs}
    rows = []
    for model in sorted({r['model'] for r in outputs}):
        for pair in pairs:
            a, b = pair
            keys = sorted({(r['prompt_variant'], r['seed']) for r in outputs
                           if r['model'] == model and r['clip_id'] in pair})
            for variant, seed in keys:
                left = by.get((model, a, variant, seed))
                right = by.get((model, b, variant, seed))
                known = (left is not None and right is not None
                         and left['final_correct'] is not None and right['final_correct'] is not None)
                rows.append(dict(model=model, clips=pair, prompt_variant=variant, seed=seed,
                                 coupled_both_correct=int(bool(left['final_correct']) and bool(right['final_correct'])) if known else None,
                                 left_task_id=left['task_id'] if left else None,
                                 right_task_id=right['task_id'] if right else None))
    return rows


def attach_scoped(result, tasks):
    path = Path(__file__).parent/'resources/core100_scoped_observations_6p4.json'
    evidence = json.loads(path.read_text(encoding='utf8'))
    by = {r['task_id']: r for r in evidence['rows']}
    assert len(by) == len(evidence['rows']), 'Duplicate scoped observation id'
    task_by = {t['id']: t for t in tasks}
    in_scope = set(by) & set(task_by)
    cohort = copy.deepcopy(result['admitted_cohort'])
    changed = []
    for row in cohort['outputs']:
        observation = by.get(row['task_id'])
        if observation is None:
            continue
        payload = task_by[row['task_id']]['payload']
        assert observation['video_sha256'] == payload['video_sha256']
        assert observation['protocol_sha256'] == payload['protocol_sha256']
        for key in ('clip_id', 'model', 'seed', 'prompt_variant'):
            assert observation[key] == payload[key], 'Scoped slot identity changed: ' + key
        assert observation['window_s'] == row['horizon_s'] == 6.4
        assert observation['target_event'] == 'can_tissue_box_contact'
        assert observation['native_frames'] == payload['frames']
        assert abs(observation['native_fps'] - payload['fps']) < .02
        assert row['input_matches'] and row['native_horizon_covers']
        assert observation['all_native_frames_through_window_reviewed'] and observation['native_media_verified']
        quality = observation['quality']['status']
        event = observation['event']
        label = event['label'] if event else None
        assert quality in ('pass', 'failure'), 'Scoped quality remains pending'
        if quality == 'pass':
            assert label in ('yes', 'no', 'uncertain', 'not_observed'), 'Scoped event remains pending'
        correct = 0 if quality == 'failure' or label in ('uncertain', 'not_observed') else int(int(label == 'yes') == row['reference_label'])
        row.update(final_correct=correct, final_status='author_authorized_codex_scoped_review',
                   native_media_verified=True, scoped_observation=observation, old_human_annotation_unchanged=True)
        changed.append(row['task_id'])
    assert set(changed) == in_scope
    joint = coupled_pairs(cohort['outputs'], [['T17_C04', 'T17_C05']])
    summaries = []
    for old in cohort['per_model']:
        own = [r for r in cohort['outputs'] if r['model'] == old['model']]
        points = []
        for clip_id in ('T17_C04', 'T17_C05'):
            values = [r for r in own if r['clip_id'] == clip_id]
            known = [r['final_correct'] for r in values if r['final_correct'] is not None]
            points.append(dict(clip_id=clip_id, registered=len(values), known=len(known), correct=sum(known),
                               accuracy=sum(known)/len(values) if values and len(known) == len(values) else None))
        complete = all(p['registered'] and p['known'] == p['registered'] for p in points)
        paired = [r for r in joint if r['model'] == old['model']]
        known_pairs = [r['coupled_both_correct'] for r in paired if r['coupled_both_correct'] is not None]
        summaries.append(dict(model=old['model'], registered=len(own), known=sum(p['known'] for p in points),
                              pending=sum(p['registered']-p['known'] for p in points),
                              NearAcc=sum(p['accuracy'] for p in points)/2 if complete else None,
                              coupled_PairAcc=sum(known_pairs)/len(paired) if paired and len(known_pairs) == len(paired) else None,
                              pair_slots=len(paired), known_pairs=len(known_pairs), independent_PairAcc=None,
                              points=points, status='complete' if complete else old['status']))
    result['completed_scoped_window_scores'] = dict(
        schema='author-authorized-scoped-window-completion-v1',
        scope='T17 original admitted 6.4s contact pair only; old annotation labels and legacy score fields retained',
        observation_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), additional_scoped_observations=len(changed),
        registered_observations_out_of_scope=len(by)-len(in_scope),
        model_assisted_review_not_independent_human_gold=True, per_model=summaries,
        outputs=cohort['outputs'], coupled_pairs=joint)
    result['summary'].update(additional_scoped_window_observations=len(changed),
                             completed_scoped_window_models=sum(m['status'] == 'complete' for m in summaries))
    return result
