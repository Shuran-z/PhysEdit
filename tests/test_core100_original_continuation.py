import copy
import hashlib
import json

import pytest

from scripts.collect_core100_original_continuation import candidate_update
from scripts.collect_core100_original_continuation import has_opposite_receipt_labels


def test_candidate_prefilter_never_admits_or_excludes_a_uniform_scan():
    probes=[dict(labels={'event':1}),dict(labels={'event':1})]
    assert not has_opposite_receipt_labels(probes,{'event':1})
    probes.append(dict(labels={'event':0}))
    assert has_opposite_receipt_labels(probes,{'event':1})


def test_original_source_findings_do_not_admit_exclude_or_relabel_a_case():
    from scripts.build_core100_distance_bindings import apply_original_search_trace
    row,_=example();row['reason']='old';before=copy.deepcopy(row)
    trace={k:copy.deepcopy(row[k])for k in ['clip_id','sample_id','reference_video_sha256','horizon_s','reference_events']}
    trace['finding']='An older search has another gravity; the current boundary is still unresolved.'
    apply_original_search_trace({row['clip_id']:row},dict(cases=[trace]))
    assert row['status']=='incomplete' and row['reference_events']==before['reference_events']
    assert row['theta']==before['theta'] and 'boundary_records'not in row
    trace['reference_video_sha256']='wrong'
    with pytest.raises(ValueError,match='identity_or_event_mismatch'):
        apply_original_search_trace({row['clip_id']:row},dict(cases=[trace]))


def test_candidate_prefilter_sends_unknown_event_labels_to_full_verification():
    assert has_opposite_receipt_labels([dict(labels={})],{'event':1})
    assert has_opposite_receipt_labels([dict(labels={'event':None})],{'event':1})


def test_candidate_prefilter_does_not_treat_repeat_disagreement_as_a_boundary():
    probes=[dict(labels={'event':1}),dict(labels={'event':0},source_repeat=True)]
    assert not has_opposite_receipt_labels(probes,{'event':1})


def test_uniform_full_window_passage_labels_do_not_hide_prefix_boundaries():
    probes=[dict(labels={'gate_passage':1}),dict(labels={'gate_passage':1})]
    assert has_opposite_receipt_labels(probes,{'gate_passage':0},shorter_gate_window=True)
    probes=[dict(labels={'gate_passage':0}),dict(labels={'gate_passage':0})]
    assert not has_opposite_receipt_labels(probes,{'gate_passage':0},shorter_gate_window=True)


def example():
    old = dict(clip_id='T06_C02', sample_id='source', reference_video_sha256='a'*64,
        theta=.0571429, parameter='gap', normalization_domain=[.02,.085], normalization_span=.065,
        horizon_s=4.1, end_frame_index=209, reference_events={'chain':1}, status='incomplete')
    job = {k:old[k] for k in ['clip_id','sample_id','reference_video_sha256','theta','horizon_s','end_frame_index']}
    job.update(domain=old['normalization_domain'], family='gap')
    def probe(theta, label, repeat=False):
        return dict(theta=theta, labels={'chain':label}, source_repeat=repeat, native_peak_m=.02,
            state_and_config_hashes_verified=True, original_solver_and_clock_verified=True)
    evidence = dict(job=job, root='/original', result=None,
        audit=dict(source_labels={'chain':1}, repeated_labels={'chain':1}, source_event_match=True,
                   max_position_error_m=.003),
        probes=[probe(old['theta'],1), probe(old['theta'],1,True), probe(.12,1),probe(.18,0)])
    return old, evidence


def test_completed_endpoints_bind_without_claiming_a_finished_curve_or_quality():
    old, evidence = example(); before=copy.deepcopy(old)
    assert candidate_update(old,evidence,'proof') is None
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['boundary_records'][0]['bracket']==[.12,.18]
    assert row['boundary_records'][0]['distance']['bin']=='far'
    assert row['boundary_records'][0]['exact_theta_star'] is None
    assert row['conditional_solver_evidence']['full_scan_completed'] is False
    assert row['source_diagnostics']['physics_quality_approval_granted'] is False
    assert row['source_diagnostics']['maximum_native_overlap_m']==.02
    assert old==before


def test_failed_parameter_execution_cannot_be_the_only_opposite_witness():
    old,evidence=example()
    evidence['probes'][-1]['intervention_applied_as_declared']=False
    assert candidate_update(old,evidence,'proof',allow_completed_probes=True) is None


