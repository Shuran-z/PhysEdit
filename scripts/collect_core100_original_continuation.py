"""Recover completed original-physics probes without changing frozen inputs.

An interval can be sealed from completed opposite-label endpoints while optional
refinement continues. Its full width is retained; this is not a completed curve,
an exact threshold, a model score, or approval of video quality.
"""
import argparse
import copy
import datetime
import hashlib
import inspect
import json
from pathlib import Path
import subprocess

from scripts.boundary_ssh import remote_text
from physedit.core100_bindings import interval_distance, load

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_continue_20261031'
REMOTE = r'''
import gzip,hashlib,json,math,pathlib
roots=ROOTS
registered_windows=WINDOWS
targets=TARGETS
PREFILTER_FUNCTION
out=[]
for root in roots:
 root=pathlib.Path(root)
 # Output-only storage migrations retain public paths through first-level
 # symlinks. pathlib.rglob does not descend into those directories.
 for jobs in sorted(set(root.rglob('jobs.json')) | set(root.glob('*/jobs.json'))):
  base=jobs.parent
  for job in json.loads(jobs.read_text()):
   if job.get('validation_only'):continue
   if targets is not None and job['clip_id'] not in targets:continue
   case=base/job['clip_id'];audit=case/'profile_0/source_audit.json'
   if not audit.exists():continue
   deployment=json.loads((base/'deployment.json').read_text())
   for name,digest in deployment.get('sources',{}).items():
    assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
   row=dict(root=str(base),job=job,audit=json.loads(audit.read_text()),probes=[],
     deployment=deployment,worker_sha256=hashlib.sha256((base/'worker.py').read_bytes()).hexdigest())
   status=case/'status.json';result=case/'result.json'
   row['status']=json.loads(status.read_text())if status.exists()else None
   row['result']=json.loads(result.read_text())if result.exists()else None
   window=registered_windows[job['clip_id']]
   prefix=(job['clip_id'].startswith('T05')and window['end_frame_index']!=job['end_frame_index'])
   receipt_files=list((case/'profile_0').glob('*/receipt.json'))
   summaries=[dict(json.loads(p.read_text()),source_repeat=p.parent.name=='source_repeat') for p in receipt_files]
   if targets is not None and not has_opposite_receipt_labels(summaries,window['reference_events'],shorter_gate_window=prefix):
    row.update(preliminary_no_opposite_endpoints=True,unverified_receipt_count=len(summaries))
    out.append(row);continue
   for receipt in receipt_files:
    data=json.loads(receipt.read_text());p=pathlib.Path(data['state_path'])
    raw=gzip.decompress(p.read_bytes());config=p.parent/'config.json'
    assert hashlib.sha256(raw).hexdigest()==data['state_sha256'],str(p)
    assert hashlib.sha256(config.read_bytes()).hexdigest()==data['config_sha256'],str(config)
    state=json.loads(raw);c=json.loads(config.read_text());source=job['base_config']
    assert len(state['frames'])==210
    assert all(math.isfinite(x)for f in state['frames']for o in f['objects']for x in o['position'])
    # Rendering/annotation destinations may change; solver and simulation clock may not.
    for key,value in source['scene_overrides'].items():
     if key not in ('record_contacts','raytracing'):assert c['scene_overrides'].get(key)==value,(str(config),key)
    for key in ('seed','random_seed'):assert c.get(key)==source.get(key),(str(config),key)
    assert c['render']['physics_steps_per_render_frame']==source['render']['physics_steps_per_render_frame']
    assert abs(c['scene_overrides']['dt']*c['render']['physics_steps_per_render_frame']-job['physical_frame_period_s'])<1e-12
    data.update(receipt_path=str(receipt),source_repeat=receipt.parent.name=='source_repeat',
      state_and_config_hashes_verified=True,original_solver_and_clock_verified=True)
    if job['family']=='support_x' and job['clip_id'].startswith('T10'):
     actual=c['experiment']['t10_design']['support_x_m']
     pen=next(o for o in c['dynamic_objects']if o['name']=='t10_support_pen')
     assert abs(pen['pose']['position'][0]-actual)<1e-9
     data['effective_parameter_value']=actual
    if job['family']=='case_friction_coefficient' and job['clip_id'].startswith('T11'):
     from copy import deepcopy
     restored=deepcopy(c['dynamic_objects']);expected=source['dynamic_objects']
     case=next(o for o in restored if o['name']=='t11_eyeglasses_case')
     original=next(o for o in expected if o['name']=='t11_eyeglasses_case')
     assert abs(case['friction']-data['theta'])<1e-9
     case['friction']=original['friction']
     if isinstance(case.get('material_preset'),dict):
      assert abs(case['material_preset']['friction']-data['theta'])<1e-9
      case['material_preset']['friction']=original['material_preset']['friction']
     assert restored==expected and c['runtime_forces']==source['runtime_forces']
     data['original_component_only_and_forces_unchanged_verified']=True
     actual=state.get('physics_debug',{}).get('effective_entity_properties',{}).get('t11_eyeglasses_case',{}).get('effective_geom_friction_coefficients',[])
     data['friction_execution_readback']={'t11_eyeglasses_case':actual}
     data['intervention_applied_as_declared']=bool(actual)and all(abs(value-data['theta'])<1e-6 for value in actual)
    if job['family']=='phone_tray_friction_coefficient':
     properties=state.get('physics_debug',{}).get('effective_entity_properties',{})
     actual={name:properties.get(name,{}).get('effective_geom_friction_coefficients',[])for name in ['t05v2_moving_phone','t05v2_pbr_wood_sorting_tray']}
     data['friction_execution_readback']=actual
     data['intervention_applied_as_declared']=all(values and all(abs(value-data['theta'])<1e-6 for value in values)for values in actual.values())
    if prefix:
     end=window['end_frame_index'];assert abs((end-4)*job['physical_frame_period_s']-window['horizon_s'])<1e-9
     assert end<=job['end_frame_index']
     data['full_source_window_labels']=data['labels']
     data['labels']={'gate_passage':int(max(o['position'][0]for f in state['frames'][5:end+1]for o in f['objects']if o['name']=='t05v2_moving_phone')>=job['full_pass_x_m'])}
    row['probes'].append(data)
   if prefix:
    row['original_full_window_job']=dict(job)
    row['job']=dict(job,**window,expected_labels=window['reference_events'])
    source=next(p for p in row['probes']if p['theta']==job['theta']and not p['source_repeat'])
    repeat=next(p for p in row['probes']if p['source_repeat'])
    row['original_full_window_audit']=row['audit']
    row['audit']=dict(row['audit'],source_labels=source['labels'],repeated_labels=repeat['labels'],published_expected_labels=window['reference_events'],source_event_match=source['labels']==window['reference_events'])
    # Full-window intervals must not be reused for a shorter observation window.
    row['original_full_window_result']=row['result'];row['result']=None
    row['window_readback']='Same completed states, original registered prefix; frozen inputs and old labels unchanged.'
   out.append(row)
print(json.dumps(out))
'''


