import copy
import json
from pathlib import Path
import sys

import pytest
from physedit import boundary
from physedit import core100_critical as critical


def test_frozen_repair_boundary_cannot_borrow_legacy_or_unfinished_endpoints():
    from scripts.build_core100_v2_critical_registry import recovered_frozen_t20
    source=dict(clip_id='T20_C01',status='completed',theta=.03,
        actual_frozen_solver_seed_objects_and_axis_verified=True,
        reference_native_state_sha256='synthetic_repair_state',reference_video_sha256='synthetic_frozen_video',
        horizon_s=5.,native_peak_penetration_m=.0003,
        measurement=dict(label=1,first_contact_tuples=[[24,5],[24,9],[25,20]]),
        source_measurement=dict(label=1,first_contact_tuples=[[24,5],[24,9],[25,20]]))
    endpoint=copy.deepcopy(source);endpoint.update(theta=.45)
    endpoint['measurement']['label']=0
    sources=dict(status='completed',points=[source]);endpoints=dict(status='completed',points=[endpoint])
    assert recovered_frozen_t20(sources,endpoints)['T20_C01']['intervals'][0]['bracket']==[.03,.45]
    for key,value in [('status','running'),('reference_native_state_sha256','synthetic_old_production'),
        ('reference_video_sha256','synthetic_other_video'),('native_peak_penetration_m',.2),('horizon_s',6.)]:
        changed=copy.deepcopy(endpoints);changed['points'][0][key]=value
        assert recovered_frozen_t20(sources,changed)=={}
    changed=copy.deepcopy(endpoints);changed['points'][0]['measurement']['label']=None
    assert recovered_frozen_t20(sources,changed)=={}
    changed=copy.deepcopy(sources);changed['points'][0]['measurement']['first_contact_tuples'][0]=[25,5]
    assert recovered_frozen_t20(changed,endpoints)=={}
    # A different case still running must not block this completed contrast.
    other=dict(clip_id='T20_C05',theta=.5,status='running')
    partial=dict(status='pending',points=[endpoint,other])
    assert 'T20_C01'in recovered_frozen_t20(sources,partial)
    changed=copy.deepcopy(endpoints);changed['points'][0]['status']='running'
    assert recovered_frozen_t20(sources,changed)=={}


def test_original_sweep_recovery_keeps_camera_context_and_uncertainty_limits():
    data,_=critical.load();rows={r['clip_id']:r for r in data['cases']}
    r=rows['T06_C05'];unit=critical.primary(r)
    assert r['parameter']=='impact_force'and r['theta']==1.6428571
    assert unit['rgb_distance_admitted']and unit['intervals']==[[1.5357143,1.6428571]]
    assert unit['bin']=='near'  # Recovered original midpoint; no new simulation.
    assert r['original_released_sweep_recovery']['quarantined_or_incomplete_records']
    assert not r['reference_cross_camera_event_binding']['exact_same_trajectory_claimed']
    for cid in ['T09_C02','T09_C03']:
        r=rows[cid]
        assert r['normalization_domain']==[10.,16.]and r['normalization_span']==6.
        assert critical.primary(r)['rgb_distance_admitted']
    for cid in ['T09_C04','T09_C05']:
        assert critical.primary(rows[cid])['intervals']==[[.2,.2178571]]
    assert critical.primary(rows['T09_C04'])['bin']=='near'
    assert critical.primary(rows['T09_C05'])['bin']=='far'
    # Original gap changes also move books laterally along the declared arc.
    # Verify that original coupling; an arbitrary lateral perturbation fails.
    r=rows['T06_C01'];recovered=r['original_released_sweep_recovery']
    assert recovered['source_event_reference_admitted']
    assert not recovered['physical_context_mismatch_sample_ids']and recovered['fixed_physical_context_verified']
    assert critical.primary(r)['rgb_distance_admitted']
    assert critical.primary(r)['intervals']==[[.02,.0223214]]
    from scripts.finalize_core100_v2_legacy_released_recovery import context
    altered=copy.deepcopy(recovered['source'])
    altered['original_specs']['t06_book_01']['pose']['position'][1]+=.001
    with pytest.raises(AssertionError,match='lateral placement'):context(altered,r['theta'])
    for cid in ['T10_C03','T10_C04']:
        r=rows[cid];assert critical.primary(r)['rgb_distance_admitted']
        assert critical.primary(r)['intervals']==[[.204,.2105]]
        assert r['original_released_sweep_recovery']['invalid_intermediate_records']
    # Approximate RGB projection does not override incompatible executed
    # parameters/objects in a stale state header.
    r=rows['T10_C05'];assert r['theta']==.2171429
    assert r['normalization_domain']==[-.05,.28]
    assert r['historical_other_version_parameter_binding']['theta']==.1909
    assert critical.primary(r)['intervals']==[]and critical.primary(r)['normalized_absolute_interval']is None
    assert not r['original_released_sweep_recovery']['source_event_reference_admitted']
    assert not critical.primary(r)['rgb_distance_admitted']
    assert critical.primary(r)['event']not in r['admitted_rgb_events']


