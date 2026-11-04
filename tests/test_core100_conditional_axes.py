import copy
import json

import pytest

from physedit import core100_bindings as bindings


def test_multiaxis_requires_explicit_selection_and_preserves_human_answer():
    data=bindings.load(verify_evidence=True)
    row=next(x for x in data['cases']if x['clip_id']=='T14_C03')
    assert row['legacy_primary_axis']['parameter']=='channel_throat_width_m'
    assert row['parameter']=='channel_throat_width_m'and row['theta']==.0325
    answer=dict(point_id='T14_C03',target_event='passed_channel',
        events={'passed_channel':1,'terminal_contact_after_full_exit':1},
        required_order=[['exit','contact']],reference_admission={'status':'pending'})
    original=copy.deepcopy(answer)
    kwargs=dict(reference_video_sha256=row['reference_video_sha256'],horizon_s=5.,registry=data)
    with pytest.raises(ValueError,match='axis_required'):
        bindings.bind_answer(answer,**kwargs)
    result=bindings.bind_answer(answer,axis='marker_initial_yaw_deg',**kwargs)
    assert result['theta']==4.5 and result['boundary_axis']=='marker_initial_yaw_deg'
    assert result['events']==answer['events']and result['required_order']==answer['required_order']
    assert result['reference_admission']=={'status':'pending'}and answer==original
    with pytest.raises(ValueError,match='unknown_or_incomplete_axis'):
        bindings.bind_answer(answer,axis='unregistered_axis',**kwargs)
    wrong=dict(answer,theta=.0325)
    with pytest.raises(ValueError,match='parameter_value_conflict'):
        bindings.bind_answer(wrong,axis='marker_initial_yaw_deg',**kwargs)


def test_each_axis_keeps_its_scale_and_event_intervals():
    data=bindings.load();row=next(x for x in data['cases']if x['clip_id']=='T14_C03')
    axes=row['conditional_axes']
    yaw=axes['marker_initial_yaw_deg'];impulse=axes['trigger_impulse_magnitude_Ns']
    assert yaw['normalization_span']==8 and impulse['normalization_span']==pytest.approx(.022554)
    assert len(yaw['boundary_records'])==len(impulse['boundary_records'])==2
    assert {b['distance']['bin']for b in yaw['boundary_records']}=={'mid'}
    assert {b['distance']['bin']for b in impulse['boundary_records']}=={'far'}
    exported=next(x for x in bindings.export_rows(data)if x['clip_id']=='T14_C03')
    assert exported['axis_selection_required']and len(exported['conditional_axes'])>=2
    assert exported['generated_event_labels']is None


def test_joint_answer_keeps_full_source_vector_when_selecting_a_scalar_axis():
    data=bindings.load(verify_evidence=True)
    row=next(x for x in data['cases']if x['clip_id']=='T11_C01')
    name=next(iter(row['conditional_axes']));axis=row['conditional_axes'][name]
    event=axis['boundary_records'][0]['event']
    answer=dict(point_id=row['clip_id'],theta=copy.deepcopy(row['theta']),
        target_event=event,events=copy.deepcopy(row['reference_events']))
    before=copy.deepcopy(answer)
    kwargs=dict(reference_video_sha256=row['reference_video_sha256'],horizon_s=row['horizon_s'],registry=data,axis=name)
    result=bindings.bind_answer(answer,**kwargs)
    assert result['theta']==axis['theta'] and result['joint_source_vector']==row['theta']
    assert result['events']==answer['events'] and answer==before
    answer['theta']['case_friction_coefficient']+=.01
    with pytest.raises(ValueError,match='joint_parameter_vector_conflict'):
        bindings.bind_answer(answer,**kwargs)


def test_modified_conditional_distance_or_source_value_is_rejected(tmp_path):
    data=bindings.load();path=tmp_path/'tampered.json'
    row=next(x for x in data['cases']if x['clip_id']=='T14_C03')
    row['conditional_axes']['marker_initial_yaw_deg']['theta']=.0325
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='source_value_changed'):bindings.load(path)
    data=bindings.load();row=next(x for x in data['cases']if x['clip_id']=='T14_C03')
    row['conditional_axes']['trigger_impulse_magnitude_Ns']['boundary_records'][0]['distance']['bin']='near'
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='distance_value_changed'):bindings.load(path)


def test_legacy_registry_and_other99_records_are_preserved():
    previous=bindings.ROOT/'review/core100_remaining15_followup_20261031/integration_backup_before_t14/core100_distance_bindings_v1.json'
    old=bindings.load(previous,verify_evidence=True);new=bindings.load(verify_evidence=True)
    # Replay this sealed update in isolation: later legitimate completions in
    # the live registry must not invalidate the preservation check.
    from scripts.apply_core100_completion_updates import apply_updates
    supplement=json.loads((bindings.ROOT/'review/core100_remaining15_followup_20261031/t14_unified_binding_update.json').read_text(encoding='utf8'))
    cases={x['clip_id']:copy.deepcopy(x)for x in old['cases']}
    apply_updates(cases,supplement,bindings.ROOT,{})
    assert old['summary']['distance_ready']==85
    assert sum(x['status']=='distance_ready'for x in cases.values())==86
    assert [x for x in old['cases']if x['clip_id']!='T14_C03']==[x for x in cases.values()if x['clip_id']!='T14_C03']
    current=next(x for x in new['cases']if x['clip_id']=='T14_C03')
    assert cases['T14_C03']['legacy_primary_axis']==current['legacy_primary_axis']
    for axis in ['marker_initial_yaw_deg','trigger_impulse_magnitude_Ns']:
        assert cases['T14_C03']['conditional_axes'][axis]==current['conditional_axes'][axis]
    assert new['summary']['generated_model_scores_computed']is False