def has_opposite_receipt_labels(probes, events, *, shorter_gate_window=False):
    """Prefilter only: raw labels can defer verification, never admit a boundary."""
    ordinary = [p for p in probes if not p.get('source_repeat')]
    # T05 passage means ever crossing an x-coordinate. All-zero full-window
    # labels imply zero on a prefix, but all-one labels may hide prefix flips.
    if shorter_gate_window and any(p.get('labels',{}).get('gate_passage') != 0 for p in ordinary):
        return True
    for event in events:
        values = [p.get('labels', {}).get(event) for p in ordinary]
        if any(type(v) is not int or v not in (0, 1) for v in values):
            return True  # Unknown or inconsistent metadata must take the full path.
        if len(set(values)) > 1:
            return True
    return False


def candidate_update(old, evidence, evidence_file, *, allow_completed_probes=False):
    """Return a scalar, source-matched update, or None; no-flip stays unresolved."""
    job, audit = evidence['job'], evidence['audit']
    for key in ('clip_id', 'sample_id', 'reference_video_sha256'):
        if job.get(key) != old[key]:
            raise ValueError('continuation_identity_mismatch:' + key)
    if isinstance(old['theta'], dict):
        if not old['clip_id'].startswith('T11'):
            return None
        if job['family']=='original_G_global_path':
            return original_joint_path_update(old,evidence,evidence_file,
                allow_completed_probes=allow_completed_probes)
        return joint_axis_update(old, evidence, evidence_file,
                                 allow_completed_probes=allow_completed_probes)
    if old.get('conditional_axes'):
        # A recovered primary direction joins the existing explicit directions;
        # it must not silently replace them or disappear because the case is ready.
        scalar=copy.deepcopy(old);scalar.pop('conditional_axes')
        update=candidate_update(scalar,evidence,evidence_file,allow_completed_probes=allow_completed_probes)
        if update is None:return None
        result=copy.deepcopy(old);axis=job['family']
        selected={k:copy.deepcopy(update[k])for k in ['parameter','theta','normalization_domain',
            'normalization_span','reference_events','boundary_records','binding_kind','source_diagnostics',
            'conditional_solver_evidence','evidence']}
        selected['formal_admission']=False
        result['conditional_axes'][axis]=selected
        result['source_point_axes'][axis]=old['theta']
        result.setdefault('evidence',[]).append(dict(file=evidence_file,detail=evidence['root']))
        return result
    if (job['theta'] != old['theta'] or job['domain'] != old['normalization_domain'] or
            abs(job['horizon_s'] - old['horizon_s']) > 1e-9 or
            job['end_frame_index'] != old['end_frame_index']):
        raise ValueError('continuation_parameter_or_window_mismatch')
    axis = job['family']
    if old['clip_id'].startswith('T03') and axis == 'C':
        axis = 'lower_phone_com_edge_distance_m'
    if old['clip_id'].startswith('T04') and axis == 'support_release':
        axis = 'commanded_support_extraction_speed_mps'
    if axis != old['parameter']:
        raise ValueError('continuation_family_mismatch')
    if (any(audit['source_labels'].get(k) != v for k,v in old['reference_events'].items()) or
            audit['repeated_labels'] != audit['source_labels'] or
            audit['source_event_match'] is not True):
        raise ValueError('continuation_source_event_mismatch')
    completed = evidence.get('result')
    if not completed and not allow_completed_probes:
        return None
    probes = [p for p in evidence['probes'] if not p['source_repeat'] and p.get('intervention_applied_as_declared',True)]
    if not all(p['state_and_config_hashes_verified'] and p['original_solver_and_clock_verified'] for p in probes):
        raise ValueError('continuation_unverified_probe')
    if not any(p['theta'] == job['theta'] and p['labels'] == audit['source_labels'] for p in probes):
        raise ValueError('continuation_source_receipt_missing')
    repeats = [p for p in evidence['probes'] if p['source_repeat'] and p.get('intervention_applied_as_declared',True)]
    if len(repeats) != 1 or repeats[0]['labels'] != audit['source_labels']:
        raise ValueError('continuation_repeat_receipt_missing')
    by_theta = {p['theta']:p for p in probes}
    if completed:
        intervals = [r for r in completed['intervals'] if r['event'] in old['reference_events']]
    else:
        ordered = sorted(probes, key=lambda p:p['theta'])
        intervals = [dict(event=event, bracket=[a['theta'], b['theta']],
                          labels=[a['labels'][event], b['labels'][event]])
                     for event in old['reference_events'] for a,b in zip(ordered, ordered[1:])
                     if a['labels'][event] != b['labels'][event]]
    records = []
    for interval in intervals:
        event = interval['event']; requested_bracket = interval['bracket']
        endpoints=[]
        for value in requested_bracket:
            if value in by_theta:endpoints.append(by_theta[value]);continue
            # Workers reuse files named with format(theta,'.12g'). Preserve
            # the executed receipt's value rather than dropping a valid cache
            # endpoint because the requested float differs in its last bit.
            matches=[p for theta,p in by_theta.items()if format(theta,'.12g')==format(value,'.12g')]
            if len(matches)>1:raise ValueError('ambiguous_cached_parameter_endpoint')
            if matches:endpoints.append(matches[0])
        if len(endpoints)!=2:continue
        # T10's released recipe quantizes positions to four decimals. The
        # command may contain extra digits; distances use executed geometry.
        bracket=[p.get('effective_parameter_value',p['theta'])for p in endpoints]
        if bracket[0]>=bracket[1]:
            raise ValueError('continuation_effective_parameter_endpoints_do_not_separate')
        labels = [p['labels'][event] for p in endpoints]
        if event not in old['reference_events'] or labels not in ([0,1], [1,0]) or labels != interval['labels']:
            raise ValueError('continuation_endpoints_do_not_flip')
        records.append(dict(event=event, bracket=bracket, endpoint_labels=labels,
            requested_search_bracket=requested_bracket,
            distance=interval_distance(old['theta'], bracket, old['normalization_span']),
            interval_kind='conditional_local_search', exact_theta_star=None, endpoints=endpoints))
    if not records:
        return None
    result = copy.deepcopy(old)
    result.update(status='distance_ready', boundary_records=records,
        reason='Completed original-axis opposite-label endpoints bound as local intervals; full bracket uncertainty retained. Optional curve/refinement is separate.',
        binding_kind='original_physics_completed_probe_local_intervals',
        evidence=[dict(file=evidence_file, detail=evidence['root'])],
        source_truth_origin='recomputed_from_pinned_original_config',
        conditional_solver_evidence=dict(backend='gpu32', original_solver_and_clock_verified=True,
            full_scan_completed=bool(completed), optional_refinement_pending=not bool(completed)),
        source_diagnostics=dict(maximum_native_overlap_m=max(p['native_peak_m'] for p in probes),
            source_repeat_max_position_error_m=audit['max_position_error_m'],
            excluded_failed_intervention_probes=[dict(theta=p['theta'],readback=p.get('friction_execution_readback'))for p in evidence['probes']if p.get('intervention_applied_as_declared')is False],
            physics_quality_approval_granted=False, original_1mm_diagnostics_retained=True))
    return result