def test_original_gpu_t18_flip_needs_named_terminal_witnesses_and_separate_trajectory_scope():
    data,_=critical.load();rows={r['clip_id']:r for r in data['cases']}
    from scripts.build_core100_v2_critical_registry import t18_terminal_event_witness_matches
    for cid in ['T18_C03','T18_C05']:
        row=rows[cid];diagnostic=row['original_GPU_endpoint_diagnostic']
        assert diagnostic['intervals']and diagnostic['formal_distance_admitted']
        assert all(set(b['endpoint_labels'])=={0,1}for b in diagnostic['intervals'])
        assert row['historical_other_profile_boundary_records']
        assert critical.primary(row)['rgb_distance_admitted']and not row['distance_admission_pending_reason']
        closure=row['original_GPU_terminal_event_closure'];audit=closure['audit']
        assert closure['source_comparison_scope']=='original_binary_event_history_and_named_terminal_witnesses_only'
        assert closure['source_full_window_position_error_m']>.001
        name=next(k for k in audit['source_hashes']if 't18_gpu_endpoints_collect_'in k)
        endpoints=[p for p in json.loads((critical.ROOT/name).read_text())['points']if p['clip_id']==cid]
        source=row['original_GPU_source_replay_diagnostic']
        assert t18_terminal_event_witness_matches(source,endpoints,audit)
        changed=copy.deepcopy(audit);changed['points'][0]['native_contact_history']=[999]
        assert not t18_terminal_event_witness_matches(source,endpoints,changed)
        changed=copy.deepcopy(audit);changed['points'][1]['terminal_frames'][0]['label']=1-changed['points'][1]['terminal_frames'][0]['label']
        assert not t18_terminal_event_witness_matches(source,endpoints,changed)
    assert critical.primary(rows['T18_C03'])['intervals']==[[.04,.08]]
    assert critical.primary(rows['T18_C03'])['bin']=='far'
    assert critical.primary(rows['T18_C05'])['bin']is None
    extra=rows['T18_C05']['original_GPU_terminal_event_closure']['additional_repeat_attempts']
    assert extra['additional_repeats_successful']is False
    assert all(p['status']=='failed'for p in extra['repeats']['points'])
    assert not rows['T18_C05']['full_EventExact_automatically_admitted']
    row=rows['T18_C04'];closure=row['original_GPU_terminal_event_closure']
    assert critical.primary(row)['rgb_distance_admitted']
    assert closure['source_full_window_position_error_m']<=.001
    assert closure['source_video_visual_review']['reviewer']=='assistant_visual_review_not_independent_human_gold'
    from scripts.build_core100_v2_critical_registry import t18_terminal_audit_matches
    source=row['original_GPU_source_replay_diagnostic'];audit=closure['audit']
    # The immutable original readback supplies actual completed endpoint
    # receipts; the altered copies below must never admit another window or
    # a missing/unstable terminal observation.
    name=next(k for k in audit['source_hashes']if 't18_gpu_endpoints_collect_'in k)
    endpoint=[p for p in json.loads((critical.ROOT/name).read_text())['points']if p['clip_id']=='T18_C04']
    assert t18_terminal_audit_matches(source,endpoint,audit)
    changed=copy.deepcopy(audit);changed['points'][-1]['end_frame']=153
    assert not t18_terminal_audit_matches(source,endpoint,changed)
    changed=copy.deepcopy(audit);changed['points'][-1]['terminal_frames'][0]['label']=1
    assert not t18_terminal_audit_matches(source,endpoint,changed)
    changed=copy.deepcopy(audit);changed['points'][-1]['state_sha256']='other_state'
    assert not t18_terminal_audit_matches(source,endpoint,changed)
    changed=copy.deepcopy(source);changed['source_maximum_position_difference_m']=.03
    assert not t18_terminal_audit_matches(changed,endpoint,audit)


