"""Connect the revised 100-case roster to versioned critical evidence.

This sidecar does not overwrite the old live-site registry. Numerical recovery,
RGB event admission, and model scoring remain separate measurable states.
"""
import collections
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil

from physedit.core100_rebalanced import load as load_roster
from physedit.critical_supplement import load as load_supplement,DEFAULT as SUPPLEMENT
from physedit.core100_bindings import interval_distance

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
OUT=ROOT/'benchmarks/core100_critical_protocol_v2_20261102'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))

def recovered_frozen_t20(source_report,endpoint_report):
    """Admit only completed, identity-bound original-profile contrasts.

    An unfinished endpoint, unknown event or bad native contact remains a
    diagnostic. Existing production brackets cannot fill in a missing repair
    endpoint. Interval width is retained rather than inventing a point root.
    """
    recovered={}
    for source in source_report['points']:
        if source['status']!='completed':continue
        cid=source['clip_id']
        endpoints=[p for p in endpoint_report['points']if p['clip_id']==cid]
        points=sorted([source]+endpoints,key=lambda p:p['theta'])
        identity=['reference_native_state_sha256','reference_video_sha256']
        if not endpoints or not all(p['status']=='completed' and
            p['actual_frozen_solver_seed_objects_and_axis_verified'] and
            all(p[k]==source[k]for k in identity) and
            p['horizon_s']==5. and p['native_peak_penetration_m']<=.001 and
            type(p['measurement']['label'])is int and p['measurement']['label']in[0,1]
            for p in points):continue
        if source['measurement']['label']!=source['source_measurement']['label']:continue
        if source['measurement']['first_contact_tuples']!=source['source_measurement']['first_contact_tuples']:continue
        intervals=[dict(event='complete_propagation_original',bracket=[a['theta'],b['theta']],
            endpoint_labels=[a['measurement']['label'],b['measurement']['label']])
            for a,b in zip(points,points[1:])if a['measurement']['label']!=b['measurement']['label']]
        if intervals:recovered[cid]=dict(source=source,points=points,intervals=intervals)
    return recovered

def t18_terminal_audit_matches(source,endpoints,audit):
    """Verify only the original terminal contact, retaining early diagnostics.

    A matching label is insufficient: the original source trajectory, executed
    endpoints, named contacts, exact window and terminal contact quality must
    agree. This does not certify all earlier physics or a unique physical root.
    """
    if source.get('source_maximum_position_difference_m',float('inf'))>.001:return False
    return t18_terminal_event_witness_matches(source,endpoints,audit)


def t18_terminal_event_witness_matches(source,endpoints,audit):
    """Validate the original binary terminal event, separately from positions.

    This deliberately does not assert full-trajectory equivalence: the
    original physical inputs/profile and the complete source event history
    must agree, and each endpoint needs ten stable named terminal witnesses.
    """
    if not(source.get('status')=='completed'and source.get('source_label_matches')and
        source.get('original_specs_solver_seed_and_controller_preserved')):return False
    completed=[source]+[p for p in endpoints if p.get('status')=='completed']
    by_hash={p['state_sha256']:p for p in completed}
    if len(audit.get('points',[]))<2:return False
    labels=set();source_found=False
    for a in audit['points']:
        p=by_hash.get(a['state_sha256'])
        if p is None or a['theta']!=p['theta']:return False
        if p['reference_video_sha256']!=source['reference_video_sha256']or p['source_state_sha256']!=source['source_state_sha256']:return False
        if not(a['reference_video_sha256']==source['reference_video_sha256']and
            a['original_source_sha256']==source['source_state_sha256']and
            a['condition_frame']==4 and a['end_frame']==154 and a['horizon_s']==5. and
            a['native_fps']==30 and a['finite_positions']and a['terminal_all_contacts_inside_declared_support']and
            a['terminal_maximum_native_penetration_m']<=.001):return False
        frames=a['terminal_frames'];label=p['measurement']['label']
        if len(frames)!=10 or [f['frame']for f in frames]!=list(range(145,155)):return False
        if any(f['label']!=label for f in frames):return False
        if a['kind']=='source':
            source_found=True
            if a['state_sha256']!=source['state_sha256']:return False
            if a['original_source_contact_history']!=a['native_contact_history']:return False
        elif not p.get('actual_original_objects_axis_seed_solver_controller_and_clock_verified'):return False
        labels.add(label)
    return source_found and labels=={0,1}


def t03_box_diagnostic_disposition(source,endpoints,audit):
    """Dispose the impossible box-depth scalar without certifying all physics.

    Saved-frame OBB checks are a different measurement from internal-substep
    telemetry. Keep both, require exact state identities, and admit only the
    original conjunction's observed interval under the original runtime.
    """
    if not(source.get('status')=='completed'and source.get('source_event_match')and
        source.get('objects_match')and not source.get('physical_solver_differences')):return False
    if audit.get('source_files_modified')is not False or audit.get('new_simulations')!=0:return False
    points=[dict(source,theta=.1)]+endpoints
    if not endpoints or any(p.get('status')!='completed'for p in points):return False
    by_hash={p['state_sha256']:p for p in points}
    if len(audit.get('points',[]))!=len(by_hash):return False
    for a in audit['points']:
        p=by_hash.get(a['state_sha256'])
        if p is None or a['theta']!=p['theta']:return False
        if p['reference_video_sha256']!=source['reference_video_sha256']:return False
        if p is not points[0]and not p.get('original_config_physical_axis_seed_and_window_verified'):return False
        size=a['book_collision_size'];slab=a['slab_collision_size']
        bound=sum(x*x for x in size)**.5/2+slab[2]/2
        if abs(bound-a['pose_independent_geometric_depth_upper_bound_m'])>1e-12:return False
        if not(a['reported_depth_exceeds_any_pose_box_overlap_bound']and
            a['maximum_internal_reported_depth_m']>bound and a['all_saved_frames_finite']and
            not a['saved_frames_above_1mm']and a['maximum_saved_frame_box_overlap_m']<=.001 and
            a['internal_peak_pose_reconstructed']is False):return False
    return {p['measurement']['label']for p in points}=={0,1}


def t09_terminal_event_closure(points,audit):
    """Same original profile and stable named terminal event; not full QA."""
    if audit.get('source_files_modified')is not False or audit.get('new_simulations')!=0:return None
    if audit.get('original_event')!='upper_nonpulled_book_on_table_at_end':return None
    source=next((p for p in points if p.get('source_repeat')),None)
    if source is None or source['measurement']['label']!=source['source_measurement']['label']:return None
    if not source.get('source_position_error_m')or max(source['source_position_error_m'].values())>.001:return None
    by_hash={p['state_sha256']:p for p in points if p.get('status')=='completed'}
    observations=[]
    for a in audit.get('points',[]):
        p=by_hash.get(a['state_sha256'])
        if p is None or a['theta']!=p['theta']:return None
        if not p['actual_objects_solver_seed_control_and_clock_verified']:return None
        if p['source_state_sha256']!=source['source_state_sha256']or p['reference_video_sha256']!=source['reference_video_sha256']:return None
        if not(a['window']==[4,209]and a['native_fps']==30 and abs(a['simulation_frame_period_s']-.02)<1e-12 and a['all_saved_positions_finite']):return None
        fs=a['terminal_frames'];label=p['measurement']['label']
        if [f['frame']for f in fs]!=list(range(200,210)):return None
        if any(f['label']!=label or f['target_table_maximum_contact_depth_m']>.001 or
            (label==1 and(not f['independently_confirmed_top_contact_witness_books']or f['minimum_target_bottom_to_table_plane_distance_m']>.001))or
            not f['all_target_contacts_inside_support']for f in fs):return None
        observations.append(p)
    if len(observations)!=len(points):return None
    ordered=sorted(observations,key=lambda p:p['theta'])
    intervals=[dict(event='upper_nonpulled_book_on_table_at_end',bracket=[a['theta'],b['theta']],
        endpoint_labels=[a['measurement']['label'],b['measurement']['label']],
        endpoint_state_sha256=[a['state_sha256'],b['state_sha256']])
        for a,b in zip(ordered,ordered[1:])if a['measurement']['label']!=b['measurement']['label']]
    return dict(source=source,points=observations,intervals=intervals,audit=audit)if intervals else None