def original_joint_path_update(old,evidence,evidence_file,*,allow_completed_probes):
    """Recover the actual G_global family, keeping its full source vector."""
    job=evidence['job'];path=WORK/'t11_original_global_path_contract_20261101.json'
    raw=path.read_bytes();contract=json.loads(raw)
    info=next(r for r in contract['cases']if r['clip_id']==old['clip_id'])
    if job['base_config']['experiment']['formal_design']['design_id']!='G_global_06':
        raise ValueError('original_global_path_requires_the_frozen_G_global_06_source')
    if (contract['original_family']!='joint_global_configuration' or
            info['source_vector']!=old['theta'] or
            job['joint_source_nominal_parameters']!=old['theta'] or
            info['source_config_sha256']!=job['config_sha256'] or
            info['source_coordinate']!=job['theta'] or
            info['joint_path']!=job['original_joint_path'] or
            hashlib.sha256(raw).hexdigest()!=job['original_joint_path_contract']['sha256'] or
            not info['source_no_op_exact'] or not info['all_eight_released_controlled_physics_match']):
        raise ValueError('original_global_joint_path_source_or_contract_mismatch')
    if hashlib.sha256(contract['helper_source'].encode()).hexdigest()!=contract['helper_sha256']:
        raise ValueError('original_global_joint_path_helper_changed')
    scalar=copy.deepcopy(old);scalar.pop('conditional_axes',None)
    scalar.update(theta=job['theta'],parameter=job['family'],normalization_domain=[0.,1.],normalization_span=1.)
    update=candidate_update(scalar,evidence,evidence_file,allow_completed_probes=allow_completed_probes)
    if update is None:return None
    result=copy.deepcopy(old)
    result.setdefault('legacy_primary_axis',{k:copy.deepcopy(old.get(k))for k in
        ['parameter','theta','normalization_domain','normalization_span','boundary_records']})
    result.update(status='distance_ready',binding_kind='verified_original_global_joint_path',
        reason='The original G_global joint family is recovered on its explicit ordered path. Five inputs vary together; this is not a single-input or global-nearest boundary.',
        axis_selection_required=True)
    selected={k:copy.deepcopy(update[k])for k in ['parameter','theta','normalization_domain',
        'normalization_span','reference_events','boundary_records','binding_kind','source_diagnostics',
        'conditional_solver_evidence','evidence']}
    selected.update(unit='normalized arc length on the original G_global path',
        original_registered_family='joint_global_configuration',original_joint_path=copy.deepcopy(info['joint_path']),
        joint_source_vector=copy.deepcopy(old['theta']),single_input_causal_attribution=False,
        global_nearest_boundary_claimed=False,formal_admission=False)
    result.setdefault('conditional_axes',{})[job['family']]=selected
    result.setdefault('source_point_axes',{})[job['family']]=job['theta']
    proof=dict(file=path.relative_to(ROOT).as_posix(),detail='Released original G_global family and source-preserving mapping')
    if proof not in result.setdefault('evidence',[]):result['evidence'].append(proof)
    return result