def test_t03_box_depth_disposition_preserves_original_event_and_uncertain_bin():
    from scripts.build_core100_v2_critical_registry import t03_box_diagnostic_disposition
    data,_=critical.load();row=next(r for r in data['cases']if r['clip_id']=='T03_C01')
    unit=critical.primary(row)
    assert unit['event']=='phone_second_fall_original'and unit['label']==0
    assert unit['intervals']==[[.08433333333333333,.1]]and unit['rgb_distance_admitted']
    assert unit['bin']is None  # No midpoint substitution to manufacture Near.
    source=row['original_shared_runtime_GPU_source_diagnostic']
    endpoints=row['original_shared_runtime_GPU_endpoint_diagnostic']['points']
    audit=row['native_contact_diagnostic_disposition']['evidence']
    assert t03_box_diagnostic_disposition(source,endpoints,audit)
    assert all(p['maximum_saved_frame_box_overlap_m']<.00021 for p in audit['points'])
    assert all(not p['internal_peak_pose_reconstructed']for p in audit['points'])
    assert row['historical_independent_gpu64_boundary_records']
    for key,value in [('state_sha256','unrelated_state'),('theta',.2),
        ('maximum_saved_frame_box_overlap_m',.02),('all_saved_frames_finite',False),
        ('maximum_internal_reported_depth_m',.001)]:
        changed=copy.deepcopy(audit);changed['points'][0][key]=value
        assert not t03_box_diagnostic_disposition(source,endpoints,changed)
    changed=copy.deepcopy(source);changed['source_event_match']=False
    assert not t03_box_diagnostic_disposition(changed,endpoints,audit)


def test_saved_box_geometry_distinguishes_separation_overlap_and_rotation():
    from scripts.audit_core100_v2_t03_contact_geometry import REMOTE
    ns={};exec(REMOTE.split('rows=[]')[0],ns)
    box=ns['box_depth'];pose=lambda xyz,q=[0,0,0,1]:dict(position=xyz,quaternion_xyzw=q)
    assert box(pose([0,0,0]),[2,2,2],pose([3,0,0]),[2,2,2])==0
    assert box(pose([0,0,0]),[2,2,2],pose([1.75,0,0]),[2,2,2])==pytest.approx(.25)
    assert box(pose([10,4,8]),[2,2,2],pose([11.75,4,8]),[2,2,2])==pytest.approx(.25)
    q=[0,0,2**-.5,2**-.5]
    # Rotating the long box changes a separated pair into an overlapping pair.
    assert box(pose([0,0,0]),[4,.5,.5],pose([0,1,0]),[1,1,1])==0
    assert box(pose([0,0,0],q),[4,.5,.5],pose([0,1,0]),[1,1,1])==pytest.approx(.75)


def test_t09_original_terminal_closure_preserves_domain_and_rejects_changed_evidence():
    from scripts.build_core100_v2_critical_registry import t09_terminal_event_closure
    data,_=critical.load();row=next(r for r in data['cases']if r['clip_id']=='T09_C01')
    c=row['original_GPU_T09_terminal_event_closure'];unit=critical.primary(row)
    assert unit['rgb_distance_admitted']and unit['intervals']==[[4.45,4.5]]
    assert unit['bin']=='far'and unit['normalization_span']==6
    assert row['normalization_domain']==[10.,16.]and unit['label']==0
    assert row['boundary_records'][0]['outside_original_parameter_domain']
    assert not row['full_EventExact_automatically_admitted']
    assert t09_terminal_event_closure(c['points'],c['audit'])
    for key,value in [('state_sha256','unrelated'),('window',[4,154]),('simulation_frame_period_s',1/30)]:
        a=copy.deepcopy(c['audit']);a['points'][0][key]=value
        assert t09_terminal_event_closure(c['points'],a)is None
    a=copy.deepcopy(c['audit']);a['points'][1]['terminal_frames'][0]['minimum_target_bottom_to_table_plane_distance_m']=.02
    assert t09_terminal_event_closure(c['points'],a)is None


def test_author_approved_t08_refinement_preserves_original_labels_and_profile_uncertainty():
    data,_=critical.load();rows={r['clip_id']:r for r in data['cases']}
    for cid in ['T08_C01','T08_C02','T08_C03']:
        row=rows[cid];profile=row['numerical_reference_profile'];unit=critical.primary(row)
        assert unit['rgb_distance_admitted']and unit['event']=='t08_target_mug_below_table_8cm'
        assert profile['precision_bits']==64 and profile['substeps']==8
        assert profile['constraint_timeconst_s']==.0005 and not profile['original_rendering_search_value']
        assert profile['uncertainty']['original_to_refined_boundary_shift'].startswith('Not quantified')
        assert row['numerical_source_matches_reference_state_digest']is False
        assert not row['full_EventExact_automatically_admitted']
    assert data['summary']['unresolved_numerical_reference_state_digest_mismatch']==[]
    row=rows['T08_C02'];event='t08_lower_impactor_book_below_table_8cm'
    assert row['reference_events'][event]==1
    assert row['author_approved_numerical_refinement']['non_target_source_event_differences'][event]==dict(original=1,refined=0)


