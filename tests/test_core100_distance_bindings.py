import json

import pytest

from physedit import core100_bindings as bindings


def test_active_roster_and_evidence_are_bound():
    data=bindings.load(verify_evidence=True)
    assert sum(data['summary'][s]for s in bindings.STATES)==100
    assert len(data['scenes'])==20
    assert all(sum(r[s]for s in bindings.STATES)==5 for r in data['scenes'])


def test_lookup_does_not_transfer_distance_to_old_video_or_other_window():
    data=bindings.load()
    ref=next(r for r in data['cases']if r['clip_id']=='T19_C01')
    with pytest.raises(ValueError,match='reference_mismatch'):
        bindings.lookup('T19_C01','0'*64,ref['horizon_s'],registry=data)
    with pytest.raises(ValueError,match='window_mismatch'):
        bindings.lookup('T19_C01',ref['reference_video_sha256'],5.,registry=data)
    assert bindings.lookup('T19_C01',ref['reference_video_sha256'],ref['horizon_s'],registry=data)==ref


def test_export_retains100_and_does_not_invent_annotations():
    data=bindings.load();rows=list(bindings.export_rows(data))
    assert len(rows)==100
    assert all(r['ordinary_event_denominator_retained']for r in rows)
    assert all(r['generated_event_labels']is None for r in rows)
    assert any(r['distance_status']=='incomplete'and not r['boundary_records']for r in rows)
    observed=next(r for r in data['cases']if r['clip_id']=='T01_C01')
    assert all(b['interval_kind']=='observed_published_transition'and b['exact_theta_star']is None for b in observed['boundary_records'])


def test_uncertain_interval_is_not_forced_near_and_multiple_boundaries_survive():
    assert bindings.interval_distance(.14,[.0875,.105],.28)['bin']is None
    row=next(r for r in bindings.load()['cases']if r['clip_id']=='T15_C04')
    assert len(row['boundary_records'])==3
    assert {tuple(b['endpoint_labels'])for b in row['boundary_records']}=={(0,1),(1,0)}


def test_changed_reference_or_fabricated_distance_is_rejected(tmp_path):
    data=bindings.load();path=tmp_path/'bad.json'
    data['cases'][0]['reference_video_sha256']='0'*64
    path.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='reference_hash_mismatch'):bindings.load(path)
    data=bindings.load();row=next(r for r in data['cases']if r['status']=='distance_ready')
    row['boundary_records'][0]['distance']['bin']='made_up'
    path.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='distance_value_changed'):bindings.load(path)


def test_sealed_reference_does_not_inherit_production_state():
    data=bindings.load();r=next(r for r in data['cases']if r['clip_id']=='T16_C04')
    assert r['source_state_sha256']=='d9c945d7182c3c51cd9e8a07392f919636f11fe0f3f6768fadf390ea9e4193e3'
    assert r['horizon_s']==5.
    assert next(r for r in data['cases']if r['clip_id']=='T17_C04')['horizon_s']==6.4


def test_existing_scorer_answer_join_preserves_chain_and_inversion():
    data=bindings.load();row=next(r for r in data['cases']if r['clip_id']=='T06_C04')
    answer=dict(point_id='T06_C04',target_event='complete_required_contact_chain',
        events={'complete_required_contact_chain':0,'another_registered_chain_event':1},
        required_order=[['first','second']],reference_admission={'status':'pending'},
        inversion={'status':'not_applicable','reason':'no suitable free-flight segment'})
    new=bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],horizon_s=4.1,registry=data)
    assert new['events']==answer['events']and new['required_order']==answer['required_order']
    assert new['inversion']==answer['inversion']and new['reference_admission']==answer['reference_admission']
    assert 'boundary'not in answer
    from physedit.boundary import distance
    assert distance(new)['bin']=='mid'


def test_original_late_gate_event_recovers_boundary_and_requires_original_window():
    data=bindings.load();row=next(r for r in data['cases']if r['clip_id']=='T05_C04')
    answer=dict(point_id='T05_C04',target_event='gate_passage',events={'gate_passage':0})
    with pytest.raises(ValueError,match='window_mismatch'):
        bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],horizon_s=5.,registry=data)
    new=bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],horizon_s=205/30,registry=data)
    from physedit.boundary import distance
    assert distance(new)['bin']=='far'
    assert new['events']=={'gate_passage':0}
    answer['events']['gate_passage']=1
    with pytest.raises(ValueError,match='labels_conflict'):
        bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],horizon_s=205/30,registry=data)
    positive=next(r for r in data['cases']if r['clip_id']=='T05_C05')
    assert positive['original_reference_review']['first_event_frame']==173
    assert positive['reference_events']['gate_passage']==1