def test_original_friction_scale_is_saved_even_when_the_scan_has_no_flip(tmp_path,monkeypatch):
    import sys
    from scripts import collect_core100_original_continuation as continuation
    text='[("phone_tray_friction", x) for x in (0.025, 0.049, 0.090)]'
    (tmp_path/'original_friction_sampling_contract.json').write_text(json.dumps(dict(
        source_text=text,source_sha256=hashlib.sha256(text.encode()).hexdigest())))
    old=dict(clip_id='T05_C01',parameter='phone_tray_friction_coefficient',theta=.049,
        normalization_domain=None,status='incomplete')
    monkeypatch.setattr(continuation,'ROOT',tmp_path)
    monkeypatch.setattr(continuation,'WORK',tmp_path)
    monkeypatch.setattr(continuation,'load',lambda:dict(cases=[old]))
    monkeypatch.setattr(continuation,'collect',lambda *a,**k:[dict(job=dict(clip_id='T05_C01'),
        root='/original',preliminary_no_opposite_endpoints=True,unverified_receipt_count=3)])
    monkeypatch.setattr(sys,'argv',['collector','--host','p25'])
    continuation.main()
    saved=json.loads((tmp_path/'sealed_binding_updates.json').read_text())['updates'][0]
    assert saved['normalization_domain']==[.025,.09] and saved['status']=='incomplete'
    assert old['normalization_domain'] is None


def test_failed_execution_outside_a_valid_bracket_does_not_discard_valid_samples():
    old,evidence=example()
    invalid=copy.deepcopy(evidence['probes'][-1]);invalid.update(theta=0.,
        intervention_applied_as_declared=False,friction_execution_readback={'phone':[1.]})
    evidence['probes'].append(invalid)
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['boundary_records'][0]['bracket']==[.12,.18]
    assert row['source_diagnostics']['excluded_failed_intervention_probes'][0]['theta']==0.


def test_completed_interval_uses_the_actual_cached_parameter_values():
    old,evidence=example()
    evidence['result']={'intervals':[dict(event='chain',bracket=[.12000000000000001,.18],labels=[1,0])]}
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['boundary_records'][0]['bracket']==[.12,.18]
    assert row['boundary_records'][0]['endpoints'][0]['theta']==.12


def test_distances_use_applied_geometry_and_reject_identical_geometry_flips():
    old,evidence=example()
    evidence['probes'][-2]['effective_parameter_value']=.1201
    evidence['probes'][-1]['effective_parameter_value']=.1799
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['boundary_records'][0]['bracket']==[.1201,.1799]
    evidence['probes'][-1]['effective_parameter_value']=.1201
    with pytest.raises(ValueError,match='effective_parameter_endpoints_do_not_separate'):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)


@pytest.mark.parametrize('field,value,error',[
    ('reference_video_sha256','b'*64,'identity'),
    ('family','impulse','family'),('horizon_s',5.,'window')])
def test_wrong_reference_family_and_window_are_never_adopted(field,value,error):
    old,evidence=example(); evidence['job'][field]=value
    with pytest.raises(ValueError,match=error):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)


def test_no_flip_and_joint_parameters_are_not_fabricated_into_scalar_boundaries():
    old,evidence=example();evidence['probes'][-1]['labels']={'chain':1}
    assert candidate_update(old,evidence,'proof',allow_completed_probes=True) is None
    old['theta']={'gap':.0571429,'speed':3.05}
    assert candidate_update(old,evidence,'proof',allow_completed_probes=True) is None


def test_repeat_disagreement_and_unverified_endpoint_block_binding():
    old,evidence=example();evidence['audit']['repeated_labels']={'chain':0}
    with pytest.raises(ValueError,match='source_event'):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)
    old,evidence=example();evidence['probes'][-1]['state_and_config_hashes_verified']=False
    with pytest.raises(ValueError,match='unverified_probe'):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)


def test_additional_event_readback_does_not_relabel_the_frozen_target():
    old,evidence=example()
    evidence['audit']['source_labels']['ever_contact']=0
    evidence['audit']['repeated_labels']['ever_contact']=0
    for probe in evidence['probes']:
        probe['labels']['ever_contact']=int(probe['theta']==.18)
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['reference_events']=={'chain':1}
    assert {r['event']for r in row['boundary_records']}=={'chain'}