def test_original_v2_families_and_windows_remain_loadable_after_versioned_revisions():
    # The original 99-candidate snapshot remains reproducible. The current
    # T03 stage revision separately rejects R032's incorrectly seeded probes.
    snapshot=critical.ROOT/'benchmarks/core100_critical_protocol_v2_20261102/registry_99526466ed6d.json'
    data,_=critical.load(snapshot,'99526466ed6d844842b760ed8af9717d6177d5b24f76f3b2b564b4d5903c84ca');rows={r['clip_id']:r for r in data['cases']}
    assert data['summary']['registered_cases']==100
    assert data['summary']['original_family_boundary_cases']==99
    assert data['summary']['original_family_pending']==['T10_C05']
    for cid,expected in [('T02_C01',[.1516736,.1770508]),('T02_C02',[.1612948,.1786225])]:
        assert rows[cid]['boundary_records'][0]['bracket']==expected
        assert rows[cid]['horizon_s']==205/30
        assert rows[cid]['historical_calibration_reference']['exact_physical_threshold_certified']is False
    t20=critical.primary(rows['T20_C01'])
    assert t20['axis']=='box_cup_gap'and t20['theta']==rows['T20_C01']['theta']
    assert not t20['supplemental_axis']
    if rows['T20_C01'].get('numerical_source_matches_reference_state_digest')is False:
        assert not t20['rgb_distance_admitted']
    assert rows['T20_C01']['native_quality_limit']['status']=='retained_failed_original_1mm_penetration_check'
    for cid in ['T07_C04','T07_C05']:
        assert rows[cid]['boundary_records'][0]['bracket']==[.24,.28]
        assert critical.primary(rows[cid])['rgb_distance_admitted']
    assert critical.primary(rows['T16_C04'])['bin']is None
    pair=next(p for p in data['pairs']if p['pair_id']=='T07_original_cf_A_friction')
    assert pair['pairing_mode']=='coupled_seed'and pair['condition_sha256']
    for cid in ['T14_C04','T14_C05']:
        assert rows[cid]['source_state_sha256']
        assert rows[cid]['boundary_records'][0]['bracket']==[.018,.019]
        assert critical.primary(rows[cid])['rgb_distance_admitted']and critical.primary(rows[cid])['bin']is None
    for cid in ['T03_C04','T03_C05']:
        unit=critical.primary(rows[cid])
        assert unit['event']=='book_contacts_upper_can'and unit['rgb_distance_admitted']
        assert rows[cid]['boundary_records'][0]['bracket']==pytest.approx([.47,.73])
        assert not rows[cid]['full_EventExact_automatically_admitted']
    # cfB's names are not its numeric ordering: theta_minus has the larger
    # actual support margin. Keep its phone-contact event and original pose
    # coupling instead of treating this as the fall/initial-speed boundary.
    for cid,label in [('T15_C04',0),('T15_C05',1)]:
        unit=critical.primary(rows[cid])
        assert unit['axis']=='laptop_edge_margin_m'and unit['event']=='laptop_contacts_phone'
        assert unit['label']==label and unit['rgb_distance_admitted']
        assert rows[cid]['boundary_records'][0]['bracket']==pytest.approx([.05,.085])
        assert rows[cid]['boundary_records'][0]['endpoint_labels']==[1,0]
    pair=next(p for p in data['pairs']if p['pair_id']=='T15_original_cf_B_laptop_phone_contact')
    assert pair['pairing_mode']=='coupled_seed'
    for cid in ['T15_C01','T15_C02','T15_C03']:
        row=rows[cid];unit=critical.primary(row)
        assert unit['rgb_distance_admitted']and unit['event']=='laptop_reaches_original_fall_criterion'
        assert row['boundary_records'][0]['bracket']==[row['normalization_domain'][0],row['theta']]
        assert unit['bin']is None  # Broad intervals are kept; no midpoint Near.
        source=row['original_V11_GPU64_evidence']['source']
        assert source['measurement']['first_threshold_frame']==source['source_measurement']['first_threshold_frame']