def joint_axis_update(old, evidence, evidence_file, *, allow_completed_probes):
    """Keep T11's joint source intact and require explicit scoring-axis choice."""
    job = evidence['job']; axis = job['family']
    units = dict(driver_initial_speed_mps='nominal command m/s', relay_case_gap_m='m',
                 case_edge_margin_m='m', relay_block_mass_kg='kg')
    if axis=='case_friction_coefficient':
        proof=WORK/'t11_original_case_friction_contract_20261101.json'
        raw=proof.read_bytes();contract=json.loads(raw)
        source=next(c for c in contract['cases']if c['clip_id']==old['clip_id'])
        if (contract['component']!=axis or contract['forces_modified'] is not False or
                hashlib.sha256(contract['helper_source'].encode()).hexdigest()!=contract['helper_sha256'] or
                hashlib.sha256(raw).hexdigest()!=job['original_component_contract_sha256'] or
                source['source_vector']!=old['theta'] or source['source_config_sha256']!=job['config_sha256'] or
                not source['source_no_op_exact'] or contract['original_range']!=job['domain'] or
                any(not p.get('original_component_only_and_forces_unchanged_verified')for p in evidence['probes'])):
            raise ValueError('original_case_friction_component_evidence_mismatch')
        units[axis]='dimensionless friction coefficient'
    if (axis not in units or job.get('joint_source_nominal_parameters') != old['theta'] or
            job.get('original_family_axes_not_collapsed') is not True):
        raise ValueError('continuation_joint_source_or_original_axis_mismatch')
    scalar = copy.deepcopy(old)
    # The scalar calculation must return this axis's records. Existing axes
    # are merged back from `old` below, after the joint source is restored.
    scalar.pop('conditional_axes', None)
    scalar.update(theta=old['theta'][axis], parameter=axis,
                  normalization_domain=job['domain'], normalization_span=job['domain'][1]-job['domain'][0])
    update = candidate_update(scalar, evidence, evidence_file,
                              allow_completed_probes=allow_completed_probes)
    if update is None:
        return None
    result = copy.deepcopy(old)
    result.setdefault('legacy_primary_axis', {k:copy.deepcopy(old.get(k)) for k in
        ['parameter','theta','normalization_domain','normalization_span','boundary_records']})
    result.update(status='distance_ready', binding_kind='verified_joint_point_conditional_axes',
        reason='Completed original-family conditional intervals; select an explicit axis. Joint source inputs and existing labels are unchanged.',
        axis_selection_required=True)
    result.setdefault('source_point_axes',{}).update(copy.deepcopy(old['theta']))
    selected = {k:copy.deepcopy(update[k]) for k in ['parameter','theta','normalization_domain',
        'normalization_span','reference_events','boundary_records','binding_kind','source_diagnostics',
        'conditional_solver_evidence','evidence']}
    selected.update(unit=units[axis], formal_admission=False)
    if axis=='case_friction_coefficient':
        selected.update(original_joint_component=True,original_joint_path_recovered=False,
            normalization_source='Range of the original G_global friction component; extended probes retain this scale.',
            component_contract_sha256=job['original_component_contract_sha256'])
        selected['evidence'].append(dict(file=proof.relative_to(ROOT).as_posix()))
    result.setdefault('conditional_axes', {})[axis] = selected
    result['registered_original_axes'] = list(units)
    result['axes_without_bound_interval'] = [name for name in units if name not in result['conditional_axes']]
    result.setdefault('evidence', []).append(dict(file=evidence_file, detail=evidence['root']))
    return result


