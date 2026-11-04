import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'annotation_site'))
from core100_connection import axes, calculate


def registry():
    return json.loads((ROOT / 'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))


def test_all100_axes_connected_without_manufacturing_scores():
    source = registry(); before = copy.deepcopy(source)
    result = calculate(source, [], {}, {'references': []})
    assert len(result['cases']) == 100 and len(result['scenes']) == 20
    assert result['summary']['numerical_ready'] == source['summary']['distance_ready']
    assert result['summary']['newly_formal_admitted_cases'] == 0
    assert all(r['NearAcc'] is None and r['PairAcc'] is None for r in result['cases'])
    assert source == before
    for ref in source['cases']:
        connected = next(r for r in result['cases'] if r['clip_id'] == ref['clip_id'])
        assert set(ref.get('conditional_axes', {})) <= set(connected['connected_axes'])


def test_shared_primary_axis_is_deduplicated_but_other_axes_preserved():
    ref = next(r for r in registry()['cases'] if r['boundary_records'])
    ref['conditional_axes'] = {ref['parameter']: copy.deepcopy(ref), 'other_axis': copy.deepcopy(ref)}
    actual = list(axes(ref))
    assert len(actual) == 2 * len({(b['event'], tuple(b['bracket'])) for b in ref['boundary_records']})


def test_discordant_boundary_is_visible_with_its_numerical_use_blocked():
    source=registry();ref=next(r for r in source['cases']if r['boundary_records'])
    record=ref['boundary_records'][0]
    record['endpoint_repeatability']={'status':'discordant'}
    result=calculate(source,[],{}, {'references':[]})
    bound=next(b for b in result['boundaries']if b['clip_id']==ref['clip_id']and b['bracket']==record['bracket']and b['event']==record['event'])
    assert bound['endpoint_checks_allow_numerical_use'] is False
    assert bound['endpoint_repeatability']['status']=='discordant'
    assert bound['formal_admission'] is False


def test_component_direction_does_not_silently_complete_the_original_joint_path():
    source=registry();ref=next(r for r in source['cases']if r['clip_id']=='T11_C01')
    axis=copy.deepcopy(next(iter(ref['conditional_axes'].values())))
    axis.update(parameter='case_friction_coefficient',original_joint_component=True,
        original_joint_path_recovered=False,binding_kind='original_physics_completed_probe_local_intervals')
    ref['conditional_axes']['case_friction_coefficient']=axis
    result=calculate(source,[],{}, {'references':[]})
    row=next(r for r in result['cases']if r['clip_id']=='T11_C01')
    assert 'case_friction_coefficient' in row['connected_axes']
    assert 'original_family_boundary_pending' in row['reference_blockers']


def test_old_formal_window_does_not_admit_new_window():
    source = registry(); ref = source['cases'][0]
    old = dict(clip_id=ref['clip_id'], target_event='old_event', horizon_s=999,
               reference_label=0, boundary_interval=[1, 2])
    result = calculate(source, [], {}, {'references': [old]})
    row = result['cases'][0]
    assert row['existing_explicit_admitted_windows'][0]['horizon_s'] == 999
    assert row['horizon_s'] != 999
    assert 'current_boundary_reference_event_window_admission_pending' in row['reference_blockers']
    assert row['NearAcc'] is None


def test_numeric_binary_label_without_measurement_is_not_output_ready(monkeypatch):
    import core100_connection as module
    source = registry(); ref = next(r for r in source['cases'] if r['boundary_records'])
    event = ref['boundary_records'][0]['event']
    payload = dict(clip_id=ref['clip_id'], model='test', seed=0, prompt_variant=1,
        video_sha256='v', protocol_sha256='p', duration_s=ref['horizon_s'], window_s=ref['horizon_s'],
        fps=30, frames=210, remote_media={'size': 123},
        source={'generation_metadata': {'condition_frame_index': ref['condition_frame_index']}},
        machine={'media_verified': {'sha256': 'v', 'fps': 30, 'frames': 210, 'size': 123}},
        protocol={'events': {e: {'metric_rule': {'unit': 'm', 'clauses': [], 'combine': 'any'}}
                             for e in ref['reference_events']}})
    annotation = dict(video_sha256='v', protocol_sha256='p', quality={'status': 'pass'},
                      events={e: {'label': 'yes'} for e in ref['reference_events']})
    monkeypatch.setattr(module, 'matches_frozen_input', lambda *args: True)
    monkeypatch.setattr(module, 'final_annotation', lambda task: annotation)
    result = calculate(source, [{'id': 'test', 'payload': payload}], {}, {'references': []})
    assert 'original_event_measurement_evidence_missing:' + event in result['outputs'][0]['output_blockers']
    assert result['summary']['current_window_output_ready'] == 0