def test_native_isaac_force_contract_and_original_speed_sweeps_are_bound_to_their_own_references():
    data,_=critical.load();rows={r['clip_id']:r for r in data['cases']}
    c=rows['T06_C04'];unit=critical.primary(c);e=c['original_isaac_existing_search_evidence']
    assert unit['event']=='complete_required_contact_chain'and unit['rgb_distance_admitted']
    assert c['horizon_s']==4.1 and c['end_frame_index']==209
    assert e['new_simulations']==0 and all(p['damping_refinement_factor']==1 for p in e['points'])
    source=next(p for p in e['points']if p['theta']==c['theta'])
    assert source['source_trajectory_exact']and source['source_maximum_position_difference_m']==0
    for cid,bracket in [('T20_C02',[.8181818181818181,1.1363636363636362]),
                        ('T20_C03',[1.4545454545454546,1.7727272727272727]),
                        ('T20_C04',[1.4545454545454546,1.7727272727272727])]:
        c=rows[cid];unit=critical.primary(c)
        assert unit['axis']=='book_drive_speed'and unit['rgb_distance_admitted']
        assert c['boundary_records'][0]['bracket']==bracket
        assert c['original_published_speed_readback']['source']['label']==1
    for c in rows.values():
        if c.get('numerical_source_matches_reference_state_digest')is False:
            if c.get('author_approved_numerical_refinement'):
                assert c['clip_id']in ['T08_C01','T08_C02','T08_C03']
                assert c['numerical_reference_profile']['reference_kind']=='author_approved_numerical_refinement'
                assert all(u['event']=='t08_target_mug_below_table_8cm'for u in c['critical_units']if u['rgb_distance_admitted'])
            else:
                assert not any(u['rgb_distance_admitted']for u in c['critical_units'])
            assert c['reference_native_state_binding']['decoded_state_sha256']!=c['source_state_sha256']


def test_all100_generate_despite_pending_inversion_and_reference_measurement(tmp_path):
    result=critical.prepare(tmp_path/'input','FIXTURE_NOT_MODEL',fps=24,seeds=[0,1])
    rows=boundary.read_rows(tmp_path/'input/inputs.jsonl');keys=boundary.read_rows(tmp_path/'input/answers.jsonl')
    assert result['registered']==result['generation_candidates']==200
    assert len({r['clip_id']for r in rows})==100
    assert all(k['inversion']['status']=='pending_reference_validation'for k in keys)
    assert any(not k['critical_rgb_distance_admitted']for k in keys)
    assert all(not(set(r)&{'events','boundary','target_event','numerical_distance_reference'})for r in rows)
    for pair in critical.load()[0]['pairs']:
        left,right=[{r['seed']for r in rows if r['clip_id']==cid}for cid in pair['clips']]
        assert left.isdisjoint(right)if pair['pairing_mode']=='independent'else left==right


def test_binding_never_changes_original_labels_order_or_inversion():
    data,_=critical.load();row=data['cases'][0];unit=critical.primary(row)
    key=dict(clip_id=row['clip_id'],target_event=unit['event'],theta=unit['theta'],
        events=copy.deepcopy(row['reference_events']),required_order=[['a','b']],inversion={'status':'eligible','reason':'external test registration'})
    old=copy.deepcopy(key)
    result=critical.bind_answer(key,reference_video_sha256=row['reference_video_sha256'],horizon_s=row['horizon_s'])
    assert key==old and all(result[k]==old[k]for k in ['events','required_order','inversion'])
    with pytest.raises(ValueError,match='window_mismatch'):
        critical.bind_answer(key,reference_video_sha256=row['reference_video_sha256'],horizon_s=1)
    with pytest.raises(ValueError,match='identity_mismatch'):
        critical.bind_answer(key,reference_video_sha256='wrong',horizon_s=row['horizon_s'])