def collect(host, *, pending_original_only=False):
    roots = (['/data2/liyuhan/core100_continue_original_20261031',
              '/data2/liyuhan/core100_continue_families_20261031',
              '/data2/liyuhan/core100_continue_t09_original_20261031'] if host == 'p25' else
             ['/data/yangkaiyuan/core100_continue_original_20261031/T20_C01'])
    registry=load()
    windows = {r['clip_id']:{k:r[k] for k in ['end_frame_index','horizon_s','reference_events']}
               for r in registry['cases']}
    from physedit.core100_bindings import original_family_reference_ready
    def pending_reference(r):
        if not original_family_reference_ready(r):return True
        path=r.get('conditional_axes',{}).get('original_G_global_path')
        return bool(path and not path.get('conditional_solver_evidence',{}).get('full_scan_completed'))
    targets=[r['clip_id']for r in registry['cases']if pending_reference(r)] if pending_original_only else None
    code = (REMOTE.replace('ROOTS', repr(roots)).replace('WINDOWS', repr(windows))
            .replace('TARGETS',repr(targets)).replace('PREFILTER_FUNCTION',inspect.getsource(has_opposite_receipt_labels)))
    if host == 'p25':
        return json.loads(remote_text(host, code, timeout=180))
    process = subprocess.run(['ssh', '-i', 'C:/Users/24511/.ssh/id_ed25519_sg88n5',
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
        'yangkaiyuan@172.25.72.115', 'python3 -'], input=code.encode(), capture_output=True, timeout=180)
    process.check_returncode()
    return json.loads(process.stdout)


