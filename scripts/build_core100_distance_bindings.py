"""Bind completed evidence to the active 100 references. Never launch searches.

Original observed transitions, conditional searches, and explicit no-flip scans
remain distinguishable. No reference media, prompt, or generated label is edited.
"""
import collections
import datetime
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from physedit.core100_release import load

WORK=ROOT/'review/core100_binding_20261028'
RES=ROOT/'annotation_site/resources'
EVIDENCE={}


def read(path):
    path=Path(path)
    raw=path.read_bytes()
    EVIDENCE[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def measured(theta,bracket,span):
    a,b=bracket
    assert all(math.isfinite(v)for v in [theta,a,b,span])and a<b and span>0
    low=max(a-theta,theta-b,0)/span
    high=max(abs(theta-a),abs(theta-b))/span
    bucket='near'if high<=.05 else'mid'if low>.05 and high<=.15 else'far'if low>.15 else None
    return dict(normalized_absolute_interval=[low,high],bin=bucket)


def evidence(path,detail=None):
    return dict(file=str(Path(path).relative_to(ROOT)).replace('\\','/'),detail=detail)


def main():
    release,manifest,conditions,_=load()
    condition={c['clip_id']:c for c in conditions['tasks']}
    worklist={c['clip_id']:c for c in read(WORK/'core100_priority_worklist_20261029.json')['cases']}
    initial={c['clip_id']:c for c in read(WORK/'binding.json')['cases']}
    old={c['clip_id']:c for c in read(RES/'core100_admission.json')['points']}
    fresh_path=WORK/'current_binding_evidence_20261031.json'
    fresh=read(fresh_path)
    latest={r['clip_id']:r for rows in fresh['hosts'].values()for r in rows}
    cases={}
    for cid,c in condition.items():
        ref=c.get('reference',{})
        cases[cid]=dict(clip_id=cid,scene_id=cid[:3],sample_id=c['sample_id'],
            reference_video_sha256=ref.get('sha256')or c['source_video_sha256'],
            reference_release_version=manifest['version'],status='incomplete',
            reason='No compatible completed boundary or applicability result bound yet.',
            horizon_s=initial[cid]['horizon_s'],condition_frame_index=initial[cid]['condition_frame_index'],
            end_frame_index=209 if initial[cid]['horizon_s']==4.1 else 154,
            parameter=None,theta=None,normalization_domain=None,reference_events={},
            reference_events_scope='boundary event subset; full EventExact continues to use its original protocol answer key',
            boundary_records=[],evidence=[],generated_labels_modified=False,
            ordinary_event_denominator_retained=True,model_scores_computed=False)

    def bind(cid,theta,domain,intervals,labels,path,*,kind='conditional_search',horizon=None,
             source_state=None,context=None,notes=None,finite=False,parameter=None,source_detail=None):
        r=cases[cid]
        registered=[v for v in old[cid]['numerical_distance_records']if v['canonical_event']in labels]
        if registered and registered[0].get('normalization_domain')and not cid.startswith('T19'):
            domain=registered[0]['normalization_domain']
        assert theta is not None and domain and domain[1]>domain[0],cid
        assert all(type(v)is int and v in(0,1)for v in labels.values()),(cid,labels)
        r.update(theta=theta,normalization_domain=domain,normalization_span=domain[1]-domain[0],
            reference_events=labels,parameter=parameter or r['parameter']or 'registered_original_parameter',
            source_state_sha256=source_state,fixed_context_sha256=context,
            boundary_records=[],evidence=[evidence(path,source_detail)],binding_kind=kind,notes=notes or [])
        if horizon is not None:r['horizon_s']=horizon
        r['end_frame_index']=r['condition_frame_index']+round(r['horizon_s']/(.02 if r['horizon_s']==4.1 else 1/30))
        for iv in intervals:
            event=iv.get('event')or iv.get('target_event')
            assert event and event in labels,(cid,event,labels)
            a,b=iv['bracket'];ends=iv.get('labels')
            assert ends and ends[0]in(0,1)and ends[1]==1-ends[0],(cid,iv)
            m=measured(theta,[a,b],r['normalization_span'])
            r['boundary_records'].append(dict(event=event,bracket=[a,b],endpoint_labels=ends,
                distance=m,interval_kind='observed_published_transition'if kind=='released_state_scan'else'conditional_local_search',
                exact_theta_star=None,endpoints=iv.get('endpoints',iv.get('checked_endpoints',[]))))
        if intervals:
            r.update(status='distance_ready',reason='Active reference, original parameter and compatible window are bound to completed interval evidence.')
        elif finite:
            r.update(status='not_applicable_in_registered_scan',reason='No target transition observed in the completed finite registered scan; retain ordinary event evaluation. This does not prove no hidden boundary exists.')
        else:
            r.update(status='incomplete',reason='Only source or one parameter value recovered; no boundary/applicability result.')

    # Original released trajectories take precedence over independently repaired
    # scenes and over replay-source mismatches.
    for filename in ['released_t01_t08_scans_20261031.json','released_t04_t05_scans_20261031.json',
                     'original_t16_t17_window_scans.json']:
        path=WORK/filename
        for recovered in read(path)['cases']:
            cid=recovered['clip_id'];scene=cid[:3]
            if cid in ['T16_C02','T16_C04','T17_C04','T17_C05']:continue
            if scene=='T08'and cid[-2:]in['01','02','03']:continue
            if recovered.get('status')!='released_state_window_recovered':continue
            row=latest[cid];j=row['jobs'][0]['data']if row['jobs']else {};data=row['data']
            domain=data.get('normalization_domain')or j.get('normalization_domain')or j.get('domain')
            if scene in ['T16','T17']:domain=[65.,90.]if scene=='T16'else[.15,4.]
            labels={e['event']:e['source_label']for e in recovered['events']if e['source_label']is not None}
            iv=[i for e in recovered['events']if e['event']in labels for i in e['intervals']]
            complete_constant=all(e['unique_points']>=2 and e['ambiguous_points']==0 and e['constant_observed_label']in(0,1)for e in recovered['events'])
            # If a source-matched conditional scan already covers this same
            # finite slice, use it for applicability rather than pretending one
            # saved source value proves absence of a boundary.
            if not iv and not complete_constant:
                audit=[a['data']for a in row.get('source_audits',[])]
                good=any(a.get('source_event_match')is True for a in audit)
                if good and not data.get('intervals')and not data.get('invalid_probes')and not data.get('unresolved_intervals'):
                    bind(cid,data['source_theta'],domain,[],labels,fresh_path,finite=True,
                        source_state=recovered['source']['state_sha256'],source_detail=row['path'],
                        notes=['Source-matched conditional finite scan; original saved-source labels retained.'])
                    continue
            bind(cid,recovered['source']['theta'],domain,iv,labels,path,
                kind='released_state_scan',horizon=5.,source_state=recovered['source']['state_sha256'],
                context=recovered['source']['fixed_context_sha256'],finite=complete_constant,
                notes=['Adjacent observed original parameter samples; do not substitute an interval midpoint or assert global uniqueness.'])

    # Saved-window readback: late full-video outcomes are not 5-second outcomes.
    path=WORK/'t02_existing_window_recovery_20261030.json'
    for r in read(path)['cases']:
        cid=r['clip_id'];iv=r['intervals'];existing=latest.get(cid,{})
        domain=existing.get('data',{}).get('normalization_domain')
        if domain is None:
            pts=[p['theta']for p in read(path)['matching_published_points']if p['fixed_recorded_context_sha256']==r['fixed_recorded_context_sha256']]
            domain=[min(pts),max(pts)]
        # Preserve the registered span, including when it came from a broader
        # original family domain than the matching saved points.
        assert abs(domain[1]-domain[0]-r['normalization_span'])<1e-7
        intervals=[dict(i,event=r['event'])for i in iv]
        bind(cid,r['theta'],domain,intervals,{r['event']:r['source_label']},path,
            kind='released_state_scan',finite=not iv,horizon=5.,source_state=r['source_state_sha256'],
            context=r['fixed_recorded_context_sha256'],notes=['Original labels read back at frames 5..154; full-video labels preserved separately.'])

    # Native T03 grids retain invalid points as breaks; no interval spans one.
    native_path=WORK/'remaining29_native_results_20261031.json'
    native=read(native_path)
    coarse=read(WORK/'t03_native_candidates_20261030.json')['cases']
    coarse+=read(WORK/'sg88_t03_native_candidates_20261030.json')['cases']
    t03jobs={r['clip_id']:r for r in read(WORK/'t03_jobs.json')}
    for cid in [f'T03_C{i:02}'for i in range(1,6)]:
        job=t03jobs[cid];found=next((r for r in native if r['data']['clip_id']==cid),None)
        if cid in ['T03_C01','T03_C02']:
            r=next(r for r in coarse if r['clip_id']==cid and r['source_verified'])
            iv=r['interval_candidates'];labels=r.get('source_labels')or job['expected_labels']
            notes=['Only verified valid local intervals are used; invalid probe gaps remain explicit. No nearest-global-boundary claim.']
            detail=r['path'];finite=not iv and r['invalid_points']==0
        else:
            r=found['data'];assert r['source_event_match'];groups={}
            for p in r['points']:groups.setdefault(p['theta'],[]).append(p)
            iv=[]
            for event in r['source_labels']:
                points=[]
                for theta,ps in sorted(groups.items()):
                    values={p['labels'][event]for p in ps};valid=all(p['quality_passed']for p in ps)
                    points.append((theta,next(iter(values))if valid and len(values)==1 else None))
                for (a,x),(b,y)in zip(points,points[1:]):
                    if x in(0,1)and y in(0,1)and x!=y:iv.append(dict(event=event,bracket=[a,b],labels=[x,y]))
            labels=r['source_labels'];notes=['Original fixed-source conditional native grid; all sampled invalid points retained as breaks.']
            detail=found['path'];finite=not iv and all(p['quality_passed']for p in r['points'])
        bind(cid,job['theta'],job.get('domain')or job['normalization_domain'],iv,labels,
            WORK/'t03_native_candidates_20261030.json'if cid=='T03_C01'else WORK/'sg88_t03_native_candidates_20261030.json'if cid=='T03_C02'else native_path,
            finite=finite,notes=notes,source_detail=detail,source_state=job.get('state_sha256'))

    # Completed source-matched conditional searches, excluding geometry repairs.
    selected=[f'T07_C{i:02}'for i in range(1,4)]+[f'T08_C{i:02}'for i in range(1,4)]
    selected+=[f'T11_C{i:02}'for i in range(1,6)]+[f'T15_C{i:02}'for i in range(1,6)]
    selected+=[f'T18_C{i:02}'for i in range(1,6)]+[f'T20_C{i:02}'for i in range(1,6)]
    for cid in selected:
        row=latest[cid];d=row['data'];j=row['jobs'][0]['data']if row['jobs']else{}
        audits=[a['data']for a in row.get('source_audits',[])]
        labels=(j.get('expected_labels')or d.get('source_events')or d.get('source_labels')or
                next((a['source_labels']for a in audits if a.get('source_labels')),None))
        if not labels:
            source=min(d.get('probes',[]),key=lambda p:abs(p['theta']-d['source_theta']))
            assert abs(source['theta']-d['source_theta'])<1e-8
            labels=source.get('labels')or {d['formal_event']:source['label']}
        assert not any(a.get('source_event_match')is False for a in audits),(cid,'source mismatch')
        iv=[dict(i,event=i.get('event')or d.get('formal_event'))for i in d['intervals']]
        notes=['Finite original-context conditional slice; preserve its recorded solver profile and scope.']
        if cid.startswith('T08'):
            # Only the mug event is source-matched for all three conditional
            # speed searches. The original auxiliary event vector is retained.
            original=next(r for r in read(WORK/'released_t01_t08_scans_20261031.json')['cases']if r['clip_id']==cid)
            labels={e['event']:e['source_label']for e in original['events']}
            assert labels['t08_target_mug_below_table_8cm']==d['source_events']['t08_target_mug_below_table_8cm']
            iv=[i for i in iv if i['event']=='t08_target_mug_below_table_8cm']
            notes+=['Boundary is for the mug only; do not replace the original auxiliary book labels with replay labels. Physical specs match; visual asset paths relocated.']
        bind(cid,d['source_theta'],d['normalization_domain'],iv,labels,fresh_path,finite=not d.get('invalid_probes')and not d.get('unresolved_intervals'),
            horizon=d['horizon_s'],source_state=d.get('published_state_sha256')or d.get('source_state_sha256'),
            notes=notes,source_detail=row['path'],parameter=j.get('family')or j.get('family_id'))

    # Original same-window friction boundary; no unnecessary new simulation.
    path=WORK/'t07_original_boundary_reuse_20261030.json';r=read(path)
    for c in r['cases']:
        theta=next(n['theta']for n in old[c['clip_id']]['numerical_distance_records'])
        bind(c['clip_id'],theta,r['normalization_domain'],[dict(event=r['event'],bracket=r['bracket'],labels=r['endpoint_labels'])],
             {r['event']:c['source_label']},path,source_state=c['source_state_sha256'],horizon=5.)

    # Preserve original searches with their original conditional/replay scope.
    for filename in ['legacy_six_endpoint_audit_20261030.json','legacy_t06_t10_recovery_20261030.json']:
        path=WORK/filename
        for r in read(path):
            cid=r['clip_id']
            if cid=='T06_C04':continue # wrong-engine historical interval superseded
            original=old[cid]['numerical_distance_records'][0]
            probes=r['checked_endpoints'];labels=original.get('reference_label')
            if labels not in(0,1):
                # Source label recovered from original reference contract/scan,
                # never inferred by deciding which side of a boundary theta is.
                src=worklist[cid].get('original_source_recovery')or{}
                labels=src.get('reference_labels',{}).get(r['event'])
            if labels not in(0,1):
                source=latest.get(cid,{}).get('data',{});ps=source.get('probes',[])
                exact=[p for p in ps if abs(p['theta']-original['theta'])<1e-7]
                if exact:labels=exact[0]['labels'].get(r['event'])
            if labels not in(0,1):
                cases[cid]['reason']='Original interval recovered; same-window source event truth still unresolved.'
                continue
            iv=[dict(event=r['event'],bracket=r['bracket'],labels=[p['label']for p in probes])]
            iv+=r.get('additional_verified_event_intervals',[])
            source_labels={r['event']:labels}
            iv=[i for i in iv if i.get('event')in source_labels]
            bind(cid,original['theta'],original['normalization_domain'],iv,source_labels,path,
                horizon=r['horizon_s'],notes=[r.get('legacy_scope')or r.get('reference_compatibility'),
                    'Original recorded conditional/replay scope retained; not relabelled as same-seed uniqueness.'])

    # Author-approved native-contact target amendments already have reference
    # truth and source-prefix witnesses. They are not old terminal-fall targets.
    truth={r['clip_id']:r for r in read(RES/'core100_contact_reference_truth_20261027.json')['references']}
    for filename in ['core100_contact_boundaries_20261027.json','core100_t13_contact_boundaries_20261027.json']:
        path=RES/filename;groups=collections.defaultdict(list)
        for r in read(path)['records']:groups[r['clip_id']].append(r)
        for cid,rs in groups.items():
            t=truth[cid];assert t['video_sha256']==cases[cid]['reference_video_sha256']
            labels=dict(t['reference_label_events'])
            if any(r['target_event']=='registered_two_contact_conjunction_and_order'for r in rs):
                labels['registered_two_contact_conjunction_and_order']=int(all(labels.values())and t['reference_order_valid'])
            bind(cid,rs[0]['source_theta'],rs[0]['normalization_domain'],
                [dict(event=r['target_event'],bracket=r['bracket'],labels=r['labels'])for r in rs],
                labels,path,source_state=t['reference_state_sha256'],
                notes=['Existing author-approved contact-target amendment; original terminal-event records preserved.'])

    # Exact original Isaac T06 result, rather than Genesis thresholds.
    path=RES/'core100_recovered_numerical_bindings.json'
    for r in read(path)['records']:
        assert r['reference_video_sha256']==cases[r['clip_id']]['reference_video_sha256']
        bind(r['clip_id'],r['theta'],r['normalization_domain'],[dict(event=r['target_event'],bracket=r['original_boundary_interval'],labels=[0,1])],
            {r['target_event']:r['reference_label']},path,horizon=r['evaluation_horizon_s'],source_state=r['source_original_state_sha256'])

    # Sealed v3 T16 C04 is not the old production trajectory.
    r=next(r for r in native if r['data']['clip_id']=='T16_C04');d=r['data']
    assert d['published_state_sha256']==condition['T16_C04']['reference']['state_sha256']
    audit=next(a['data']for a in r['audits']if a['data'].get('source_event_match')is True)
    bind('T16_C04',d['source_theta'],d['normalization_domain'],d['intervals'],audit['source_labels'],native_path,
         source_state=d['published_state_sha256'],notes=['Sealed v3 reference; solver profile retained. Failed distant probes do not erase valid local intervals. No global-nearest-boundary assertion.'])
    optional=WORK/'t16_c02_exact_result_20261031.json'
    if optional.exists():
        r=read(optional);d=r['data'];audit=r['source_audit']
        assert d['published_state_sha256']==condition['T16_C02']['reference']['state_sha256']
        if audit.get('source_event_match')is True:
            bind('T16_C02',d['source_theta'],d['normalization_domain'],d['intervals'],audit['source_labels'],optional,
                source_state=d['published_state_sha256'],finite=not d['invalid_probes']and not d['unresolved_intervals'])
    if cases['T16_C02']['status']=='incomplete':cases['T16_C02']['reason']='Sealed v3 source reproduced. Valid probes and failed-contact probes leave a transition gap; targeted completion inside the original range is running.'

    # Existing explicitly admitted 6.4-second T17 pair takes precedence over
    # source-window 5-second readback.
    path=RES/'reference_window_admission.json';admitted=read(path)
    for r in admitted['references']:
        bind(r['clip_id'],r['theta'],r['normalization_domain'],[dict(event=r['target_event'],bracket=r['boundary_interval'],labels=[0,1])],
            {r['target_event']:r['reference_label']},path,horizon=r['horizon_s'],source_state=r['reference_state_sha256'])
        cases[r['clip_id']]['reference_admission']=r['reference_admission']

    # Active T19 five are fully separate from the retired reference records.
    path=release/'answers_t19.jsonl'
    EVIDENCE[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
    for r in [json.loads(s)for s in path.read_text(encoding='utf8').splitlines()]:
        cid=r['point_id'];c=cases[cid];c['condition_frame_index']=0
        span=r['boundary']['normalization_span']
        bind(cid,r['theta'],[-.14,.14],[dict(event=r['target_event'],bracket=r['boundary']['bracket'],labels=[0,1]if cid!='T19_C05'else[1,0])],
             r['events'],path,horizon=209/30,source_state=condition[cid]['reference'].get('state_sha256'),
             notes=['Active T19 release; old references and model outputs remain historical.'])
        assert abs(span-c['normalization_span'])<1e-10
        c['reference_admission']='active_hash_bound_reference_package'

    for cid in ['T06_C01','T06_C02','T06_C03','T09_C01','T10_C01','T10_C02']:
        r=cases[cid];r['evidence']=[evidence(fresh_path,latest[cid]['path'])]
        r['reason']='Pinned published config recovered; original per-frame state missing. Original-setting GPU completion is running; older CPU replay alone is not substituted for source truth.'
    path=WORK/'t14_original_source_binding_20261031.json'
    for r in read(path):
        cid=r['clip_id'];row=latest[cid];d=row['data']
        assert not r['physical_spec_differences']and not r['physical_setting_differences']
        audits=[a['data']for a in row['source_audits']]
        if any(a.get('source_labels')==r['reference_labels']for a in audits):
            bind(cid,d['source_theta'],d['normalization_domain'],d['intervals'],r['reference_labels'],fresh_path,
                source_state=r['source_state_sha256'],finite=not d['invalid_probes']and not d['unresolved_intervals'],
                notes=['Original pinned R006 metadata recovered; exact physical specs/settings/clock verified.'],source_detail=row['path'])
            cases[cid]['evidence'].append(evidence(path))
        else:
            cases[cid]['reason']='Original R006 metadata recovered. CPU replay source events differ; original-setting GPU search running, incompatible CPU result not admitted.'

    completed_path=WORK/'remaining_completed_results_20261031.json'
    if completed_path.exists():
        published={r['clip_id']:r for r in read(WORK/'legacy_published_configs_20261031.json')}
        t14truth={r['clip_id']:r for r in read(WORK/'t14_original_source_binding_20261031.json')}
        for recovered in read(completed_path):
            cid=recovered['clip_id']
            if 'result'not in recovered:
                state=recovered.get('status',{}).get('state')
                if state in ['runtime_failure_requires_repair','unresolved_after_bounded_physics_profiles']:
                    cases[cid]['reason']='Original-setting completion did not produce an admissible result: '+str(recovered.get('rejections')or state)
                continue
            d=recovered['result'];audit=recovered['source_audit'];j=recovered['job']
            assert recovered['completed_probe_state_hashes_verified']and recovered['completed_probe_config_hashes_verified']
            assert audit['source_labels']==audit['repeated_labels']
            if cid in published:
                p=published[cid];actual=recovered['source_config_physical_inputs'];original=p['config']
                assert j['config_sha256']==p['sha256']
                assert all(actual[k]==original.get(k)for k in ['seed','random_seed','dynamic_objects','runtime_forces','scene_overrides','experiment','render'])
                notes=['Original pinned published configuration and seed; original-setting GPU numerical recovery. Original per-frame source state was unavailable.',
                    'Native overlap and spatial repeat diagnostics retained separately. Numerical completion is not physical-quality certification or generated-video annotation.']
                source_state=None
            else:
                expected=t14truth[cid]['source_state_sha256']if cid.startswith('T14')else condition[cid]['reference']['state_sha256']
                assert d['published_state_sha256']==expected and audit['source_event_match']is True
                source_state=expected;notes=['Original-reference source event reproduced; completed local search inside the registered original domain.']
            bind(cid,d['source_theta'],d['normalization_domain'],d['intervals'],audit['source_labels'],completed_path,
                source_state=source_state,horizon=d['horizon_s'],finite=not d['invalid_probes']and not d['unresolved_intervals'],
                notes=notes,source_detail=recovered['root'],parameter=j.get('family'))
            cases[cid]['source_truth_origin']='recomputed_from_pinned_original_config'if cid in published else'original_state_and_reproduced_event'
            probes=d['probes']+d['invalid_probes']
            cases[cid]['source_diagnostics']=dict(maximum_native_overlap_m=max(p['native_peak_m']for p in probes),
                points_above_additional_1mm_diagnostic=sum(p['native_peak_m']>.001 for p in probes),
                source_repeat_max_position_error_m=audit['max_position_error_m'],
                original_video_outcome_independently_verified=cid not in published,
                physics_quality_approval_granted=False)
            if cases[cid]['status']=='incomplete':
                cases[cid]['reason']='Source event reproduced, but failed probes leave unresolved gaps; no valid interval or complete finite no-flip result.'

    # Name the actual physical axis; scene/family shorthand alone is ambiguous.
    axes={'T01':'chain_surface_friction_coefficient','T02':'probe_initial_speed_mps',
        'T04':'commanded_support_extraction_speed_mps','T05':'gap_ratio',
        'T07':'phone_surface_friction_coefficient','T08':'lower_impactor_initial_speed_mps',
        'T11':'driver_initial_speed_command_mps','T12':'stapler_initial_speed_mps',
        'T13':'falling_book_edge_distance_m','T14':'channel_throat_width_m',
        'T16':'support_angle_deg','T17':'can_initial_speed_mps','T19':'impact_eccentricity_m'}
    for cid,r in cases.items():
        scene=cid[:3]
        if scene in axes:r['parameter']=axes[scene]
        elif scene=='T03':r['parameter']='book_initial_speed_mps'if cid[-2:]in['04','05']else'lower_phone_com_edge_distance_m'
        elif scene=='T15':r['parameter']='driver_book_initial_speed_mps'if cid[-2:]in['01','02','03']else'laptop_edge_margin_m'
        else:
            row=latest.get(cid,{});jobs=row.get('jobs',[])
            if jobs:r['parameter']=jobs[0]['data'].get('family')or jobs[0]['data'].get('family_id')or r['parameter']
            if r['parameter']in(None,'registered_original_parameter')and old[cid]['numerical_distance_records']:
                r['parameter']=old[cid]['numerical_distance_records'][0].get('family_id')
        if cid in latest:
            d=latest[cid]['data'];r['conditional_solver_evidence']=dict(backend=d.get('backend'),profile=d.get('profile'),
                invalid_probes=len(d.get('invalid_probes',[])),unresolved_intervals=len(d.get('unresolved_intervals',[])))

    # Retain recovered recorded values as traceable auxiliary references. They
    # do not override an active window-specific boundary or another release.
    path=WORK/'remaining_original_numeric_sources_20261031.json'
    for source in read(path):
        cid=source.get('clip_id')
        if cid not in cases or source.get('sample_id')!=cases[cid]['sample_id']:continue
        value=source.get('original_critical_value');interval=source.get('original_boundary_interval')
        if value is None and not interval:continue
        cases[cid].setdefault('retained_original_numerical_sources',[]).append(dict(
            kind=source.get('original_reference_kind'),value=value,interval=interval,
            normalization_span=source.get('normalization_span'),source_file=source.get('source_file')or source.get('ledger_source'),
            active_applicability='Trace retained; use the separately bound active event/window record for scoring.',
            recorded_value_absolute_distance=abs(source['theta']-value)if value is not None else None))

    original_review=ROOT/'review/core100_no_flip_reaudit_20261031/review.json'
    if original_review.exists():
        from scripts.reaudit_core100_original_references import apply_review
        review=read(original_review)
        apply_review(cases,review)
        for proof in review['cases']:
            for name in proof['evidence']:
                path=ROOT/name
                EVIDENCE[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    # Sealed follow-up searches are applied after the older source-review reset.
    for relative in ['review/core100_completion_20261031/sealed_binding_updates.json',
                     'review/core100_remaining16_20261031/sealed_binding_updates.json']:
        supplement=ROOT/relative
        if supplement.exists():
            from scripts.apply_core100_completion_updates import apply_updates
            apply_updates(cases,read(supplement),ROOT,EVIDENCE)
    rows=[cases[cid]for cid in sorted(cases)]
    counts=collections.Counter(r['status']for r in rows)
    assert len(rows)==100 and sum(counts.values())==100
    scenes=[]
    for i in range(1,21):
        scene=f'T{i:02}';own=[r for r in rows if r['scene_id']==scene]
        scenes.append(dict(scene_id=scene,**{k:sum(r['status']==k for r in own)for k in ['distance_ready','not_applicable_in_registered_scan','incomplete']}))
    summary=dict(total=100,**{k:counts[k]for k in ['distance_ready','not_applicable_in_registered_scan','incomplete']},
        observed_transition_cases=sum(r['status']=='distance_ready'and r['binding_kind']=='released_state_scan'for r in rows),
        conditional_search_cases=sum(r['status']=='distance_ready'and r['binding_kind']not in('released_state_scan','original_recorded_calibration')for r in rows),
        interval_reference_cases=sum(r['status']=='distance_ready'and bool(r['boundary_records'])for r in rows),
        recorded_calibration_reference_cases=sum(r['status']=='distance_ready'and bool(r.get('original_calibration_reference'))for r in rows),
        numerical_near_candidate_cases=sum(any(b['distance']['bin']=='near'for b in r['boundary_records'])for r in rows),
        generated_model_scores_computed=False)
    result=dict(schema='core100-active-distance-bindings-v1',generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reference_release_version=manifest['version'],
        summary=summary,cases=rows,scenes=scenes,evidence_sha256=EVIDENCE,
        policy=dict(no_near_targeted_rescan=True,no_original_inputs_or_labels_modified=True,
            finite_no_flip_is_not_global_nonexistence=True,observed_interval_is_not_an_exact_threshold=True,
            pending_generated_labels_are_not_zeros=True,metric_applicability_separate_from_reference_binding=True))
    output=RES/'core100_distance_bindings.json';temporary=output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(output)
    lines=['# Core100 临界距离接入结果','', '这是参考参数与临界证据的接入状态，不是生成模型成绩。', '',
        f"100条：已接数值参考 {counts['distance_ready']}（边界区间{summary['interval_reference_cases']}、原校准值{summary['recorded_calibration_reference_cases']}）；已确认不适用 {counts['not_applicable_in_registered_scan']}；原族/事件/观察窗仍待对齐 {counts['incomplete']}。",'',
        '原21条统一不适用结论已撤回。有限扫描无翻转不能证明没有原临界值；原族未核清的保留待对齐。原校准点、原采样中心与已测边界区间分别记录，不冒充精确物理阈值。','',
        '| 场景 | 已接数值参考 | 已确认不适用 | 待对齐 |','|---|---:|---:|---:|']
    lines += [f"| {r['scene_id']} | {r['distance_ready']} | {r['not_applicable_in_registered_scan']} | {r['incomplete']} |"for r in scenes]
    lines+=['','## 接入命令','','```text','python -m physedit.core100_bindings status --verify-evidence',
        'python -m physedit.core100_bindings export --out core100_distance_reference.jsonl','```','',
        '评分代码 `annotation_site/critical_results.py` 已读取此表。匹配同时检查参考视频哈希和观察时长，不能仅按案例ID套用。',
        '数值接入不自动批准视频质量，也不生成模型事件标签。完整EventExact仍使用原事件协议的全部标签与时序要求。',
        '此参考表只供评分器使用；不得把参考事件答案或临界值发给视频生成器、VLM事件裁判。',
        '有限扫描无翻转只作为诊断；原族、事件或窗口未核清时保持待对齐，不直接判不适用。',
        '原始区间、条件补算和物理诊断分别保留；区间跨越Near/Mid/Far阈值时保留未定，不取中点强行分组。',
        '', '## 未完成项','']
    remaining=[r for r in rows if r['status']=='incomplete']
    for r in remaining:
        cid=r['clip_id']
        if 'running'in r['reason']:
            text=('原状态已找回；CPU复跑与原结果不同，正在用原GPU设置补算。'if cid.startswith('T14')else
                  '已复现冻结修复版来源；正在原参数范围内补齐有效转变区间。'if cid=='T16_C02'else
                  '已找回原发布配置和种子；原逐帧状态缺失，正在用原GPU设置补算。')
        else:text=r['reason']
        lines.append(f'- {cid}：{text}')
    if not remaining:lines.append('无。')
    lines+=['','## 100条逐项明细','',
        '| 案例 | 原参数轴 | 参数值 | 观察窗(s) | 距离接入状态 | 分组 |',
        '|---|---|---:|---:|---|---|']
    labels={'distance_ready':'已接数值参考','not_applicable_in_registered_scan':'已确认不适用','incomplete':'原族待对齐'}
    for r in rows:
        bins=sorted({b['distance']['bin']or'区间跨分界'for b in r['boundary_records']})
        theta=f"{r['theta']:.9g}"if type(r['theta'])in(int,float)else json.dumps(r['theta'],ensure_ascii=False)if r['theta']is not None else'待定'
        bin_text=', '.join(bins)or('原校准值距离，非精确边界'if r.get('original_calibration_reference')else'待定')
        lines.append(f"| {r['clip_id']} | {r['parameter']} | {theta} | {r['horizon_s']:.6g} | {labels[r['status']]} | {bin_text} |")
    (ROOT/'docs/critical_boundary/CORE100_DISTANCE_BINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(summary));print([(r['clip_id'],r['reason'])for r in rows if r['status']=='incomplete'])


if __name__=='__main__':main()