@pytest.mark.parametrize('has_supplemental_axis',[False,True])
def test_joint_axes_preserve_nominal_vector_and_do_not_pick_a_minimum_distance(has_supplemental_axis):
    old,evidence=example();old.update(clip_id='T11_C01',parameter='joint_global_configuration',
        theta={'driver_initial_speed_mps':3.05,'relay_case_gap_m':.024,'case_edge_margin_m':.055,
               'relay_block_mass_kg':.13,'case_friction_coefficient':.08},
        normalization_domain=None,normalization_span=None,boundary_records=[])
    if has_supplemental_axis:
        old['conditional_axes']={'supplemental_force':dict(theta=.2,boundary_records=[{'event':'chain'}])}
        old['source_point_axes']={'supplemental_force':.2}
    job=evidence['job'];job.update(clip_id=old['clip_id'],family='case_edge_margin_m',theta=.055,
        domain=[.025,.175],joint_source_nominal_parameters=copy.deepcopy(old['theta']),
        original_family_axes_not_collapsed=True)
    evidence['probes'][0]['theta']=evidence['probes'][1]['theta']=.055
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['theta']==old['theta'] and row['parameter']=='joint_global_configuration'
    assert row['boundary_records']==[] and row['axis_selection_required']
    axis=row['conditional_axes']['case_edge_margin_m']
    assert axis['boundary_records']
    if has_supplemental_axis:
        assert row['conditional_axes']['supplemental_force']==old['conditional_axes']['supplemental_force']
        assert row['source_point_axes']['supplemental_force']==.2
    assert axis['theta']==.055 and axis['normalization_span']==pytest.approx(.15)
    assert row['axes_without_bound_interval']==['driver_initial_speed_mps','relay_case_gap_m','relay_block_mass_kg']
    assert row['reference_events']==old['reference_events']
    evidence['job']['joint_source_nominal_parameters']['relay_block_mass_kg']=.1
    with pytest.raises(ValueError,match='joint_source'):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)


