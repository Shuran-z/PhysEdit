import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'annotation_site'))
import scoped_window_completion as bridge


@pytest.fixture
def case(tmp_path, monkeypatch):
    source = json.loads((ROOT/'annotation_site/resources/core100_scoped_observations_6p4.json').read_text(encoding='utf8'))
    observation = copy.deepcopy(source['rows'][0])
    evidence = {**source, 'rows': [observation]}
    (tmp_path/'resources').mkdir()
    path = tmp_path/'resources/core100_scoped_observations_6p4.json'
    path.write_text(json.dumps(evidence), encoding='utf8')
    monkeypatch.setattr(bridge, '__file__', str(tmp_path/'scoped_window_completion.py'))
    payload = {k: observation[k] for k in ('clip_id', 'model', 'seed', 'prompt_variant', 'video_sha256', 'protocol_sha256')}
    payload.update(frames=observation['native_frames'], fps=observation['native_fps'])
    tasks = [dict(id=observation['task_id'], payload=payload, annotations={'old': 'preserved'})]
    left = dict(task_id=observation['task_id'], clip_id='T17_C04', model=payload['model'],
                prompt_variant=payload['prompt_variant'], seed=0, horizon_s=6.4,
                input_matches=True, native_horizon_covers=True, reference_label=0, final_correct=None)
    right = {**left, 'task_id': 'other', 'clip_id': 'T17_C05', 'reference_label': 1, 'final_correct': 1}
    result = dict(summary={}, admitted_cohort=dict(outputs=[left, right], per_model=[dict(model=payload['model'], status='pending_reviews')]),
                  legacy_scores={'unchanged': True})
    return path, evidence, tasks, result


def test_restores_only_scoped_view_and_preserves_tasks_and_legacy(case):
    _, _, tasks, result = case
    before_tasks = copy.deepcopy(tasks)
    before_cohort = copy.deepcopy(result['admitted_cohort'])
    bridge.attach_scoped(result, tasks)
    scoped = result['completed_scoped_window_scores']
    assert scoped['additional_scoped_observations'] == 1
    assert scoped['outputs'][0]['final_correct'] == 0
    assert scoped['per_model'][0]['NearAcc'] == .5
    assert scoped['per_model'][0]['coupled_PairAcc'] == 0
    assert scoped['per_model'][0]['independent_PairAcc'] is None
    assert scoped['model_assisted_review_not_independent_human_gold']
    assert tasks == before_tasks and result['admitted_cohort'] == before_cohort
    assert result['legacy_scores'] == {'unchanged': True}


@pytest.mark.parametrize('key,value', [('video_sha256', 'bad'), ('protocol_sha256', 'bad'),
                                      ('window_s', 5.0), ('native_frames', 1), ('native_fps', 1),
                                      ('seed', 1), ('prompt_variant', 1)])
def test_rejects_wrong_media_slot_or_window(case, key, value):
    path, evidence, tasks, result = case
    assert evidence['rows'][0][key] != value
    evidence['rows'][0][key] = value
    path.write_text(json.dumps(evidence), encoding='utf8')
    with pytest.raises(AssertionError):
        bridge.attach_scoped(result, tasks)
    assert 'completed_scoped_window_scores' not in result


def test_missing_label_does_not_become_zero(case):
    path, evidence, tasks, result = case
    evidence['rows'][0]['quality']['status'] = 'pass'
    evidence['rows'][0]['event'] = None
    path.write_text(json.dumps(evidence), encoding='utf8')
    with pytest.raises(AssertionError, match='event remains pending'):
        bridge.attach_scoped(result, tasks)


def test_partial_task_scope_does_not_create_missing_observations(case):
    _, _, _, result = case
    result['admitted_cohort'] = dict(outputs=[], per_model=[])
    bridge.attach_scoped(result, [])
    scoped = result['completed_scoped_window_scores']
    assert scoped['outputs'] == [] and scoped['additional_scoped_observations'] == 0
    assert scoped['registered_observations_out_of_scope'] == 1


def test_different_seeds_do_not_form_a_coupled_pair(case):
    _, _, _, result = case
    rows = result['admitted_cohort']['outputs']
    rows[0]['final_correct'] = 1
    rows[1]['seed'] = 1
    pairs = bridge.coupled_pairs(rows, [['T17_C04', 'T17_C05']])
    assert len(pairs) == 2 and all(p['coupled_both_correct'] is None for p in pairs)