def fixture_run(tmp_path,monkeypatch,inversion_registry=None):
    out=tmp_path/'input';critical.prepare(out,'SYNTHETIC_UNIT_TEST_NOT_MODEL',fps=24,inversion_registry=inversion_registry)
    spec=json.loads((out/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    def fixture_media(path,row):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(row['sample_id'].encode())
        return dict(status='ok',video=str(path),video_sha256=boundary.digest(path))
    monkeypatch.setattr(boundary,'media',fixture_media)
    run=tmp_path/'run';boundary.run(spec,run)
    keys=boundary.read_rows(run/'answers.jsonl');videos=boundary.read_rows(run/'observed_rows.jsonl')
    annotations=[];screening=[]
    for key,video in zip(keys,videos):
        annotations.append(dict(sample_id=key['sample_id'],video_sha256=video['video_sha256'],
            events=key['events'],method='synthetic_unit_test_fixture',review_status='final',evidence='Test fixture only, not real model evidence.'))
        screening.append(dict(sample_id=key['sample_id'],video_sha256=video['video_sha256'],
            status='pass',method='synthetic_unit_test_fixture',evidence='Test quality gate only.'))
    ann=tmp_path/'annotations.jsonl';scr=tmp_path/'screening.jsonl'
    boundary.write_rows(ann,annotations);boundary.write_rows(scr,screening)
    return run,ann,scr


def test_final_scoring_and_coverage_do_not_claim_full_chain_or_all_references_admitted(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    r=critical.score(run,annotations=ann,screening=scr)
    assert r['registered']==100 and r['near_accuracy']==1
    assert r['independent_pair_accuracy']==r['coupled_pair_accuracy']==1
    assert r['event_exact']is None and r['event_measurement']['target_coverage']==1
    assert r['critical_reference_coverage']<1
    assert r['inversion']['registered']==100 and r['inversion']['eligible']==0
    assert r['numerical_reference_profile_coverage']['t08_cpu64_sub8_tc0p0005']==3
    profile=next(p for p in r['distance_strata_by_numerical_profile']if p['profile_id']=='t08_cpu64_sub8_tc0p0005')
    assert next(s for s in profile['strata']if s['bin']=='far')['reference_points']==3
    assert next(s for s in profile['strata']if s['bin']=='near')['reference_points']==0
    assert set(r['refined_reference_configurations_and_uncertainty'])=={'T08_C01','T08_C02','T08_C03'}
    assert all('numerical_reference_profile'not in row for row in boundary.read_rows(run/'inputs.jsonl'))


def test_changed_refinement_profile_cannot_be_smuggled_into_scoring(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    rows=boundary.read_rows(run/'answers.jsonl');key=next(k for k in rows if k['clip_id']=='T08_C01')
    key['numerical_reference_profile']['constraint_timeconst_s']=.002
    (run/'answers.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    with pytest.raises(ValueError,match='numerical_reference_profile_changed'):
        critical.score(run,annotations=ann,screening=scr)


def test_reference_trajectory_limitations_remain_disclosed_and_hash_bound(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    value=critical.score(run,annotations=ann,screening=scr)
    d=value['reference_replay_disclosures']['T18_C05']
    assert d['additional_repeats_successful']is False and d['source_full_window_position_error_m']>.03
    assert d['scope']=='original_binary_event_history_and_named_terminal_witnesses_only'
    assert all('reference_replay_disclosure'not in r for r in boundary.read_rows(run/'inputs.jsonl'))
    keys=boundary.read_rows(run/'answers.jsonl');key=next(k for k in keys if k['clip_id']=='T18_C05')
    key['reference_replay_disclosure']['exact_full_trajectory_equivalence_claimed']=True
    (run/'answers.jsonl').write_text(''.join(json.dumps(k)+'\n'for k in keys),encoding='utf8')
    with pytest.raises(ValueError,match='reference_replay_disclosure_changed'):
        critical.score(run,annotations=ann,screening=scr)


def test_prelabels_remain_pending_instead_of_final_errors_or_successes(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    rows=boundary.read_rows(ann)
    for row in rows:row['review_status']='prelabel'
    ann.write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    r=critical.score(run,annotations=ann,screening=scr)
    assert r['near_accuracy']is None and r['near_accuracy_lower_bound']==0
    assert r['independent_pair_accuracy']is None and r['coupled_pair_accuracy']is None
    assert r['event_measurement']['pending_decisions']==100 and r['event_measurement']['target_coverage']==0


def test_confirmed_quality_failure_remains_in_near_and_pair_denominators(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    inputs=boundary.read_rows(run/'inputs.jsonl');cid='T10_C01';sid=next(r['sample_id']for r in inputs if r['clip_id']==cid)
    rows=boundary.read_rows(scr);bad=next(r for r in rows if r['sample_id']==sid)
    bad.update(status='confirmed_failure',reviewer='unit_test_adjudicator',blocked_events=['support_pen_displacement_reaches_source_threshold'],block_inversion=True)
    scr.write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    result=critical.score(run,annotations=ann,screening=scr)
    n=result['independent_pair_accuracy_eligible_pairs']
    assert result['registered']==100 and result['independent_pair_accuracy']==pytest.approx((n-1)/n)
    assert result['near_accuracy']<1 and result['near_accuracy']is not None
    assert result['event_measurement']['target_coverage']==.99
    assert next(p for p in result['points']if p['clip_id']==cid)['accuracy']==0


def test_recovered_coupled_pair_keeps_failed_endpoint_in_its_denominator(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    key=next(k for k in boundary.read_rows(run/'answers.jsonl')if k['clip_id']=='T14_C05')
    rows=boundary.read_rows(scr);bad=next(r for r in rows if r['sample_id']==key['sample_id'])
    bad.update(status='confirmed_failure',reviewer='synthetic_unit_test',blocked_events=list(key['events']),block_inversion=True)
    updated=tmp_path/'adjudicated_screening.jsonl';boundary.write_rows(updated,rows)
    value=critical.score(run,annotations=ann,screening=updated)
    eligible=value['coupled_pair_accuracy_eligible_pairs']
    assert value['coupled_pair_accuracy']==pytest.approx((eligible-1)/eligible)
    assert next(p for p in value['pairs']if p['pair_id']=='T14_original_cf_A_gap')['score']==0


def test_incorrect_reference_labels_cannot_be_smuggled_into_scoring(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    rows=boundary.read_rows(run/'answers.jsonl');row=rows[0];event=row['target_event'];row['events'][event]=1-row['events'][event]
    (run/'answers.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    with pytest.raises(ValueError,match='truth_conflict|reference_truth_changed'):critical.score(run,annotations=ann,screening=scr)


def test_constant_outcome_cannot_pass_the_cross_boundary_pairs(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    rows=boundary.read_rows(ann)
    for row in rows:row['events']={event:1 for event in row['events']}
    ann.write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    result=critical.score(run,annotations=ann,screening=scr)
    assert result['near_accuracy']==.5
    assert next(s for s in result['distance_strata']if s['bin']=='near')['balanced_accuracy']==.5
    assert result['independent_pair_accuracy']==result['coupled_pair_accuracy']==0


def test_missing_or_changed_download_is_not_a_confirmed_model_quality_failure(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    videos=boundary.read_rows(run/'observed_rows.jsonl')
    inputs={r['sample_id']:r for r in boundary.read_rows(run/'inputs.jsonl')}
    bad=next(r for r in videos if inputs[r['sample_id']]['clip_id']=='T10_C01')
    Path(bad['video']).write_bytes(b'broken_media_transfer_fixture')
    result=critical.score(run,annotations=ann,screening=scr)
    assert result['registered']==100 and result['near_accuracy']is None
    assert result['event_measurement']['pending_decisions']==1
    assert result['screening']['confirmed_failure_count']==0


def test_two_stage_router_preserves_prelabels_and_finalizes_human_target_reviews(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    inputs=boundary.read_rows(run/'inputs.jsonl');videos=boundary.read_rows(run/'observed_rows.jsonl')
    answers=boundary.read_rows(run/'answers.jsonl');qualities=[];events=[];reviews=[]
    for i,v,k in zip(inputs,videos,answers):
        qualities.append(dict(sample_id=i['sample_id'],video_sha256=v['video_sha256'],status='ok',
            quality=dict(status='measurable',failure='none',target_integrity='intact',support_integrity='intact',
                confidence=.99,evidence_times_s=[0,i['evaluation_duration_s']],reason='Synthetic test fixture only.')))
        events.append(dict(sample_id=i['sample_id'],video_sha256=v['video_sha256'],status='ok',
            events={e:dict(label='yes'if y else'no',confidence=.99,
                evidence_times_s=[0,i['evaluation_duration_s']],reason='Synthetic fixture, not model evidence.',contradictions=[])
                for e,y in k['events'].items()}))
        reviews.append(dict(sample_id=i['sample_id'],video_sha256=v['video_sha256'],reviewer='synthetic_unit_test',
            evidence='Synthetic test adjudication only.',quality_status='pass',
            events={k['target_event']:dict(label=k['events'][k['target_event']],evidence='Synthetic target label.')}))
    qp=tmp_path/'quality_predictions.jsonl';ep=tmp_path/'event_predictions.jsonl';rp=tmp_path/'human_reviews.jsonl'
    boundary.write_rows(qp,qualities);boundary.write_rows(ep,events);boundary.write_rows(rp,reviews)
    protocol=tmp_path/'input/judge_protocol.json'
    # Simulated judge consumes the actual scheduled observation contract,
    # including its generated clock, instead of copying a reference time.
    scheduled=tmp_path/'scheduled'
    critical.judge(run,protocol,scheduled,quality_file=qp)
    jobs={j['sample_id']:j for j in boundary.read_rows(scheduled/'event_jobs.jsonl')}
    for prediction in events:
        job=jobs[prediction['sample_id']];end=job['last_observed_time_s']
        prediction.update(event_contract_sha256=job['event_contract_sha256'],times_s=[0,end])
        for event in prediction['events'].values():event['evidence_times_s']=[0,end]
    ep=tmp_path/'event_predictions_bound.jsonl'
    boundary.write_rows(ep,events)
    auto=tmp_path/'auto'
    receipt=critical.judge(run,protocol,auto,quality_file=qp,event_file=ep)
    assert receipt['preannotated_event_count']>=100 and receipt['final_target_labels']==0
    auto_score=json.loads((auto/'scores.json').read_text())
    assert auto_score['near_accuracy']is None and auto_score['event_measurement']['pending_decisions']==100
    final=tmp_path/'final'
    receipt=critical.judge(run,protocol,final,quality_file=qp,event_file=ep,reviews_file=rp)
    score=json.loads((final/'scores.json').read_text())
    assert receipt['final_target_labels']==100 and score['near_accuracy']==1
    assert score['event_exact']is None and score['event_measurement']['pending_decisions']==0
    assert (final/'generic_scores_diagnostic.json').is_file()
    labels=boundary.read_rows(final/'critical_annotations.jsonl')
    assert all(x['review_status']=='final'for x in labels)
    assert any('pending'in x['event_review_status'].values()for x in labels)


def test_judge_contract_uses_replacement_objects_and_cannot_be_silently_rewritten(tmp_path,monkeypatch):
    run,ann,scr=fixture_run(tmp_path,monkeypatch)
    protocol=tmp_path/'input/judge_protocol.json';value=json.loads(protocol.read_text(encoding='utf8'))
    assert len(value['samples'])==100
    assert all(not(set(s)&{'label','reference_label','theta','boundary'})for s in value['samples'].values())
    t04=next(v for k,v in value['samples'].items()if k.startswith('T04_C01_'))
    assert 't04v3_chain_mug'in t04['events']['original_full_chain']['definition']
    assert 'V4'not in t04['events']['original_full_chain']['definition']
    value['samples'][next(iter(value['samples']))]['events']['full_chain']['definition']='Changed event contract fixture'
    protocol.write_text(json.dumps(value),encoding='utf8')
    with pytest.raises(ValueError,match='judge_protocol_changed'):
        critical.judge(run,protocol,tmp_path/'screened')


def test_external_inversion_admission_is_independent_and_hash_bound(tmp_path,monkeypatch):
    data,_=critical.load();r=next(x for x in data['cases']if x['clip_id']=='T06_C02')
    assert not critical.primary(r)['rgb_distance_admitted']
    registration=dict(roster_release=data['roster_release'],references=[dict(clip_id=r['clip_id'],
        reference_video_sha256=r['reference_video_sha256'],horizon_s=r['horizon_s'],
        status='eligible',reason='Synthetic independent inversion contract fixture.',protocol_version='test-only',
        measurement_window_s=[0,1],validation_evidence='SYNTHETIC_UNIT_TEST_NOT_REAL_VALIDATION')])
    path=tmp_path/'external_inverse.json';path.write_text(json.dumps(registration),encoding='utf8')
    run,ann,scr=fixture_run(tmp_path,monkeypatch,inversion_registry=path)
    keys=boundary.read_rows(run/'answers.jsonl');key=next(x for x in keys if x['clip_id']==r['clip_id'])
    video=next(x for x in boundary.read_rows(run/'observed_rows.jsonl')if x['sample_id']==key['sample_id'])
    predictions=tmp_path/'gravity.jsonl'
    boundary.write_rows(predictions,[dict(sample_id=key['sample_id'],video_sha256=video['video_sha256'],
        status='ok',gravity=key['gravity']*1.1,reference_registration_sha256=critical.sha(path))])
    value=critical.score(run,annotations=ann,screening=scr,gravity=predictions)
    assert value['registered']==100 and value['inversion']['eligible']==1 and value['inversion']['fitted']==1
    assert value['inversion']['relative_deviation_mean']==pytest.approx(.1)
    assert value['inversion']['registered_coverage']==.01
    # The same stage cannot reuse an old/different source video's eligibility.
    registration['references'][0]['reference_video_sha256']='wrong_reference'
    path.write_text(json.dumps(registration),encoding='utf8')
    with pytest.raises(ValueError,match='reference_or_window_changed'):
        critical.prepare(tmp_path/'bad','FIXTURE',fps=24,inversion_registry=path)