def recover_original_friction_scale(old):
    if old['parameter'] != 'phone_tray_friction_coefficient' or old['normalization_domain'] is not None:
        return old
    path = WORK / 'original_friction_sampling_contract.json'
    contract = json.loads(path.read_text(encoding='utf8'))
    if hashlib.sha256(contract['source_text'].encode()).hexdigest() != contract['source_sha256']:
        raise ValueError('original_friction_producer_changed')
    if '("phone_tray_friction", x) for x in (0.025, 0.049, 0.090)' not in contract['source_text']:
        raise ValueError('original_friction_design_range_not_found')
    result = copy.deepcopy(old)
    result.update(normalization_domain=[.025,.09], normalization_span=.09-.025,
        normalization_source=dict(file=path.relative_to(ROOT).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), kind='original_producer_sampling_range'))
    return result


def restore_t09_original_event(old, evidence):
    """Restore the author's contact event; retain the older end-state label."""
    if old['clip_id'] != 'T09_C01':
        return old
    path=WORK/'t09_original_family_event_contract_v2.json'
    if not path.exists():path=WORK/'t09_original_family_event_contract.json'
    contract=json.loads(path.read_text(encoding='utf8'));job=evidence['job']
    for source in contract['source_files']:
        if hashlib.sha256(source['text'].encode()).hexdigest()!=source['sha256']:
            raise ValueError('t09_original_producer_changed')
    for name in ['clip_id','sample_id','reference_video_sha256','horizon_s','end_frame_index']:
        if old[name]!=contract[name] or job[name]!=old[name]:
            raise ValueError('t09_restored_event_source_or_window_mismatch')
    if (old['parameter']!=contract['family'] or old['theta']!=contract['source_theta'] or
            old['normalization_domain']!=contract['original_normalization_domain']):
        raise ValueError('t09_original_family_changed')
    event=contract['restored_event'];audit=evidence['audit']
    if any(audit[key].get(event)!=contract['source_event_label'] for key in ['source_labels','repeated_labels']):
        raise ValueError('t09_restored_event_source_repeat_mismatch')
    result=copy.deepcopy(old)
    result['reference_events'][event]=contract['source_event_label']
    result.update(primary_boundary_event=event,
        restored_event_protocol=dict(file=path.relative_to(ROOT).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legacy_event_retained=contract['retained_legacy_event'],
            old_human_labels_reused=False,vertical_displacement_threshold_used=False))
    if result['status']=='incomplete':
        result['reason']='Original pull_force family and author-confirmed ever-table-contact event restored; resolve the 2-5 N response band before binding a boundary. Finite no-flip scans are not exclusions.'
    return result