def build():
    roster,manifest,tasks,mapping=load_roster();_,_,supp=load_supplement()
    retained={r['clip_id']:r for r in read(roster/'retained_distance_references.json')['cases']}
    swap={r['clip_id']:r['supplement_point_id']for r in mapping};new={r['point_id']:r for r in supp['points']}
    cohort_path=ROOT/'annotation_site/resources/core100_formal_cohorts.json'
    cohorts=read(cohort_path);admissions=[r for c in cohorts['cohorts']for r in c['references']]
    obs_path=ROOT/'annotation_site/resources/core100_reference_observability_progress.json'
    obs={r['clip_id']:r for r in read(obs_path)['cases']}
    contract_path=ROOT/'annotation_site/resources/event_contracts.json'
    contracts=read(contract_path)['clips']
    t19_contract_path=ROOT/'benchmarks/core100_t19_isaac_v1_20261031/event_protocols.json'
    t19_contracts=read(t19_contract_path)
    native_readback_path=ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    native_readbacks={r['clip_id']:r for r in read(native_readback_path)}
    t02_pointer=read(WORK/'T02_FULL_WINDOW.json');t02_file=ROOT/t02_pointer['path']
    assert sha(t02_file)==t02_pointer['sha256'];t02={r['clip_id']:r for r in read(t02_file)['cases']}
    t20_pointer=read(WORK/'T20_ORIGINAL_GAP.json');t20_file=ROOT/t20_pointer['path']
    assert sha(t20_file)==t20_pointer['sha256'];t20=read(t20_file)
    t07_pointer=read(WORK/'T07_PUBLISHED.json');t07_file=ROOT/t07_pointer['path']
    assert sha(t07_file)==t07_pointer['sha256'];t07={r['clip_id']:r for r in read(t07_file)['cases']}
    t14_pointer=read(WORK/'T14_ORIGINAL_A.json');t14_file=ROOT/t14_pointer['path']
    assert sha(t14_file)==t14_pointer['sha256'];t14={r['clip_id']:r for r in read(t14_file)['cases']}
    t03_pointer=read(WORK/'T03_ORIGINAL_A.json');t03_file=ROOT/t03_pointer['path']
    assert sha(t03_file)==t03_pointer['sha256'];t03_report=read(t03_file);t03={r['clip_id']:r for r in t03_report['cases']}
    t15_pointer=read(WORK/'T15_ORIGINAL_PUBLISHED.json');t15_file=ROOT/t15_pointer['path']
    assert sha(t15_file)==t15_pointer['sha256'];t15={r['clip_id']:r for r in read(t15_file)['cases']}
    t06_pointer=read(WORK/'T06_ISAAC_EXISTING.json');t06_file=ROOT/t06_pointer['path']
    assert sha(t06_file)==t06_pointer['sha256'];t06=read(t06_file)
    assert t06['clip_id']=='T06_C04'and t06['new_simulations']==0
    assert all(p['original_engine_seed_force_mode_clock_and_physical_objects_verified']and p['damping_refinement_factor']==1 for p in t06['points'])
    assert next(p for p in t06['points']if p['theta']==t06['theta'])['source_trajectory_exact']
    t20_speed_pointer=read(WORK/'T20_SAVED_SPEED.json');t20_speed_file=ROOT/t20_speed_pointer['path']
    assert sha(t20_speed_file)==t20_speed_pointer['sha256'];t20_speed={r['clip_id']:r for r in read(t20_speed_file)['cases']}
    t20_canonical={};t20_canonical_files=[];t20_canonical_reports=[]
    for stage in ['SOURCE','ENDPOINTS']:
        pointer_path=WORK/('T20_CANONICAL_GPU_'+stage+'_RESULT.json')
        if pointer_path.exists():
            pointer=read(pointer_path);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
            t20_canonical_files.append(path);t20_canonical_reports.append(read(path))
    if len(t20_canonical_reports)==2:t20_canonical=recovered_frozen_t20(*t20_canonical_reports)
    extension_pointer=WORK/'T20_CANONICAL_GPU_GAP_EXTENSION_RESULT.json'
    if len(t20_canonical_reports)==2 and extension_pointer.exists():
        pointer=read(extension_pointer);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        t20_canonical_files.append(path);extension=read(path)
        combined=copy.deepcopy(t20_canonical_reports[1]);combined['points']+=extension['points']
        t20_canonical.update(recovered_frozen_t20(t20_canonical_reports[0],combined))
    t08_attempts={};t08_attempt_files=[]
    for stage in ['SOURCE','ENDPOINTS']:
        pointer_path=WORK/('T08_GPU_'+stage+'_RESULT.json')
        if pointer_path.exists():
            pointer=read(pointer_path);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];report=read(path)
            if report['status']=='completed':
                t08_attempt_files.append(path)
                for p in report['points']:t08_attempts.setdefault(p['clip_id'],{})[stage.lower()]=p
    t08_refined={};t08_refined_files=[]
    if(WORK/'T08_APPROVED_REFINEMENT.json').exists():
        pointer=read(WORK/'T08_APPROVED_REFINEMENT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];report=read(path)
        assert report['author_authorization']['decision']=='允许数值细化，单列配置与不确定性'
        t08_refined_files.append(path)
        for name,digest in report['source_hashes'].items():
            source=ROOT/name;assert sha(source)==digest;t08_refined_files.append(source)
        for r in report['cases']:
            audit=read(ROOT/r['refined_state_audit']);r=copy.deepcopy(r)
            r['numerical_source']=next(p for p in audit['verified_points']if p['kind']=='point'and p['theta']==r['theta'])
            t08_refined[r['clip_id']]=r
    t15_gpu={};t15_gpu_files=[]
    if(WORK/'T15_GPU_RESULT.json').exists():
        pointer=read(WORK/'T15_GPU_RESULT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        report=read(path)
        if report['status']=='completed':
            t15_gpu_files.append(path)
            for cid in ['T15_C01','T15_C02','T15_C03']:
                points=sorted([p for p in report['points']if p['clip_id']==cid],key=lambda p:p['theta'])
                assert len(points)==2 and {p['kind']for p in points}=={'source','low'}
                assert all(p['original_profile_seed_and_clock_verified']and p['original_physical_inputs_except_declared_speed_verified']for p in points)
                assert [p['measurement']['label']for p in points]==[0,1]
                source=next(p for p in points if p['kind']=='source')
                assert source['source_measurement']['label']==source['measurement']['label']==source['reference_label']
                assert source['source_measurement']['first_threshold_frame']==source['measurement']['first_threshold_frame']
                t15_gpu[cid]=dict(source=source,points=points)
    width_pointer=read(WORK/'T14_EXISTING_WIDTH.json');width_file=ROOT/width_pointer['path']
    assert sha(width_file)==width_pointer['sha256'];width=read(width_file)
    assert width['clip_id']=='T14_C03'and width['points'][0]['label']==1
    assert all(p['original_physics_and_axis_verified']and p['native_peak_m']<=.001 for p in width['points'])
    t18_sources=[]
    for name in ['T18_CONTEXT_AUDIT.json','T18_SAVED_FRICTION.json']:
        pointer=read(WORK/name);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];t18_sources.append(path)
    pending_audit_files=[WORK/name for name in ['t04_original_receipts.json','t04_contact_anomaly_audit.json',
        't18_overlap_existing_jobs_vs_frozen.json','t18_original_context_cpu_candidates.json','t18_overlap_existing_results.json']if(WORK/name).exists()]
    t04_saved_geometry=None
    if(WORK/'T04_SAVED_GEOMETRY.json').exists():
        pointer=read(WORK/'T04_SAVED_GEOMETRY.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        t04_saved_geometry=read(path);pending_audit_files+=[path,ROOT/'scripts/audit_core100_v2_t04_saved_geometry.py']
    t03_original_source=None;t03_original_files=[]
    if(WORK/'T03_ORIGINAL_GPU_SOURCE_RESULT.json').exists():
        pointer=read(WORK/'T03_ORIGINAL_GPU_SOURCE_RESULT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        report=read(path);t03_original_files.append(path)
        if report['status']=='completed':t03_original_source=report
    t03_original_endpoints=[];t03_dense_review=None;t03_geometry=None
    if(WORK/'T03_CONTACT_GEOMETRY_COLLECT.json').exists():
        pointer=read(WORK/'T03_CONTACT_GEOMETRY_COLLECT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        report=read(path);t03_original_files.append(path)
        if report.get('status')=='completed':
            t03_geometry=report['result']
            for name in ['scripts/audit_core100_v2_t03_contact_geometry.py','review/core100_v2_resolution_20261102/t03_dynamic_builder_contract.json']:
                t03_original_files.append(ROOT/name)
    if(WORK/'T03_ORIGINAL_GPU_ENDPOINTS_RESULT.json').exists():
        pointer=read(WORK/'T03_ORIGINAL_GPU_ENDPOINTS_RESULT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        t03_original_files.append(path);t03_original_endpoints=read(path)['points']
    if(WORK/'T03_C01_DENSE_RGB_REVIEW.json').exists():
        path=WORK/'T03_C01_DENSE_RGB_REVIEW.json';t03_dense_review=read(path);t03_original_files.append(path)
        assert t03_dense_review['source_pixels_only']
        assert [f for group in t03_dense_review['groups']for f in group['frames']]==list(range(100,155))
        for group in t03_dense_review['groups']:
            path=ROOT/group['image_path'];assert sha(path)==group['image_sha256'];t03_original_files.append(path)
    t10_reconstruction_files=[WORK/name for name in ['t10_metadata_source_comparison.json','t10_original_seed_formula_probe.json',
        't10_p26_matching_config_search.json','t10_p26_sample_file_search.json']if(WORK/name).exists()]
    if(WORK/'T10_VALID_SUPPORT_DISPATCH.json').exists():
        pointer=read(WORK/'T10_VALID_SUPPORT_DISPATCH.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];t10_reconstruction_files.append(path)
    t10_valid_points=[]
    if(WORK/'T10_VALID_SUPPORT_RESULT.json').exists():
        pointer=read(WORK/'T10_VALID_SUPPORT_RESULT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];t10_reconstruction_files.append(path)
        t10_valid_points=read(path)['points']
    legacy_exact={};legacy_exact_files=[];t09_terminal=None
    if(WORK/'LEGACY_EXACT_COLLECT.json').exists():
        pointer=read(WORK/'LEGACY_EXACT_COLLECT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];legacy_exact_files.append(path)
        for p in read(path)['points']:legacy_exact.setdefault(p['clip_id'],[]).append(p)
    if(WORK/'T09_TERMINAL_GEOMETRY.json').exists():
        pointer=read(WORK/'T09_TERMINAL_GEOMETRY.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];legacy_exact_files.append(path)
        report=read(path)
        for name,digest in report['source_hashes'].items():
            p=ROOT/name;assert sha(p)==digest;legacy_exact_files.append(p)
        t09_terminal=t09_terminal_event_closure(legacy_exact.get('T09_C01',[]),report)
    t18_dispatched_cases=set()
    for path in WORK.glob('t18_gpu_endpoints_launch_*.json'):
        t18_dispatched_cases.update(p['clip_id']for p in read(path).get('started',[]))
    legacy_recovered={};legacy_recovered_files=[]
    if(WORK/'LEGACY_RELEASED_RECOVERY.json').exists():
        pointer=read(WORK/'LEGACY_RELEASED_RECOVERY.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        report=read(path);legacy_recovered_files.append(path)
        for name,digest in report['source_hashes'].items():
            source=ROOT/name;assert sha(source)==digest;legacy_recovered_files.append(source)
        legacy_recovered={r['clip_id']:r for r in report['cases']}
    t10_old_version=None;t10_old_version_files=[]
    if(WORK/'T10_C05_EXECUTED_VERSION.json').exists():
        pointer=read(WORK/'T10_C05_EXECUTED_VERSION.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        t10_old_version=read(path);t10_old_version_files.append(path)
        for name,digest in t10_old_version['source_hashes'].items():
            source=ROOT/name;assert sha(source)==digest;t10_old_version_files.append(source)
    t18_gpu_attempts={};t18_gpu_attempt_files=[]
    for name in ['T18_GPU_SOURCE_RESULT.json','T18_GPU_OVERLAP_SOURCE_RESULT.json']:
        if (WORK/name).exists():
            pointer=read(WORK/name);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
            t18_gpu_attempt_files.append(path)
            for point in read(path)['points']:
                if point['status']=='completed':t18_gpu_attempts[point['clip_id']]=point
    t18_gpu_endpoints={}
    if(WORK/'T18_GPU_ENDPOINTS_RESULT.json').exists():
        pointer=read(WORK/'T18_GPU_ENDPOINTS_RESULT.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
        t18_gpu_attempt_files.append(path)
        for point in read(path)['points']:
            t18_gpu_endpoints.setdefault(point['clip_id'],[]).append(point)
    t18_terminal_audits={};t18_c05_witness=None
    if(WORK/'T18_C05_EVENT_EQUIVALENCE.json').exists():
        pointer=read(WORK/'T18_C05_EVENT_EQUIVALENCE.json');path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];t18_sources.append(path)
        t18_c05_witness=read(path)
        for name,digest in t18_c05_witness['source_hashes'].items():
            p=ROOT/name;assert sha(p)==digest;t18_sources.append(p)
    for cid in ['T18_C03','T18_C04','T18_C05']:
        pointer_path=WORK/(cid+'_TERMINAL_CONTACT_AUDIT.json')
        if not pointer_path.exists():continue
        pointer=read(pointer_path);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];report=read(path)
        t18_gpu_attempt_files.append(path)
        for name,digest in report['source_hashes'].items():
            item=ROOT/name;assert sha(item)==digest;t18_gpu_attempt_files.append(item)
        t18_terminal_audits[cid]=report
    t07_gpu={};t07_gpu_files=[]
    if(WORK/'T07_GPU_ENDPOINTS_RESULT.json').exists():
        reports=[]
        for name in ['T07_GPU_SOURCE_RESULT.json','T07_GPU_ENDPOINTS_RESULT.json']:
            pointer=read(WORK/name);path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
            reports.append(read(path));t07_gpu_files.append(path)
        assert all(r['status']=='completed'for r in reports)
        for source in reports[0]['points']:
            points=sorted([p for p in reports[1]['points']if p['clip_id']==source['clip_id']],key=lambda p:p['theta'])
            assert source['original_source_specs_match']and source['original_source_solver_differences']=={}
            assert source['quality_passed']and source['measurement']['label']==source['reference_measurement']['label']
            assert source['measurement']['first_threshold_frame']==source['reference_measurement']['first_threshold_frame']
            assert len(points)==2 and all(p['quality_passed']and p['original_seed_solver_and_intervention_verified']for p in points)
            if len({p['measurement']['label']for p in points})==2:
                t07_gpu[source['clip_id']]=dict(source=source,points=points)
    t16=None;t16_sources=[]
    if (WORK/'T16_GPU_ENDPOINT_RESULT.json').exists():
        ep=read(WORK/'T16_GPU_ENDPOINT_RESULT.json');sp=read(WORK/'T16_GPU_SOURCE_RESULT.json')
        for pointer in [ep,sp]:
            path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];t16_sources.append(path)
        endpoints=read(t16_sources[0]);source=read(t16_sources[1])
        points=sorted(endpoints['points'],key=lambda r:r['theta'])
        assert endpoints['status']=='completed'and len(points)==2
        assert source['source_solver_differences']=={}and source['native_peak_penetration_m']<=.001
        assert source['reference_label']==source['replay_label']==1
        assert source['original_contact_frames']==source['replay_contact_frames']
        assert all(p['quality_passed']and p['actual_original_intervention_verified']and p['original_seed_solver_and_clock_verified']for p in points)
        if len({p['labels']['folder_downstream_contact']for p in points})==2:
            t16=dict(source=source,endpoints=endpoints,bracket=[p['theta']for p in points],labels=[p['labels']['folder_downstream_contact']for p in points])
    cases=[]
    for task in tasks:
        cid=task['clip_id']
        if cid in swap:
            key=new[swap[cid]];b=key['boundary'];event=key['target_event']
            row=dict(clip_id=cid,scene_id=cid[:3],sample_id=task['sample_id'],
                reference_video_sha256=key['reference_video_sha256'],horizon_s=key['evaluation_duration_s'],
                condition_frame_index=4,end_frame_index=key['end_frame_index'],parameter=key['family_id'],
                theta=key['theta'],normalization_domain=key['normalization_domain'],
                normalization_span=b['normalization_span'],reference_events=key['events'],
                fixed_context_sha256=key['fixed_context_sha256'],source_state_sha256=key['source_state_sha256'],
                boundary_records=[dict(event=event,bracket=b['bracket'],endpoint_labels=next(p['endpoint_labels']for p in supp['pairs']if swap[cid]in p['points']),
                    distance=key['distance'],interval_kind='observed_published_transition',exact_theta_star=None)],
                conditional_axes={},evidence=[dict(file='benchmarks/critical_supplement_v1_20261101/MANIFEST.json')],
                binding_kind='published_contrast_replacement',reference_admission=key['reference_admission'],
                original_roster_replacement=True,source_point_axes={},inversion=key['inversion'])
        else:
            row=copy.deepcopy(retained[cid]);row['original_roster_replacement']=False
        if cid=='T20_C01':
            # Restore the recovered original gap axis, not the useful but
            # different speed-axis supplement. Keep its quality diagnostic.
            primary=row['legacy_primary_axis']
            assert primary['parameter']==t20['family']=='box_cup_gap'
            assert row['sample_id']==t20['sample_id']and row['theta']==t20['source_theta']
            for boundary in primary['boundary_records']:
                for theta,label in zip(boundary['bracket'],boundary['endpoint_labels']):
                    assert any(abs(p['theta']-theta)<1e-10 and p['labels'][boundary['event']]==label
                        and p['original_seed_solver_and_intervention_verified']for p in t20['observed'])
            row['boundary_records']=copy.deepcopy(primary['boundary_records'])
            row['evidence'].append(dict(file=t20_pointer['path']))
            row['native_quality_limit']=dict(status='retained_failed_original_1mm_penetration_check',
                original_source_peak_m=t20['observed'][0]['all_contact_peak_m'],
                scope='Native dynamic book-can penetration also occurs in the source contract; no new physical-quality approval.',
                reference_distance_use='numerical fixed-simulator observation only; formal RGB distance admission pending')
        if cid in t02:
            recovered=t02[cid]
            assert recovered['reference_video_sha256']==row['reference_video_sha256']
            assert recovered['horizon_s']==row['horizon_s']and recovered['reference_label']==row['reference_events'][recovered['target_event']]
            if row.get('original_calibration_reference'):
                row['historical_calibration_reference']=row.pop('original_calibration_reference')
            row['boundary_records']=[]
            for b in recovered['intervals']:
                row['boundary_records'].append(dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                    interval_kind='observed_original_full_window_transition',exact_theta_star=None))
            row['binding_kind']='published_full_window_recovery';row['evidence'].append(dict(file=t02_pointer['path']))
        if cid=='T16_C04'and t16:
            assert t16['source']['source_state_sha256']==row['source_state_sha256']
            assert t16['source']['horizon_s']==row['horizon_s']
            row['historical_solver_profile_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(event='folder_downstream_contact',bracket=t16['bracket'],endpoint_labels=t16['labels'],
                distance=interval_distance(row['theta'],t16['bracket'],row['normalization_span']),
                interval_kind='original_setting_gpu32_local_transition',exact_theta_star=None)]
            row['original_gpu_contact_evidence']=dict(source=t16['source'],endpoints=t16['endpoints'],
                admission_scope='Same source predicate, contact frames and original settings. Full position trajectory is not claimed exact; no numerical-convergence claim.')
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t16_sources]
        if cid in t07 and t07[cid]['intervals']:
            recovered=t07[cid];source=recovered['source']
            assert row['source_state_sha256']in[source['stored_state_sha256'],source['state_sha256']]
            assert recovered['reference_video_sha256']==row['reference_video_sha256']
            assert row['horizon_s']==recovered['horizon_s']and row['theta']==source['theta']
            assert row['reference_events']==source['labels']
            row['historical_solver_profile_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(event=b['event'],bracket=b['bracket'],endpoint_labels=b['labels'],endpoints=b['endpoints'],
                distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                interval_kind='observed_original_published_friction_transition',exact_theta_star=None)for b in recovered['intervals']]
            row['fixed_context_sha256']=source['fixed_context_sha256']
            row['binding_kind']='original_published_friction_recovery'
            row['evidence'].append(dict(file=t07_pointer['path']))
        if cid in t07_gpu:
            recovered=t07_gpu[cid];source=recovered['source'];points=recovered['points']
            assert source['source_state_sha256']==row['source_state_sha256']and source['horizon_s']==row['horizon_s']
            assert source['measurement']['label']==row['reference_events']['motion_ge_1cm']
            bracket=[p['theta']for p in points]
            row['historical_solver_profile_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(event='motion_ge_1cm',bracket=bracket,endpoint_labels=[p['measurement']['label']for p in points],
                distance=interval_distance(row['theta'],bracket,row['normalization_span']),
                interval_kind='original_setting_gpu32_observed_local_transition',exact_theta_star=None)]
            row['original_gpu_motion_evidence']=recovered
            row['binding_kind']='original_setting_gpu32_motion_recovery'
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t07_gpu_files]
        if cid in t14:
            recovered=t14[cid]
            assert row['reference_video_sha256']==recovered['reference_video_sha256']
            assert row['horizon_s']==recovered['horizon_s']and row['theta']==recovered['theta']
            assert row['reference_events']['passed_channel']==recovered['label']
            row['historical_context_unresolved_refinement_records']=row['boundary_records']
            row['boundary_records']=[dict(event='passed_channel',bracket=recovered['bracket'],endpoint_labels=[0,1],
                distance=interval_distance(row['theta'],recovered['bracket'],row['normalization_span']),
                interval_kind='original_released_A_bracket',exact_theta_star=None)]
            row['fixed_context_sha256']=recovered['fixed_context_sha256']
            row['source_state_sha256']=recovered['source_state_sha256']
            row['original_calibration_contract_sha256']=recovered['source_calibration_contract_sha256']
            row['binding_kind']='original_released_A_bracket_recovery'
            row['evidence'].append(dict(file=t14_pointer['path']))
        if cid in t03:
            recovered=t03[cid]
            assert row['reference_video_sha256']==recovered['reference_video_sha256']
            assert row['source_state_sha256']==recovered['source_state_sha256']and row['theta']==recovered['theta']
            assert row['reference_events']['book_contacts_upper_can']==recovered['label']
            row['historical_independent_diagnostic_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(event='book_contacts_upper_can',bracket=t03_report['bracket'],endpoint_labels=[0,1],
                distance=interval_distance(row['theta'],t03_report['bracket'],row['normalization_span']),
                interval_kind='original_released_cf_A_contact_contrast',exact_theta_star=None)]
            row['fixed_context_sha256']=recovered['fixed_context_sha256']
            row['binding_kind']='original_released_cf_A_contact_recovery'
            row['original_released_contrast_evidence']=recovered
            row['evidence'].append(dict(file=t03_pointer['path']))
        if cid=='T14_C03':
            assert row['source_state_sha256']==width['source_state_sha256']
            assert row['reference_video_sha256']==width['reference_video_sha256']and row['horizon_s']==width['horizon_s']
            row['original_gpu_width_evidence']=dict(width,
                axis_origin='Original A width family, conditioned at the frozen G source input; not an original single-axis G calibration.',
                timing_scope='Replay first exit frame43 versus original45; only the ever-passage target is admitted, not exact event timing or the complete chain.')
            row['evidence'].append(dict(file=width_pointer['path']))
        if cid in t15:
            recovered=t15[cid];source=recovered['source']
            assert row['reference_video_sha256']==recovered['reference_video_sha256']
            assert row['source_state_sha256']==source['state_sha256']and abs(row['theta']-source['theta'])<1e-10
            assert row['horizon_s']==source['horizon_s']and row['reference_events'][recovered['event']]==source['label']
            row['original_published_context_recovery']=recovered
            row['evidence'].append(dict(file=t15_pointer['path']))
            if recovered['intervals']:
                assert not recovered['conflicting_theta_labels']
                row['historical_solver_profile_boundary_records']=row['boundary_records']
                row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                    interval_kind='original_V11_published_observed_transition',exact_theta_star=None)for b in recovered['intervals']]
                row['fixed_context_sha256']=source['fixed_context_sha256']
                row['binding_kind']='original_V11_published_transition_recovery'
        if cid in t15_gpu:
            recovered=t15_gpu[cid];source=recovered['source'];points=recovered['points']
            assert row['source_state_sha256']==source['source_state_sha256']and row['theta']==source['theta']
            assert points[0]['theta']==row['normalization_domain'][0]
            row['historical_solver_profile_boundary_records']=row['boundary_records']
            bracket=[p['theta']for p in points]
            row['boundary_records']=[dict(event='laptop_reaches_original_fall_criterion',bracket=bracket,endpoint_labels=[0,1],
                distance=interval_distance(row['theta'],bracket,row['normalization_span']),
                interval_kind='original_V11_GPU64_source_and_low_domain_observed_transition',exact_theta_star=None)]
            row['original_V11_GPU64_evidence']=dict(recovered,
                scope='Original solver, seed15 and physical input at frozen source; first threshold frame reproduced. Coarse interval, not a unique root, exact full trajectory or new physical-quality certification.')
            row['binding_kind']='original_V11_GPU64_source_and_low_endpoint_recovery'
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t15_gpu_files]
        if cid=='T06_C04':
            assert row['source_state_sha256']==t06['source_state_sha256']and row['reference_video_sha256']==t06['reference_video_sha256']
            assert row['horizon_s']==t06['horizon_s']and row['theta']==t06['theta']
            assert row['reference_events']['complete_required_contact_chain']==t06['native_source_measurement']['label']
            assert [b['bracket']for b in row['boundary_records']]==[b['bracket']for b in t06['intervals']]
            row['original_isaac_existing_search_evidence']=t06
            row['binding_kind']='original_isaac_force_waveform_existing_result_recovery'
            row['evidence'].append(dict(file=t06_pointer['path']))
        if cid in t20_speed:
            recovered=t20_speed[cid]
            row['original_published_speed_readback']=recovered
            row['evidence'].append(dict(file=t20_speed_pointer['path']))
            if recovered['intervals']:
                source=recovered['source']
                assert row['source_state_sha256']in[source['stored_state_sha256'],source['decoded_state_sha256']]
                assert row['reference_video_sha256']==recovered['reference_video_sha256']and row['theta']==source['theta']
                assert row['horizon_s']==source['horizon_s']and row['reference_events']['complete_propagation_original']==source['label']
                row['historical_conditional_diagnostic_boundary_records']=row['boundary_records']
                row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                    interval_kind='original_released_book_speed_observed_transition',exact_theta_star=None)for b in recovered['intervals']]
                row['fixed_context_sha256']=source['fixed_context_sha256']
                row['binding_kind']='original_released_book_speed_transition_recovery'
        if cid in t08_attempts:
            row['original_GPU_attempt_evidence']=t08_attempts[cid]
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t08_attempt_files]
            row['distance_admission_pending_reason']='按原记录设置复跑的源点/低端出现书本与桌面异常接触；保留结果但不把该批数值放行为可靠边界。现有64位数值精化候选的采用规则待作者确认，原视频、标签及普通事件准入未改。'
        if cid in t08_refined:
            refined=t08_refined[cid]
            assert refined['reference_video_sha256']==row['reference_video_sha256']and refined['theta']==row['theta']
            assert refined['parameter']==row['parameter']and refined['horizon_s']==row['horizon_s']
            assert refined['normalization_domain']==row['normalization_domain']
            assert refined['original_physical_specs_preserved']and refined['original_event_labels_preserved']and refined['source_primary_event_matches']
            row['historical_unapproved_refinement_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                interval_kind='author_approved_cpu64_refined_observed_interval',exact_theta_star=None)for b in refined['intervals']]
            row['author_approved_numerical_refinement']=refined
            row['numerical_reference_profile']=refined['numerical_reference_profile']
            row['published_physical_source_state_sha256']=refined['source_state_sha256']
            row['source_state_sha256']=refined['numerical_source']['state_sha256']
            row['binding_kind']='author_approved_cpu64_refined_observed_interval'
            row['distance_admission_pending_reason']=None
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t08_refined_files]
        if cid=='T03_C01'and t03_original_source:
            assert t03_original_source['reference_video_sha256']==row['reference_video_sha256']
            assert t03_original_source['source_state_sha256']==row['source_state_sha256']
            row['original_shared_runtime_GPU_source_diagnostic']=t03_original_source
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t03_original_files]
            row['distance_admission_pending_reason']='原T01共享运行链GPU32源点已复现主事件0和前三接触帧；晚段轨迹有偏差，原C族三个端点已派发。原生接触深度与实际几何仍交叉核查，不自动放行旧GPU64网格。'
            completed=[p for p in t03_original_endpoints if p['status']=='completed']
            points=sorted([dict(theta=.1,measurement=t03_original_source['measurement'],state_sha256=t03_original_source['state_sha256'])]+completed,key=lambda p:p['theta'])
            for p in completed:
                assert p['original_config_physical_axis_seed_and_window_verified']and p['reference_video_sha256']==row['reference_video_sha256']
            intervals=[dict(event='phone_second_fall_original',bracket=[a['theta'],b['theta']],
                endpoint_labels=[a['measurement']['label'],b['measurement']['label']],endpoint_state_sha256=[a['state_sha256'],b['state_sha256']])
                for a,b in zip(points,points[1:])if a['measurement']['label']!=b['measurement']['label']]
            row['original_shared_runtime_GPU_endpoint_diagnostic']=dict(points=completed,intervals=intervals,formal_admission=False)
            if intervals:
                row['historical_independent_gpu64_boundary_records']=row['boundary_records']
                row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                    interval_kind='original_shared_runtime_gpu32_observed_interval_pending_contact_disposition',exact_theta_star=None)for b in intervals]
                row['distance_admission_pending_reason']='原共享GPU32已完成三个端点，找到手机二次跌落／未跌落区间[0.0843333333,0.1]米；数值已绑定。原生内部深度读数仍待同步几何核验，未改用旧GPU64区间或宣称正式距离完成。'
                if t03_geometry and t03_box_diagnostic_disposition(t03_original_source,completed,t03_geometry):
                    row['native_contact_diagnostic_disposition']=dict(evidence=t03_geometry,
                        disposition='Reported scalar exceeds the pose-independent box-overlap bound; it cannot be interpreted as visible box penetration of that depth. All 151 saved-frame OBB checks independently remain below 1 mm.',
                        scope='Original fixed-profile phone-second-fall interval only. Raw telemetry and late source drift retained; internal peak poses, convergence and full physical quality are not certified.')
                    row['original_shared_runtime_GPU_endpoint_diagnostic']['formal_admission']=True
                    row['binding_kind']='original_shared_runtime_gpu32_observed_event_interval'
                    row['distance_admission_pending_reason']=None
                    for b in row['boundary_records']:b['interval_kind']='original_shared_runtime_gpu32_observed_event_interval_box_diagnostic_disposed'
        if cid in legacy_exact:
            row['original_recipe_GPU_probe_diagnostic']=dict(points=legacy_exact[cid],
                scope='Actual original configurations and seeds. T06 mixed-width arc regenerated, source controls preserved. Probes outside the published domain do not expand normalization.')
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in legacy_exact_files]
            if cid.startswith('T06'):
                row['distance_admission_pending_reason']='已按原配置、原种子和混合书宽弧线规则复跑源点、0.12及0.1225米；全部完成接触链，尚未找到反侧端点。旧只移动x的条件补扫另存，不作为原弧线族边界。'
        if cid=='T09_C01'and t09_terminal:
            source=t09_terminal['source'];assert source['reference_video_sha256']==row['reference_video_sha256']
            assert source['source_measurement']['label']==row['reference_events']['upper_nonpulled_book_on_table_at_end']
            row['historical_unclosed_contact_boundary_records']=row['boundary_records']
            row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                interval_kind='original_gpu_terminal_event_observed_interval_verified_terminal_contact',exact_theta_star=None,
                outside_original_parameter_domain=any(not row['normalization_domain'][0]<=x<=row['normalization_domain'][1]for x in b['bracket']))for b in t09_terminal['intervals']]
            row['source_state_sha256']=source['source_state_sha256']
            row['original_GPU_T09_terminal_event_closure']=t09_terminal
            row['binding_kind']='original_gpu_terminal_event_observed_interval'
            row['distance_admission_pending_reason']=None
        if cid in t20_canonical:
            recovered=t20_canonical[cid];source=recovered['source']
            assert row['source_state_sha256']==source['old_numerical_state_sha256']
            assert row['reference_video_sha256']==source['reference_video_sha256']and row['theta']==source['theta']
            assert row['reference_events']['complete_propagation_original']==source['source_measurement']['label']
            row['historical_production_boundary_records']=row['boundary_records']
            row['historical_production_state_sha256']=row['source_state_sha256']
            row['source_state_sha256']=source['reference_native_state_sha256']
            row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                interval_kind='frozen_geometry_r3_original_gpu32_observed_transition',exact_theta_star=None)for b in recovered['intervals']]
            row['frozen_original_gpu_contact_evidence']=recovered
            row['binding_kind']='frozen_geometry_r3_original_gpu32_transition_recovery'
            row['distance_admission_pending_reason']=None
            row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t20_canonical_files]
        if cid.startswith('T18'):
            row['original_sampling_context_evidence']=[p.relative_to(ROOT).as_posix()for p in t18_sources]
            row['distance_admission_pending_reason']='已有区间来自固定源配置的条件补扫；原发布相邻摩擦ID同时改变书本数量、摆放和抽取方式，不能当作同一堆书的两侧。原GPU条件边界对应仍待核准。'
            if cid in t18_gpu_attempts:
                row['original_GPU_source_replay_diagnostic']=t18_gpu_attempts[cid]
                row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t18_gpu_attempt_files]
                source=t18_gpu_attempts[cid];points=[]
                assert source['source_state_sha256']==row['source_state_sha256']
                assert source['reference_video_sha256']==row['reference_video_sha256']
                assert source['source_label_matches']and source['original_specs_solver_seed_and_controller_preserved']
                for p in t18_gpu_endpoints.get(cid,[]):
                    if p['status']!='completed':continue
                    assert p['actual_original_objects_axis_seed_solver_controller_and_clock_verified']
                    assert p['source_state_sha256']==row['source_state_sha256']
                    assert p['reference_video_sha256']==row['reference_video_sha256']and p['horizon_s']==row['horizon_s']
                    points.append(p)
                observed=sorted([source]+points,key=lambda p:p['theta'])
                intervals=[dict(event='upper_nonpulled_book_on_table_at_end',bracket=[a['theta'],b['theta']],
                    endpoint_labels=[a['measurement']['label'],b['measurement']['label']],
                    endpoint_state_sha256=[a['state_sha256'],b['state_sha256']],
                    endpoint_native_peak_penetration_m=[a['native_peak_penetration_m'],b['native_peak_penetration_m']],
                    outside_original_parameter_domain=any(not row['normalization_domain'][0]<=x<=row['normalization_domain'][1]for x in[a['theta'],b['theta']]))
                    for a,b in zip(observed,observed[1:])if a['measurement']['label']!=b['measurement']['label']]
                row['original_GPU_endpoint_diagnostic']=dict(
                    points=[dict(theta=p['theta'],label=p['measurement']['label'],state_sha256=p['state_sha256'],
                        native_peak_penetration_m=p['native_peak_penetration_m'])for p in observed],
                    intervals=intervals,formal_distance_admitted=False,
                    reason='Matching original-profile GPU transitions are retained. Native contact anomalies require disposition before RGB-distance admission; no-flip cases remain pending, not inapplicable.')
                if intervals:
                    row['historical_other_profile_boundary_records']=row['boundary_records']
                    row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                        interval_kind='original_t18_gpu_observed_transition_pending_contact_review',exact_theta_star=None)for b in intervals]
                    row['distance_admission_pending_reason']='原GPU源点已复现，原参数轴已找到两侧端点；数值区间已接入候选，接触诊断尚未核完，不自动准入正式RGB距离。'
                elif points:
                    row['distance_admission_pending_reason']='原GPU源点已复现，当前原参数轴端点仍无翻转；保留已有其他设置的诊断，不判不适用，也不宣称原GPU边界完成。'
                event_witness=False;trajectory_checked=False
                if cid in t18_terminal_audits and intervals:
                    audit=t18_terminal_audits[cid]
                    trajectory_checked=t18_terminal_audit_matches(source,points,audit)
                    if trajectory_checked:event_witness=True
                    elif cid=='T18_C03':
                        event_witness=t18_terminal_event_witness_matches(source,points,audit)and all(not a['earlier_frames_above_1mm']for a in audit['points'])
                    elif cid=='T18_C05'and t18_c05_witness:
                        original=t18_c05_witness['original'];a=next(a for a in audit['points']if a['kind']=='source')
                        event_witness=(t18_terminal_event_witness_matches(source,points,audit)and
                            original['reference_video_sha256']==row['reference_video_sha256']and
                            row['source_state_sha256']in[original['original_stored_state_sha256'],original['original_decoded_state_sha256']]and
                            original['original_contact_history']==a['native_contact_history']and
                            all(x['frame']==y['frame']and x['label']==y['label']and sorted(x['upper_books_on_table'])==sorted(y['upper_books_on_table'])for x,y in zip(original['original_terminal_frames'],a['terminal_frames'])))
                if event_witness:
                    audit=t18_terminal_audits[cid]
                    image=ROOT/'review/core100_remaining74_admission_20261101/reference_review'/cid/'original_sheet.jpg'
                    row['original_GPU_terminal_event_closure']=dict(
                        audit=audit,source_video_visual_review=dict(
                            reviewer='assistant_visual_review_not_independent_human_gold',
                            image_path=image.relative_to(ROOT).as_posix(),image_sha256=sha(image),
                            notes=('Named non-extracted upper book08 is upright and supported on the tabletop; the horizontally travelling extracted book07 is not the target.'if cid=='T18_C04'else
                                'Upper non-extracted books remain in a supported stack; the extracted travelling book is excluded.'if cid=='T18_C03'else
                                'The five upper non-extracted books lean onto the tabletop; the travelling extracted blue book is excluded.')),
                        source_full_window_position_error_m=source['source_maximum_position_difference_m'],
                        source_comparison_scope='full_trajectory_within_1mm_and_event_history'if trajectory_checked else'original_binary_event_history_and_named_terminal_witnesses_only',
                        exact_full_trajectory_equivalence_claimed=False,
                        scope='Only the original terminal table-contact event and its observed local boundary. Earlier transient contacts remain disclosed; full physical-quality, unique-root and convergence certification are not asserted.')
                    if cid=='T18_C05':row['original_GPU_terminal_event_closure']['additional_repeat_attempts']=t18_c05_witness
                    row['original_GPU_endpoint_diagnostic']['formal_distance_admitted']=True
                    row['original_GPU_endpoint_diagnostic']['reason']='Original event history and named terminal-contact witnesses closed; trajectory drift and early transient diagnostics retained separately.'
                    row['distance_admission_pending_reason']=None
                    row['binding_kind']='original_gpu_terminal_contact_observed_transition'
                    for boundary in row['boundary_records']:
                        boundary['interval_kind']='original_gpu_terminal_contact_observed_transition_verified_terminal_readback'
                    row['evidence'].append(dict(file=image.relative_to(ROOT).as_posix()))
            row['original_GPU_source_replay_is_not_endpoint_completion']=True
        if cid in['T03_C02','T03_C03']:
            row['distance_admission_pending_reason']='原二次跌落为正类，终端落地点超出当前画面；原C族边界、种子与实际版本的对应仍未闭合。上游事件标签保留，不据此准入完整二次跌落距离。'
        if cid=='T04_C02'and (WORK/'t04_contact_anomaly_audit.json')in pending_audit_files:
            audit=read(WORK/'t04_contact_anomaly_audit.json');assert audit['job']['clip_id']==cid
            row['original_GPU_contact_diagnostic']=dict(evidence='review/core100_v2_resolution_20261102/t04_contact_anomaly_audit.json',
                scope='Existing conditional GPU probes only; frozen reference acceptance and ordinary event label are unchanged.',
                deepest_pair=['t04v3_folder_ramp_pbr','t04v3_stack_book_bottom'],
                penetration_m_at_theta_0_125=.15131749212741852)
            row['distance_admission_pending_reason']='原设置候选虽有翻转，但源复跑最大位置差约0.119米，原配置及种子对应仍未认证。原生深度读数不直接等同可见穿模；保留候选、原视频及普通事件标签，原族距离仍待闭合。'
            if t04_saved_geometry:
                row['original_GPU_saved_geometry_diagnostic']=t04_saved_geometry
                row['distance_admission_pending_reason']='三条已存轨迹的书／斜面几何重叠均低于0.41毫米，不能把原生0.151米读数直接称为可见穿模。但原配置／种子对应仍未认证，源复跑最大位置差约0.119米；原族候选保留，尚未准入正式距离。'
        if cid in legacy_recovered:
            recovered=legacy_recovered[cid];source=recovered['source']
            assert row['reference_video_sha256']==recovered['reference_video_sha256']
            assert source['theta']==row['theta']and source['family']==row['parameter']
            assert source['horizon_s']==row['horizon_s']
            assert all(source['labels'][e]==y for e,y in row['reference_events'].items())
            row['original_released_sweep_recovery']=recovered
            row['evidence']+=[dict(file=legacy_recovered_files[0].relative_to(ROOT).as_posix())]
            if recovered['source_event_reference_admitted']:
                row['reference_cross_camera_event_binding']=dict(
                    state_path=source['state_path'],decoded_state_sha256=source['state_decoded_sha256'],
                    reference_video_sha256=row['reference_video_sha256'],
                    original_config_sha256=source['original_config_sha256'],
                    same_physical_config_and_seed_across_cameras=True,exact_same_trajectory_claimed=False,
                    evidence=legacy_recovered_files[0].relative_to(ROOT).as_posix(),
                    scope=recovered['observation_scope'])
                row['distance_admission_pending_reason']=recovered.get('boundary_pending_reason')
                if row['normalization_domain']!=recovered['normalization_domain']:
                    row['historical_normalization_domain']=row['normalization_domain']
                    row['normalization_domain']=recovered['normalization_domain']
                    row['normalization_span']=recovered['normalization_domain'][1]-recovered['normalization_domain'][0]
                    for boundary in row['boundary_records']:
                        boundary['distance']=interval_distance(row['theta'],boundary['bracket'],row['normalization_span'])
            if recovered['intervals']:
                assert recovered['source_event_reference_admitted']and recovered['fixed_physical_context_verified']
                row['historical_conditional_diagnostic_boundary_records']=row['boundary_records']
                row.setdefault('historical_normalization_domain',row['normalization_domain'])
                row['normalization_domain']=recovered['normalization_domain'];row['normalization_span']=recovered['normalization_domain'][1]-recovered['normalization_domain'][0]
                row['source_state_sha256']=source['state_decoded_sha256']
                row['boundary_records']=[dict(b,distance=interval_distance(row['theta'],b['bracket'],row['normalization_span']),
                    interval_kind='original_released_physical_context_observed_transition',exact_theta_star=None)for b in recovered['intervals']]
                row['binding_kind']='original_released_sweep_recovery_with_cross_camera_event_review'
        if cid=='T10_C05'and t10_old_version:
            assert row['reference_video_sha256']==t10_old_version['reference_video_sha256']
            row['historical_other_version_boundary_records']=row['boundary_records']
            row['historical_other_version_parameter_binding']=dict(parameter=row['parameter'],theta=row['theta'],normalization_domain=row['normalization_domain'])
            row['parameter']=t10_old_version['parameter'];row['theta']=t10_old_version['theta']
            row['normalization_domain']=t10_old_version['normalization_domain'];row['normalization_span']=row['normalization_domain'][1]-row['normalization_domain'][0]
            row['boundary_records']=[];row['source_state_sha256']=t10_old_version['source_state_sha256']
            row['executed_reference_version_recovery']=t10_old_version
            row['pending_primary_event']='support_pen_displacement_reaches_source_threshold'
            row['binding_kind']='matching_executed_version_boundary_pending'
            row['distance_admission_pending_reason']='原冻结输入对应支撑位置0.2171429米、初速3米/秒、倾角38度的旧版；同名新版0.1909米、1.8米/秒的区间已移到历史诊断，不再计算旧参考到该区间的距离。待找回或补算匹配旧版的边界。'
            row['evidence']+=[dict(file=t10_old_version_files[0].relative_to(ROOT).as_posix())]
            if(WORK/'t10_metadata_source_comparison.json').exists():
                row['metadata_reconstructed_source_seed_probes']=read(WORK/'t10_metadata_source_comparison.json')
                row['metadata_reconstruction_is_not_original_seed_recovery']=True
                row['evidence']+=[dict(file=p.relative_to(ROOT).as_posix())for p in t10_reconstruction_files]
                row['distance_admission_pending_reason']='旧版参数已按原执行记录恢复；重建种子0/1均重现接触(23,3)和达到4厘米的第25帧，但原种子尚未找回，未冒充原配置。按原38度几何合法端点约[0.19580,0.22155]米继续补扫，原归一化域[-0.05,0.28]不改。'
                if t10_valid_points:
                    row['metadata_reconstructed_valid_support_endpoints']=t10_valid_points
                    row['distance_admission_pending_reason']='旧版种子0/1的源点与合法支撑范围两端均已算完。四个端点支撑笔最大位移约0.322–0.324米，仍全为达到4厘米，尚未找到负端；不判不适用，不借用1.8米/秒新版边界。原种子未找回的限制保留。'
        assert row['reference_video_sha256']==task['reference']['sha256']
        gravity=next((f[1]for f in task.get('parameter_facts',[])if f[0]=='gravity'),None)
        row['declared_gravity_mps2']=gravity if gravity is not None else new[swap[cid]]['gravity']
        row['reference_release_version']=manifest['version']
        row['ordinary_generation_denominator_retained']=True
        own_admissions=[a for a in admissions if a['clip_id']==cid and a['reference_video_sha256']==row['reference_video_sha256']and abs(a['horizon_s']-row['horizon_s'])<1e-8]
        # Old records called their numerical source simply source_state. A
        # repaired frozen RGB reference can have a different native state.
        # Keep both identities; never silently attach production distances
        # to that repair just because the sample ID stayed the same.
        native=native_readbacks.get(cid)
        if cid not in swap and native and native.get('video_sha256')==row['reference_video_sha256']:
            point=native['points'][0]
            hashes={point.get(k)for k in['state_sha256','stored_state_sha256','decoded_state_sha256']}
            row['reference_native_state_binding']=dict(state_path=point['state_path'],
                decoded_state_sha256=point['decoded_state_sha256'],stored_state_sha256=point['stored_state_sha256'],
                reference_video_sha256=row['reference_video_sha256'],evidence=native_readback_path.relative_to(ROOT).as_posix(),
                scope='Frozen reference state identity only; does not independently certify the camera or the numerical boundary.')
            row['numerical_source_matches_reference_state_digest']=(row['source_state_sha256']in hashes if row.get('source_state_sha256')else None)
        elif cid in swap:
            row['reference_native_state_binding']=dict(decoded_state_sha256=row['source_state_sha256'],
                reference_video_sha256=row['reference_video_sha256'],evidence='benchmarks/critical_supplement_v1_20261101/MANIFEST.json',
                scope='Independently bound replacement source; old slot labels not transferred.')
            row['numerical_source_matches_reference_state_digest']=True
        row['rgb_reference_status']=('target_reference_admitted'if cid in swap or own_admissions else'observation_or_source_identity_pending')
        row['admitted_rgb_events']=(list(row['reference_events'])if cid in swap else list(dict.fromkeys(a['target_event']for a in own_admissions)))
        if cid=='T03_C01'and t03_dense_review and t03_original_source:
            assert t03_dense_review['video_sha256']==row['reference_video_sha256']
            assert t03_original_source['original_source']['label']==row['reference_events']['phone_second_fall_original']==0
            row['reference_RGB_primary_event_review']=dict(evidence=t03_dense_review,
                reviewer='assistant_visual_review_not_independent_human_gold',native_reference_label_preserved=0,
                notes='Phone remains visible on the lower shelf through frames100–154, including the protruding black end under the arriving book; no disappearance or floor event is inferred from occlusion. Original full-window native source confirms the conjunction is false.',
                scope='Reference negative primary event only; numerical-boundary contact diagnostic remains pending.')
            row['admitted_rgb_events']=list(dict.fromkeys(row['admitted_rgb_events']+['phone_second_fall_original']))
        if cid in legacy_recovered and legacy_recovered[cid]['source_event_reference_admitted']:
            row['admitted_rgb_events']=list(dict.fromkeys(row['admitted_rgb_events']+list(row['reference_events'])))
            row['rgb_reference_status']='target_reference_admitted'
        if cid=='T11_C02':
            # Source state truth is preserved. Re-reading the immutable RGB
            # sheet shows the final driver is out of view, so earlier falling
            # cannot certify the registered terminal world-z measurement.
            row['admitted_rgb_events']=[]
            row['rgb_reference_status']='terminal_target_unobservable_in_rgb'
            row['terminal_rgb_reaudit']=dict(
                evidence='benchmarks/critical_supplement_v1_20261101/evidence/T11_S02_visual.png',
                evidence_sha256=sha(SUPPLEMENT/'evidence/T11_S02_visual.png'),
                reviewer='assistant_visual_review_not_independent_human_gold',
                condition_frame=4,terminal_frame=154,terminal_target_visible=False,
                native_state_label_preserved=True,video_quality_acceptance_unchanged=True,
                no_earlier_fall_to_terminal_label_substitution=True)
        row['rgb_pending_reason']=(None if row['rgb_reference_status']=='target_reference_admitted'else
            '新参考的橡皮在末帧154已出画；先前下落不直接证明原末态Z阈值。原状态真值和视频质量验收保留。'if cid=='T11_C02'else
            obs[cid].get('reference_pending_reason'))
        if cid=='T10_C05'and cid in legacy_recovered and not legacy_recovered[cid]['source_event_reference_admitted']:
            row['rgb_pending_reason']='冻结文本与执行状态均为位置0.2171429米、初速3米/秒、倾角38度；同名cam01配置已换成另一版。物理参数已恢复，原机位完整轨迹对应仍待核验。冻结输入、标签保留。'
        contexts=[]
        if row['boundary_records']:contexts.append(row)
        axes=row.get('conditional_axes',{})
        for name,axis in axes.items():
            # Auxiliary axes stay available in evidence, but do not silently
            # complete a different original intervention.
            if name==row['parameter']or name=='original_G_global_path'or (cid=='T20_C01'and name=='book_drive_speed_mps'):
                contexts.append(dict(axis,parameter=name,fixed_context_sha256=row.get('fixed_context_sha256')))
        units=[]
        for context in contexts:
            for event in dict.fromkeys(b['event']for b in context['boundary_records']):
                candidates=[b for b in context['boundary_records']if b['event']==event]
                usable=[b for b in candidates if b.get('endpoint_repeatability',{}).get('status','reproduced')=='reproduced']
                if not usable:continue
                intervals=[list(b)for b in dict.fromkeys(tuple(b['bracket'])for b in usable)]
                # Distance to the closest observed registered boundary, while
                # preserving the entire union and its local-only scope.
                ds=[interval_distance(context['theta'],b,context['normalization_span'])for b in intervals]
                low=min(d['normalized_absolute_interval'][0]for d in ds);high=min(d['normalized_absolute_interval'][1]for d in ds)
                bucket='near'if high<=.05 else'mid'if low>.05 and high<=.15 else'far'if low>.15 else None
                explicit=[a for a in own_admissions if a['target_event']==event and a['reference_label']==row['reference_events'][event]]
                admitted=cid in swap and event in row['admitted_rgb_events']
                if explicit:
                    for a in explicit:
                        evidence_ok=a.get('distance_admitted',bool(a.get('boundary_interval')))
                        same_boundary=a.get('boundary_interval')in intervals
                        if evidence_ok and same_boundary:admitted=True
                        if cid in t02:
                            # The original RGB event/window is admitted. New
                            # endpoints were re-read at that same exact window.
                            admitted=True
                        if cid=='T16_C04'and t16 and event=='folder_downstream_contact':admitted=True
                        if cid in t07 and t07[cid]['intervals']and event=='motion_ge_1cm':admitted=True
                        if cid in t07_gpu and event=='motion_ge_1cm':admitted=True
                        if cid in t14 and event=='passed_channel':admitted=True
                        if cid in t03 and event=='book_contacts_upper_can':admitted=True
                        if cid=='T14_C03'and event=='passed_channel':admitted=True
                        if cid in t15 and t15[cid]['intervals']and event==t15[cid]['event']:admitted=True
                        if cid in t15_gpu and event=='laptop_reaches_original_fall_criterion':admitted=True
                        if cid=='T06_C04'and event=='complete_required_contact_chain':admitted=True
                        if cid in t20_speed and t20_speed[cid]['intervals']and event=='complete_propagation_original':admitted=True
                        if cid in t20_canonical and event=='complete_propagation_original':admitted=True
                if cid in legacy_recovered and legacy_recovered[cid]['source_event_reference_admitted']and legacy_recovered[cid]['intervals']:
                    if event in row['admitted_rgb_events']:admitted=True
                if row.get('original_GPU_terminal_event_closure')and event=='upper_nonpulled_book_on_table_at_end'and event in row['admitted_rgb_events']:
                    admitted=True
                if cid in t08_refined and event=='t08_target_mug_below_table_8cm'and event in row['admitted_rgb_events']:
                    admitted=True
                if cid=='T03_C01'and row.get('native_contact_diagnostic_disposition')and event=='phone_second_fall_original'and event in row['admitted_rgb_events']:
                    admitted=True
                if cid=='T09_C01'and row.get('original_GPU_T09_terminal_event_closure')and event in row['admitted_rgb_events']:
                    admitted=True
                identity=[cid,context['parameter'],event,intervals,row['horizon_s']]
                if row.get('numerical_reference_profile'):identity.append(dict(profile=row['numerical_reference_profile']['id'],source_state_sha256=row['source_state_sha256']))
                units.append(dict(reference_id=hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
                    clip_id=cid,axis=context['parameter'],theta=context['theta'],event=event,label=row['reference_events'][event],
                    intervals=intervals,normalization_span=context['normalization_span'],
                    normalized_absolute_interval=[low,high],bin=bucket,
                    numerical_evidence_status='bound_local_intervals',rgb_distance_admitted=admitted,
                    supplemental_axis=context.get('binding_kind')=='verified_supplemental_conditional_local_search',
                    rgb_blockers=[]if admitted else['event_axis_window_distance_admission_pending'],
                    exact_or_unique_physical_root_claimed=False))
        if not units and row.get('pending_primary_event'):
            event=row['pending_primary_event']
            units.append(dict(reference_id=hashlib.sha256(json.dumps([cid,row['parameter'],event,[],row['horizon_s']]).encode()).hexdigest(),
                clip_id=cid,axis=row['parameter'],theta=row['theta'],event=event,label=row['reference_events'][event],
                intervals=[],normalization_span=row['normalization_span'],normalized_absolute_interval=None,bin=None,
                numerical_evidence_status='matching_reference_version_boundary_missing',rgb_distance_admitted=False,
                supplemental_axis=False,rgb_blockers=['matching_reference_version_boundary_missing','reference_event_admission_pending'],
                exact_or_unique_physical_root_claimed=False))
        row['critical_units']=units;row['numerical_boundary_complete']=any(u['intervals']for u in units)
        if row.get('numerical_source_matches_reference_state_digest')is False and not row.get('author_approved_numerical_refinement'):
            assert not any(u['rgb_distance_admitted']for u in units),(cid,'unresolved reference/numerical state mismatch')
            row['distance_admission_pending_reason']='冻结参考为修复版，已有数值使用原发布状态；两版求解设置不同，不能按同ID直接迁移距离，需按冻结视频实际配置恢复对应边界。'
        row['original_family_boundary_complete']=any(not u['supplemental_axis']and u['intervals']for u in units)
        row['full_EventExact_automatically_admitted']=False
        definition_contract=t19_contracts[cid]if cid.startswith('T19')else contracts[cid]
        definitions={}
        for event in row['reference_events']:
            definition=copy.deepcopy(definition_contract['events'].get(event,{}))
            if event=='upper_nonpulled_book_ever_contacts_table':
                definition=dict(definition='At least one original upper non-extracted book physically contacts the tabletop at any time in the observation window. This is not a center-sinking threshold or a window-end-only contact.',
                    time_semantics='ever',definition_origin='registered_original_native_contact_event')
            elif event=='registered_two_contact_conjunction_and_order':
                definition=dict(definition='Both original driver-book to falling-book and falling-book to drink-box contacts occur, with the first driver/book contact strictly earlier than the first book/drink contact. Simultaneous or unresolvable ordering is not positive evidence.',
                    time_semantics='ordered_first_contacts',definition_origin='scripts/collect_t13_contact_boundaries.py')
            if cid in swap:
                point=new[swap[cid]]
                if cid.startswith('T04'):
                    definition=dict(definition='The original t04v3_chain_can_2 contacts the original t04v3_chain_mug, AND the mug maximum rotation from the condition pose reaches 18 degrees OR its maximum 3D center displacement from that pose reaches 0.040 m. The parentheses are: contact AND (rotation OR displacement).',
                        time_semantics='ever_with_maximum_excursion',actors=['t04v3_chain_can_2','t04v3_chain_mug'])
                elif cid.startswith('T05'):
                    threshold=point['measurements']['full_passage_threshold_x_m']
                    definition=dict(definition=f'The original phone center world x reaches or exceeds {threshold!r} m at least once within the observation window. This is the source full-passage center-plane criterion; arrival at the entrance or leading-edge passage is insufficient.',
                        time_semantics='ever',actors=['t05v2_moving_phone'])
                elif cid.startswith('T10'):
                    threshold=point['measurements']['threshold_m']
                    definition=dict(definition=f'The original support pen maximum 3D center displacement from the condition pose reaches or exceeds {threshold!r} m. This is maximum excursion, not final displacement or folder support loss.',
                        time_semantics='maximum_excursion',actors=['t10_support_pen'])
                definition['definition_origin']='bound replacement source state and scripts/build_critical_supplement.py'
            assert definition.get('definition'),(cid,event,'missing original definition')
            definition['minimum_evidence_times']=max(1,definition.get('minimum_evidence_times',1))
            definitions[event]=definition
        row['judge_protocol']=dict(target=definition_contract.get('target_en')or definition_contract.get('target')or
            'Track the original named actors by appearance and temporal continuity; do not substitute new objects.',
            events=definitions,
            uncertainty_policy='Do not infer nonoccurrence from occlusion, leaving view or a truncated window. Physical units require calibration; unknown labels go to review. No reference outcomes are supplied to the judge.')
        cases.append(row)
    assert len(cases)==100
    summary=dict(registered_cases=100,numerical_boundary_cases=sum(r['numerical_boundary_complete']for r in cases),
        numerical_boundary_pending=[r['clip_id']for r in cases if not r['numerical_boundary_complete']],
        original_family_boundary_cases=sum(r['original_family_boundary_complete']for r in cases),
        original_family_pending=[r['clip_id']for r in cases if not r['original_family_boundary_complete']],
        numerical_reference_state_digest_mismatch=[r['clip_id']for r in cases if r.get('numerical_source_matches_reference_state_digest')is False],
        unresolved_numerical_reference_state_digest_mismatch=[r['clip_id']for r in cases if r.get('numerical_source_matches_reference_state_digest')is False and not r.get('author_approved_numerical_refinement')],
        author_approved_refined_profile_cases=[r['clip_id']for r in cases if r.get('author_approved_numerical_refinement')],
        reference_rgb_target_admitted=sum(r['rgb_reference_status']=='target_reference_admitted'for r in cases),
        reference_rgb_target_pending=[r['clip_id']for r in cases if r['rgb_reference_status']!='target_reference_admitted'],
        critical_rgb_distance_cases=sum(any(u['rgb_distance_admitted']for u in r['critical_units'])for r in cases),
        critical_rgb_distance_pending=[r['clip_id']for r in cases if not any(u['rgb_distance_admitted']for u in r['critical_units'])],
        numerical_records_include_unadmitted_candidates=True,
        numerical_near_cases=sum(any(u['bin']=='near'for u in r['critical_units'])for r in cases),
        admitted_near_cases=sum(any(u['bin']=='near'and u['rgb_distance_admitted']for u in r['critical_units'])for r in cases),
        generated_model_scores_created=False,new_parameter_searches_started=int((WORK/'T16_GPU_ENDPOINT_DISPATCH.json').exists())+3*int((WORK/'T07_GPU_ENDPOINTS_DISPATCH.json').exists())+3*int((WORK/'T15_GPU_DISPATCH.json').exists())+3*int((WORK/'T08_GPU_ENDPOINTS_DISPATCH.json').exists())+2*int((WORK/'T20_CANONICAL_GPU_ENDPOINTS_DISPATCH.json').exists())+len(t18_dispatched_cases)+int((WORK/'T03_ORIGINAL_GPU_ENDPOINTS_DISPATCH.json').exists()),
        source_replays_started=int((WORK/'T16_GPU_SOURCE_DISPATCH.json').exists())+3*int((WORK/'T07_GPU_SOURCE_DISPATCH.json').exists())+3*int((WORK/'T15_GPU_DISPATCH.json').exists())+3*int((WORK/'T08_GPU_SOURCE_DISPATCH.json').exists())+2*int((WORK/'T20_CANONICAL_GPU_SOURCE_DISPATCH.json').exists())+3*int((WORK/'T18_GPU_SOURCE_DISPATCH.json').exists())+2*int((WORK/'T18_GPU_OVERLAP_SOURCE_DISPATCH.json').exists())+int((WORK/'T03_ORIGINAL_GPU_SOURCE_DISPATCH.json').exists()),
        metadata_reconstructed_source_seed_probes_completed=len(read(WORK/'t10_metadata_source_comparison.json'))if(WORK/'t10_metadata_source_comparison.json').exists()else 0,
        metadata_reconstructed_parameter_searches_started=int((WORK/'T10_VALID_SUPPORT_DISPATCH.json').exists()))
    result=dict(schema='core100-critical-protocol-registry-v2',version=OUT.name,
        roster_release=manifest['version'],summary=summary,cases=cases,
        policy=dict(near_upper=.05,mid_upper=.15,full_EventExact='separate original complete-chain protocol',
            failed_generated_outputs_stay_in_registered_denominator=True,
            reference_admission_is_not_generated_quality_screening=True,
            quality_event_and_inversion_coverage_reported_separately=True),
        source_hashes={str(p.relative_to(ROOT)):sha(p)for p in [roster/'MANIFEST.json',SUPPLEMENT/'MANIFEST.json',cohort_path,obs_path,contract_path,t19_contract_path,t02_file,t20_file,
            ROOT/'scripts/build_critical_supplement.py',ROOT/'scripts/collect_t13_contact_boundaries.py',t07_file,t14_file,width_file,t03_file,t15_file,t06_file,t20_speed_file,native_readback_path]+t16_sources+t07_gpu_files+t15_gpu_files+t18_sources+t08_attempt_files+t08_refined_files+t20_canonical_files+pending_audit_files+t18_gpu_attempt_files+legacy_recovered_files+t10_old_version_files+t03_original_files+t10_reconstruction_files+legacy_exact_files})
    from physedit.core100_critical import primary
    result['summary']['primary_rgb_event_cases']=sum(primary(r)['event']in r['admitted_rgb_events']for r in cases)
    result['summary']['primary_rgb_event_pending']=[r['clip_id']for r in cases if primary(r)['event']not in r['admitted_rgb_events']]
    return result