def test_no_flip_is_not_an_exclusion_and_original_axes_are_preserved():
    data=bindings.load();by={r['clip_id']:r for r in data['cases']}
    # A later original-axis search may recover a boundary. A finite no-flip
    # diagnostic must never turn into permanent exclusion of the case.
    assert by['T06_C02']['status'] in ('incomplete','distance_ready')
    assert by['T06_C02']['ordinary_event_denominator_retained']
    assert by['T05_C01']['parameter']=='phone_tray_friction_coefficient'
    assert by['T05_C01']['theta']==.049
    assert isinstance(by['T11_C01']['theta'],dict)
    assert by['T11_C01']['parameter']=='joint_global_configuration'


def test_original_calibration_value_is_recovered_without_inventing_bracket():
    data=bindings.load();row=next(r for r in data['cases']if r['clip_id']=='T02_C01')
    assert row['original_calibration_reference']['value']==.1416407
    assert not row['boundary_records']
    answer=dict(point_id='T02_C01',target_event='C2_signal_displaced_0p05m',events=row['reference_events'])
    new=bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],horizon_s=205/30,registry=data)
    assert new['recorded_reference_distance']['raw_absolute_distance']==pytest.approx(.0354101)
    assert new['boundary']['status']=='recorded_reference'
    from physedit.boundary import distance
    assert distance(new)['bin']is None


def test_missing_boundary_for_one_event_is_not_an_exclusion_or_another_event_score():
    import copy
    data=copy.deepcopy(bindings.load())
    row=next(r for r in data['cases']if r['clip_id']=='T06_C04')
    row['reference_events']['retained_legacy_event']=0
    answer=dict(point_id='T06_C04',target_event='retained_legacy_event',events={'retained_legacy_event':0})
    new=bindings.bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],
        horizon_s=row['horizon_s'],registry=data)
    assert new['boundary']['status']=='unavailable'
    assert new['events']==answer['events']
    from physedit.boundary import distance
    assert distance(new)['bin'] is None


def test_supplemental_axis_does_not_hide_a_completed_original_primary_axis():
    import copy
    data=copy.deepcopy(bindings.load());row=next(r for r in data['cases']if r['clip_id']=='T06_C04')
    row['conditional_axes']={'other_direction':dict(parameter='other_direction',theta=42.)}
    answer=dict(point_id=row['clip_id'],target_event='complete_required_contact_chain',
        events={'complete_required_contact_chain':0},theta=row['theta'])
    kwargs=dict(reference_video_sha256=row['reference_video_sha256'],horizon_s=row['horizon_s'],registry=data)
    with pytest.raises(ValueError,match='axis_required'):bindings.bind_answer(answer,**kwargs)
    result=bindings.bind_answer(answer,axis=row['parameter'],**kwargs)
    assert result['theta']==row['theta'] and result['boundary_axis']==row['parameter']
    from physedit.boundary import distance
    assert distance(result)['bin']=='mid'


def test_supplemental_only_boundary_does_not_complete_original_family():
    row=dict(status='distance_ready', boundary_records=[], conditional_axes={
        'force':dict(boundary_records=[{}], binding_kind='verified_supplemental_conditional_local_search')})
    assert not bindings.original_family_reference_ready(row)
    row['conditional_axes']['original_gap']=dict(boundary_records=[{}],
        binding_kind='original_physics_completed_probe_local_intervals')
    assert bindings.original_family_reference_ready(row)


def test_original_family_summary_accounts_for_all_registered_cases():
    data=bindings.load()
    expected=[r['clip_id']for r in data['cases']if not bindings.original_family_reference_ready(r)]
    assert data['original_family_pending']==expected
    assert data['summary']['original_family_incomplete']==len(expected)
    assert data['summary']['original_family_distance_ready']+len(expected)==100


def test_independent_axis_through_a_global_source_does_not_complete_its_joint_family():
    row=dict(status='distance_ready',parameter='joint_global_configuration',
        boundary_records=[],conditional_axes={'case_edge_margin_m':dict(
            boundary_records=[{}],binding_kind='original_physics_completed_probe_local_intervals')})
    assert not bindings.original_family_reference_ready(row)
    row['conditional_axes']['original_G_global_path']=dict(boundary_records=[{}],
        original_registered_family='joint_global_configuration')
    assert bindings.original_family_reference_ready(row)