def test_original_global_path_keeps_joint_source_and_supplemental_axes(tmp_path,monkeypatch):
    from scripts import collect_core100_original_continuation as continuation
    from physedit.original_joint_path import T11_KEYS,make_joint_path
    from physedit.core100_bindings import original_family_reference_ready
    nodes=[dict(zip(T11_KEYS,row))for row in [
        (2.,.07,.15,.065,.22),(2.25,.055,.125,.075,.18),(2.45,.045,.105,.0875,.15),
        (2.65,.035,.085,.1,.12),(2.85,.03,.07,.115,.1),(3.05,.024,.055,.13,.08),
        (3.3,.018,.04,.15,.06),(3.55,.012,.03,.175,.04)]]
    path=make_joint_path(nodes);coordinate=path['coordinates'][5]
    old,evidence=example();old.update(clip_id='T11_C01',parameter='joint_global_configuration',
        theta=nodes[5],normalization_domain=None,normalization_span=None,boundary_records=[],
        conditional_axes={'supplemental_force':dict(boundary_records=[{'event':'chain'}],
            binding_kind='verified_supplemental_conditional_local_search')})
    proof=dict(original_family='joint_global_configuration',helper_source='pass',
        helper_sha256=hashlib.sha256(b'pass').hexdigest(),cases=[dict(clip_id=old['clip_id'],
            source_vector=nodes[5],source_coordinate=coordinate,joint_path=path,source_config_sha256='config',
            source_no_op_exact=True,all_eight_released_controlled_physics_match=True)])
    file=tmp_path/'t11_original_global_path_contract_20261101.json';file.write_text(json.dumps(proof))
    monkeypatch.setattr(continuation,'WORK',tmp_path);monkeypatch.setattr(continuation,'ROOT',tmp_path)
    job=evidence['job'];job.update(clip_id=old['clip_id'],family='original_G_global_path',
        base_config={'experiment':{'formal_design':{'design_id':'G_global_06'}}},
        theta=coordinate,domain=[0.,1.],joint_source_nominal_parameters=copy.deepcopy(nodes[5]),
        original_joint_path=path,config_sha256='config',original_joint_path_contract={
            'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    evidence['probes'][0]['theta']=evidence['probes'][1]['theta']=coordinate
    before=copy.deepcopy(old);result=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert old==before and result['theta']==nodes[5]
    assert result['conditional_axes']['supplemental_force']==old['conditional_axes']['supplemental_force']
    axis=result['conditional_axes']['original_G_global_path']
    assert axis['boundary_records'] and axis['normalization_span']==1
    assert axis['single_input_causal_attribution'] is False
    assert original_family_reference_ready(result)


def test_original_friction_component_keeps_joint_path_completion_separate(tmp_path,monkeypatch):
    from scripts import collect_core100_original_continuation as continuation
    from physedit.core100_bindings import original_family_reference_ready
    vector=dict(driver_initial_speed_mps=3.05,relay_case_gap_m=.024,case_edge_margin_m=.055,
        relay_block_mass_kg=.13,case_friction_coefficient=.08)
    old,evidence=example();old.update(clip_id='T11_C01',parameter='joint_global_configuration',
        theta=vector,normalization_domain=None,normalization_span=None,boundary_records=[])
    proof=dict(component='case_friction_coefficient',forces_modified=False,helper_source='pass',
        helper_sha256=hashlib.sha256(b'pass').hexdigest(),original_range=[.04,.22],
        cases=[dict(clip_id='T11_C01',source_vector=vector,source_config_sha256='original',source_no_op_exact=True)])
    file=tmp_path/'t11_original_case_friction_contract_20261101.json';file.write_text(json.dumps(proof))
    monkeypatch.setattr(continuation,'WORK',tmp_path);monkeypatch.setattr(continuation,'ROOT',tmp_path)
    evidence['job'].update(clip_id='T11_C01',theta=.08,family='case_friction_coefficient',domain=[.04,.22],
        joint_source_nominal_parameters=copy.deepcopy(vector),original_family_axes_not_collapsed=True,
        config_sha256='original',original_component_contract_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    evidence['probes'][0]['theta']=evidence['probes'][1]['theta']=.08
    for p in evidence['probes']:p['original_component_only_and_forces_unchanged_verified']=True
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    axis=row['conditional_axes']['case_friction_coefficient']
    assert axis['boundary_records'] and axis['original_joint_component']
    assert not axis['original_joint_path_recovered']
    assert row['theta']==vector and row['reference_events']==old['reference_events']
    assert not original_family_reference_ready(row)
    evidence['probes'][-1]['original_component_only_and_forces_unchanged_verified']=False
    with pytest.raises(ValueError,match='component_evidence_mismatch'):
        candidate_update(old,evidence,'proof',allow_completed_probes=True)


def test_recovered_primary_axis_joins_other_directions_without_replacing_them():
    old,evidence=example();other=dict(theta=2.,boundary_records=[{'event':'other-event'}])
    old.update(conditional_axes={'other':copy.deepcopy(other)},source_point_axes={'other':2.})
    row=candidate_update(old,evidence,'proof',allow_completed_probes=True)
    assert row['conditional_axes']['other']==other
    assert row['conditional_axes']['gap']['theta']==old['theta']
    assert row['source_point_axes']=={'other':2.,'gap':old['theta']}
    assert 'gap'not in old['conditional_axes']


def test_t09_restores_ever_contact_without_overwriting_legacy_or_claiming_completion(tmp_path,monkeypatch):
    from scripts import collect_core100_original_continuation as continuation
    old,evidence=example()
    old.update(clip_id='T09_C01',theta=15.5714286,parameter='pull_force',
        normalization_domain=[10.,16.],reference_events={'upper_nonpulled_book_on_table_at_end':0})
    evidence['job'].update({k:old[k]for k in ['clip_id','sample_id','reference_video_sha256','theta','horizon_s','end_frame_index']})
    event='upper_nonpulled_book_ever_contacts_table'
    for key in ['source_labels','repeated_labels']:
        evidence['audit'][key]={**old['reference_events'],event:0}
    contract={k:old[k]for k in ['clip_id','sample_id','reference_video_sha256','horizon_s','end_frame_index']}
    contract.update(family='pull_force',source_theta=old['theta'],original_normalization_domain=[10.,16.],
        restored_event=event,retained_legacy_event='upper_nonpulled_book_on_table_at_end',source_event_label=0,
        source_files=[dict(text='original producer',sha256=hashlib.sha256(b'original producer').hexdigest())])
    work=tmp_path/'review';work.mkdir();(work/'t09_original_family_event_contract.json').write_text(json.dumps(contract),encoding='utf8')
    monkeypatch.setattr(continuation,'ROOT',tmp_path);monkeypatch.setattr(continuation,'WORK',work)
    row=continuation.restore_t09_original_event(old,evidence)
    assert row['status']=='incomplete'and row['reference_events']['upper_nonpulled_book_on_table_at_end']==0
    assert row['reference_events'][event]==0 and row['primary_boundary_event']==event
    assert row['restored_event_protocol']['old_human_labels_reused'] is False
    assert event not in old['reference_events']
    evidence['job']['horizon_s']=5.
    with pytest.raises(ValueError,match='source_or_window'):
        continuation.restore_t09_original_event(old,evidence)