def main():
    result=build();OUT.mkdir(exist_ok=True)
    # Admission tables can be extended by another authorized task. Pin the
    # exact bytes used here so later extensions do not invalidate this release.
    pinned={}
    for name,digest in result['source_hashes'].items():
        raw=(ROOT/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
        target=OUT/'sources'/(digest+'.json');target.parent.mkdir(exist_ok=True)
        if target.exists():assert target.read_bytes()==raw
        else:target.write_bytes(raw)
        pinned[target.relative_to(ROOT).as_posix()]=digest
    result['original_source_paths']=result['source_hashes'];result['source_hashes']=pinned
    roster,_,conditions,_=load_roster()
    legacy=read(ROOT/'catalog/active_core100_conditions.json')
    legacy_root=(ROOT/'catalog'/legacy['release_root']).resolve()
    t19={r['clip_id']:r for r in read(legacy_root/'MANIFEST.json')['replacements']}
    image_bindings={r['clip_id']:r for r in map(json.loads,(ROOT.parent/'prompts_72000_unified/core100_generation_input_bindings.jsonl').read_text(encoding='utf8').splitlines())}
    inputs=[]
    for task in conditions:
        cid=task['clip_id']
        if task.get('supplement_point_id'):
            source=ROOT/task['condition_image'];expected=task['condition_sha256'];condition_frame=task['condition_frame_index']
        elif cid in t19:
            source=legacy_root/t19[cid]['condition_image'];expected=t19[cid]['condition_sha256'];condition_frame=0
        else:
            source=ROOT/'review/prompt_length_ab_20261030/conditions'/(cid+'.png')
            expected=image_bindings[cid]['condition_image_sha256'];condition_frame=image_bindings[cid]['declared_condition_frame_index']
        assert sha(source)==expected
        dest=OUT/'conditions'/(cid+'_'+expected[:12]+'.png');dest.parent.mkdir(exist_ok=True)
        if dest.exists():assert sha(dest)==expected
        else:shutil.copyfile(source,dest)
        from PIL import Image
        with Image.open(dest)as image:width,height=image.size;image.verify()
        ref=next(r for r in result['cases']if r['clip_id']==cid)
        assert condition_frame==ref['condition_frame_index']
        inputs.append(dict(clip_id=cid,sample_id=task['sample_id'],
            prompt_variants_en=task['prompt_variants_en'],prompt_variant_sha256=task['prompt_variant_sha256'],
            reference_video_sha256=ref['reference_video_sha256'],condition_image=dest.relative_to(ROOT).as_posix(),
            condition_sha256=expected,condition_frame_index=condition_frame,source_width=width,source_height=height,
            evaluation_duration_s=ref['horizon_s']))
    result['input_bindings']=inputs
    # Source-defined pairs only. Historic shared-seed pairs and the four new
    # independent pairs remain distinct; no arbitrary same-scene pairing.
    valid={r['clip_id']for r in result['cases']};pairs=[]
    for c in read(ROOT/'annotation_site/resources/core100_formal_cohorts.json')['cohorts']:
        for pair in c.get('pairs',[]):
            ids=pair.get('clips',[])
            if len(ids)==2 and set(ids)<=valid:
                pairs.append(dict(pair_id=pair['pair_id'],clips=ids,pairing_mode='coupled_seed',source='previous_explicit_cohort'))
    mapping=read(roster/'replacement_map.json');to_clip={r['supplement_point_id']:r['clip_id']for r in mapping}
    for pair in read(SUPPLEMENT/'answers.json')['pairs']:
        pairs.append(dict(pair_id=pair['pair_id'],clips=[to_clip[p]for p in pair['points']],pairing_mode='independent',source='author_replacement'))
    result['pairs']=pairs
    # The original T07 cf-A endpoints already in the roster have the same
    # physical context and identical condition image. Register that actual
    # source pair; do not manufacture a pair from arbitrary scene labels.
    case_by_id={r['clip_id']:r for r in result['cases']}
    image_by_id={r['clip_id']:r for r in result['input_bindings']}
    a,b=[case_by_id[c]for c in ['T07_C04','T07_C05']]
    if a['binding_kind']==b['binding_kind']=='original_published_friction_recovery':
        assert a['fixed_context_sha256']==b['fixed_context_sha256']
        assert image_by_id[a['clip_id']]['condition_sha256']==image_by_id[b['clip_id']]['condition_sha256']
        assert a['reference_events']['motion_ge_1cm']!=b['reference_events']['motion_ge_1cm']
        pairs.append(dict(pair_id='T07_original_cf_A_friction',clips=[a['clip_id'],b['clip_id']],
            pairing_mode='coupled_seed',source='recovered_original_published_cf_A_pair',
            fixed_context_sha256=a['fixed_context_sha256'],condition_sha256=image_by_id[a['clip_id']]['condition_sha256']))
    a,b=[case_by_id[c]for c in ['T14_C04','T14_C05']]
    assert a['fixed_context_sha256']==b['fixed_context_sha256']
    assert a['reference_events']['passed_channel']!=b['reference_events']['passed_channel']
    pairs.append(dict(pair_id='T14_original_cf_A_gap',clips=[a['clip_id'],b['clip_id']],pairing_mode='coupled_seed',
        source='recovered_original_released_A_bracket',fixed_context_sha256=a['fixed_context_sha256']))
    a,b=[case_by_id[c]for c in ['T03_C04','T03_C05']]
    assert a['fixed_context_sha256']==b['fixed_context_sha256']
    pairs.append(dict(pair_id='T03_original_cf_A_book_contact',clips=[a['clip_id'],b['clip_id']],pairing_mode='coupled_seed',
        source='recovered_original_released_speed_and_equivalent_impulse_contrast',fixed_context_sha256=a['fixed_context_sha256'],
        condition_images_byte_identical=image_by_id[a['clip_id']]['condition_sha256']==image_by_id[b['clip_id']]['condition_sha256']))
    a,b=[case_by_id[c]for c in ['T15_C04','T15_C05']]
    assert a['fixed_context_sha256']==b['fixed_context_sha256']and a['binding_kind']==b['binding_kind']=='original_V11_published_transition_recovery'
    pairs.append(dict(pair_id='T15_original_cf_B_laptop_phone_contact',clips=[a['clip_id'],b['clip_id']],pairing_mode='coupled_seed',
        source='original_V11_coupled_book_laptop_edge_margin_contrast',fixed_context_sha256=a['fixed_context_sha256']))
    from physedit.core100_critical import primary
    result['summary']['registered_pairs']=len(pairs)
    for mode in ['independent','coupled_seed']:
        own=[p for p in pairs if p['pairing_mode']==mode]
        result['summary'][mode+'_registered_pairs']=len(own)
        result['summary'][mode+'_admitted_pairs']=sum(all(primary(case_by_id[c])['rgb_distance_admitted']for c in p['clips'])for p in own)
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=OUT/('registry_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    pointer=dict(version=result['version'],roster_release=result['roster_release'],
        registry='../'+path.relative_to(ROOT).as_posix(),registry_sha256=digest,
        scope='new Core100 critical pipeline; previous live inputs and scores unchanged')
    (ROOT/'catalog/active_core100_critical_protocol.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    lines=['# Core100新版临界接入状态','',
        '本表由当前哈希登记生成；数值区间不等于模型成绩或参考画面准入。','',
        str(result['summary']['numerical_boundary_cases'])+'条有数值登记，其中包含原设置、上下文或事件凭据尚未核准的候选；另'+str(100-result['summary']['numerical_boundary_cases'])+'条尚缺匹配版本的区间，不能视为100条已经完成。正式RGB距离评分准入'+str(result['summary']['critical_rgb_distance_cases'])+'条，剩余'+str(100-result['summary']['critical_rgb_distance_cases'])+'条待闭合；正式Near参考'+str(result['summary']['admitted_near_cases'])+'条。','',
        '| 场景 | 案例 | 原族数值区间 | RGB距离准入 | 正式Near |',
        '|---|---:|---:|---:|---:|']
    for scene in [f'T{i:02}'for i in range(1,21)]:
        own=[r for r in result['cases']if r['scene_id']==scene]
        lines.append('|'+scene+'|'+str(len(own))+'|'+str(sum(r['original_family_boundary_complete']for r in own))+'|'+
            str(sum(any(u['rgb_distance_admitted']for u in r['critical_units'])for r in own))+'|'+
            str(sum(any(u['rgb_distance_admitted']and u['bin']=='near'for u in r['critical_units'])for r in own))+'|')
    lines+=['','## 逐条状态','','| 案例 | 原参数族 | 源参数 | 观察窗(s) | 区间 | RGB距离 | 说明 |','|---|---|---|---:|---|---|---|']
    csv_rows=[]
    for r in result['cases']:
        units=[u for u in r['critical_units']if not u['supplemental_axis']]
        admitted=any(u['rgb_distance_admitted']for u in units)
        note=r.get('rgb_pending_reason')or r.get('distance_admission_pending_reason')or('事件/参数轴/窗口的数值凭据对应待补齐；不是缺少临界区间。'if not admitted else'已接入固定参考的局部区间。')
        row=dict(clip_id=r['clip_id'],parameter=r['parameter'],theta=r['theta'],horizon_s=r['horizon_s'],
            intervals=[dict(axis=u['axis'],event=u['event'],intervals=u['intervals'],distance=u['normalized_absolute_interval'],bin=u['bin'])for u in units],
            rgb_distance_admitted=admitted,note=note,reference_video_sha256=r['reference_video_sha256'])
        csv_rows.append(row)
        lines.append('|'+r['clip_id']+'|'+str(r['parameter'])+'|'+str(r['theta'])+'|'+str(round(r['horizon_s'],6))+'|'+
            '; '.join(u['event']+': '+str(u['intervals'])for u in units)+'|'+('已接入'if admitted else'未准入')+'|'+note+'|')
    (OUT/'STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    with (OUT/'case_status.csv').open('w',encoding='utf-8-sig',newline='')as handle:
        writer=csv.DictWriter(handle,fieldnames=list(csv_rows[0]));writer.writeheader();writer.writerows(csv_rows)
    print(json.dumps(result['summary'],ensure_ascii=False))

if __name__=='__main__':main()
