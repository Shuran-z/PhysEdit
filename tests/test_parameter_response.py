"""Control-group aggregation only; no inference, media processing or refitting."""
import hashlib
import json

import pytest

from scripts.phyediting_gen_summary import report


def cohort(tmp_path, values=(1.62, 3.71, 9.81)):
    items = {str(i): dict(id=str(i), gravity=g, event='T19', camera_id='cam01', object_name='can', split='test_id')
             for i, g in enumerate(values)}
    path = tmp_path / 'group.json'
    path.write_text(json.dumps(dict(group_id='registered_scene_1', varying_parameter='gravity',
                                   fixed_controls=dict(scene='scene_1', solver='locked', intervention='fixed'),
                                   members=[dict(item_id=k, gravity=v['gravity']) for k, v in items.items()])))
    reference = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for item in items.values():
        item['parameter_response_registration'] = reference
    rows = [dict(sample_id=k, item_id=k, model_name='fixture', seed=1, gravity_truth=v['gravity']) for k, v in items.items()]
    predictions = [dict(id=k, gravity=v['gravity'], status='ok') for k, v in items.items()]
    return rows, predictions, items


def test_ideal_response_and_ranking(tmp_path):
    rows, predictions, items = cohort(tmp_path)
    value = report(rows, predictions, items)
    group = value['parameter_response']['groups'][0]
    assert value['registered'] == 3 and value['mean_error_percent'] == 0
    assert group['response_slope'] == pytest.approx(1)
    assert group['ordering_consistency'] == 1 and group['spearman_rho'] == pytest.approx(1)
    assert not group['scientific_group_accuracy_certified']


def test_constant_wrong_response_is_not_correct_ordering(tmp_path):
    rows, predictions, items = cohort(tmp_path)
    for p in predictions:
        p['gravity'] = 1
    group = report(rows, predictions, items)['parameter_response']['groups'][0]
    assert group['response_slope'] == 0 and group['ordering_consistency'] == 0
    assert group['spearman_rho'] is None and group['spearman_reason'] == 'constant_estimated_response'
    assert group['tied_response_pairs'] == 3


@pytest.mark.parametrize('fault', ['at_bound', 'missing', 'input_failure', 'missing_seed_member'])
def test_failed_or_absent_members_never_shrink_control_group(tmp_path, fault):
    rows, predictions, items = cohort(tmp_path)
    if fault == 'at_bound':
        predictions[1]['status'] = 'at_bound'
    elif fault == 'missing':
        predictions.pop(1)
    elif fault == 'input_failure':
        rows[1]['input_failure'] = 'missing_source'
    else:
        rows[1]['seed'] = 2
    value = report(rows, predictions, items)
    assert value['registered'] == 3
    for group in value['parameter_response']['groups']:
        assert group['status'] == 'insufficient_evidence'
        assert group['spearman_rho'] is None and group['ordering_consistency'] is None
        assert group['registered_members'] == 3


@pytest.mark.parametrize('fault', ['hash', 'camera', 'target', 'no_group'])
def test_unverified_group_does_not_erase_registered_denominator(tmp_path, fault):
    rows, predictions, items = cohort(tmp_path)
    if fault == 'hash':
        items['0']['parameter_response_registration']['sha256'] = 'stale'
    elif fault == 'camera':
        items['1']['camera_id'] = 'cam02'
    elif fault == 'target':
        items['0']['gravity'] = 24
    else:
        for item in items.values():
            del item['parameter_response_registration']
    response = report(rows, predictions, items)['parameter_response']
    assert response['registered_samples'] == 3 and len(response['ungrouped']) == 3
    assert response['scored_groups'] == 0


def test_two_levels_allow_pairs_but_not_informative_rho(tmp_path):
    rows, predictions, items = cohort(tmp_path, (1.62, 9.81))
    group = report(rows, predictions, items)['parameter_response']['groups'][0]
    assert group['ordering_consistency'] == 1
    assert group['spearman_rho'] is None and group['spearman_reason'] == 'fewer_than_three_parameter_levels'


def test_low_gravity_results_are_not_posthoc_filtered(tmp_path):
    rows, predictions, items = cohort(tmp_path)
    for p in predictions:
        p['gravity'] *= 0.02
    value = report(rows, predictions, items)
    assert value['scored'] == 3 and value['mean_error_percent'] == pytest.approx(98)
    group = value['parameter_response']['groups'][0]
    assert group['response_slope'] == pytest.approx(0.02)
    assert group['spearman_rho'] == pytest.approx(1)


def test_model_results_are_separately_reported(tmp_path):
    rows, predictions, items = cohort(tmp_path)
    other_rows = [dict(r, sample_id='other'+r['sample_id'], model_name='other') for r in rows]
    other_predictions = [dict(p, id='other'+p['id'], gravity=1) for p in predictions]
    by_model = report(rows+other_rows, predictions+other_predictions, items)['parameter_response']['by_model']
    assert by_model['fixture']['ordering_consistency']['mean'] == 1
    assert by_model['other']['ordering_consistency']['mean'] == 0