def binding_signature(row):
    contexts = row.get('conditional_axes') or {'primary':row}
    return {name:dict(records=[(r['event'],r['bracket'],r['endpoint_labels'])for r in c['boundary_records']],
        full_scan_completed=c.get('conditional_solver_evidence',{}).get('full_scan_completed'))
        for name,c in contexts.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['p25', 'sg88', 'all'], default='all')
    parser.add_argument('--completed-probes', action='store_true')
    parser.add_argument('--pending-original-only', action='store_true')
    args = parser.parse_args()
    WORK.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    data = []
    for host in (['p25', 'sg88'] if args.host == 'all' else [args.host]):
        for row in collect(host,pending_original_only=args.pending_original_only):
            row['host'] = host; data.append(row)
    evidence_path = WORK / ('verified_probes_' + stamp + '.json')
    relative = evidence_path.relative_to(ROOT).as_posix()
    registry = load(); cases = {r['clip_id']:r for r in registry['cases']}
    supplement_path = WORK / 'sealed_binding_updates.json'
    supplement = (json.loads(supplement_path.read_text(encoding='utf8')) if supplement_path.exists() else
                  dict(schema='core100-sealed-followup-bindings-v1', updates=[], evidence_sha256={}))
    updates = {r['clip_id']:r for r in supplement['updates']}
    outcomes = []; changed = False
    for row in data:
        cid = row['job']['clip_id']; old = updates.get(cid, cases[cid])
        try:
            scaled = recover_original_friction_scale(old)
        except ValueError as exc:
            outcomes.append(dict(clip_id=cid,key=Path(row['root']).name,blocked=str(exc)))
            continue
        if scaled != old:
            old=scaled;updates[cid]=old;changed=True
        if row.get('preliminary_no_opposite_endpoints'):
            outcomes.append(dict(clip_id=cid,key=Path(row['root']).name,
                bound_intervals=0,preliminary_receipts_only=True,unverified_receipt_count=row['unverified_receipt_count'],
                status='no_opposite_receipt_labels_yet_not_an_exclusion'))
            continue
        unbound_axis=(old.get('conditional_axes') and row['job']['family'] not in old['conditional_axes'])
        if old['status'] == 'distance_ready' and cid not in updates and not unbound_axis:
            continue
        try:
            restored=restore_t09_original_event(old,row)
            if restored!=old:
                old=restored;updates[cid]=old;changed=True
            update = candidate_update(old, row, relative, allow_completed_probes=args.completed_probes)
        except ValueError as exc:
            outcomes.append(dict(clip_id=cid, key=Path(row['root']).name, blocked=str(exc)))
            continue
        if update and binding_signature(update) != binding_signature(old):
            updates[cid] = update
            changed = True
        outcomes.append(dict(clip_id=cid, key=Path(row['root']).name,
            full_scan_completed=bool(row['result']), bound_intervals=(len(update['boundary_records'])+
                sum(len(a['boundary_records'])for a in update.get('conditional_axes',{}).values())) if update else 0))
    if changed:
        evidence_path.write_text(json.dumps(data, indent=2), encoding='utf8')
        supplement.update(updates=list(updates.values()), at_utc=stamp)
        supplement['evidence_sha256'][relative] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        for name in ['original_friction_sampling_contract.json','frozen_source_lineage_verified.json',
                     't09_original_family_event_contract.json','t09_original_family_event_contract_v2.json',
                     't11_original_nine_point_contract_20261101.json','t11_original_global_path_contract_20261101.json',
                     't11_original_case_friction_contract_20261101.json']:
            proof=WORK/name
            if proof.exists():supplement['evidence_sha256'][proof.relative_to(ROOT).as_posix()]=hashlib.sha256(proof.read_bytes()).hexdigest()
        temporary = supplement_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(supplement, indent=2), encoding='utf8'); temporary.replace(supplement_path)
    repeat_changed=False
    if args.host in ['all','p25'] and (WORK/'t11_c02_endpoint_recheck_launch_20261101.json').exists():
        from scripts.collect_t11_c02_endpoint_rechecks import collect as collect_rechecks
        latest=WORK/'endpoint_repeatability_latest.json'
        previous=json.loads(latest.read_text(encoding='utf8'))['sha256']if latest.exists()else None
        try:
            checked=collect_rechecks()
            repeat_changed=checked['sha256']!=previous
            outcomes.append(dict(clip_id='T11_C02',key='independent_endpoint_rechecks',
                completed=checked['completed_new_endpoint_executions'],requested=checked['requested_new_endpoint_executions'],
                interval_statuses=[r['status']for r in checked['intervals']]))
        except (RuntimeError,ValueError)as exc:
            outcomes.append(dict(clip_id='T11_C02',key='independent_endpoint_rechecks',blocked=str(exc)))
    status=dict(outcomes=outcomes, sealed_cases=sum(r['status']=='distance_ready'for r in updates.values()),
        pending_definition_updates=sum(r['status']=='incomplete'for r in updates.values()),
        changed=changed or repeat_changed, evidence=relative if changed else None)
    (WORK/'collection_latest.json').write_text(json.dumps(status,indent=2),encoding='utf8')
    print(json.dumps(status))


if __name__ == '__main__':
    main()
