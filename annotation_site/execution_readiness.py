"""Live coverage over independently verified evidence; never auto-admit a boundary."""
import collections,json
from pathlib import Path
from workflow import final_annotation
from input_contract import matches_frozen_input
from window_contract import window_binding

RES=Path(__file__).parent/'resources'

def calculate(tasks):
    p=RES/'core100_execution_evidence.json'
    if not p.exists():return {'status':'not_registered'}
    evidence=json.loads(p.read_text(encoding='utf8'))
    policy=json.loads((RES/'core100_final_input_policy.json').read_text(encoding='utf8'))
    physical=json.loads((RES/'core100_physical_windows_20261027.json').read_text(encoding='utf8'))['cases']
    by=collections.defaultdict(list)
    for t in tasks:by[t['payload']['clip_id']].append(t)
    cases=[];windows=[]
    for r in evidence['cases']:
        own=by[r['clip_id']];states=collections.Counter(t['state']for t in own)
        blockers=[b for b in r['blockers'] if b not in ('human_records_pending','some_event_labels_missing_or_unobservable')]
        if any(t['state']!='resolved'for t in own):blockers.append('human_records_pending')
        for t in own:
            h=final_annotation(t)
            if h and h.get('quality',{}).get('status')=='pass' and any(h.get('events',{}).get(k,{}).get('label') not in ('yes','no')for k in r['events']):
                blockers.append('some_event_labels_missing_or_unobservable');break
        cases.append({**r,'blockers':blockers,'registered_outputs':len(own),'human_states':dict(states),
                      'actual_input_matches':sum(matches_frozen_input(t['payload'],policy)for t in own)})
        if r['clip_id']not in physical:continue
        rule=physical[r['clip_id']]
        for t in own:
            x=t['payload'];human=final_annotation(t);event=rule['source_event']['target_event'];binding=window_binding(x,physical)
            identity=bool(human)and human.get('video_sha256')==x['video_sha256']and human.get('protocol_sha256')==x.get('protocol_sha256')
            q=(human or{}).get('quality',{}).get('status');label=(human or{}).get('events',{}).get(event,{}).get('label')
            blockers=[]
            if not matches_frozen_input(x,policy):blockers.append('actual_input_identity_pending')
            if not binding['native_covers']:blockers.append('native_shorter_than_registered_physical_window;keep_native_diagnostic')
            if not identity:blockers.append('final_human_identity_pending')
            if not binding['annotation_window_matches']:
                if event=='complete_required_contact_chain'and binding['native_covers']and q=='pass'and label=='no':
                    blockers.append('negative_contact_chain_can_inherit_to_prefix_after_semantic_check')
                else:blockers.append('physical_window_review_required')
            if event=='support_pen_displacement_reaches_source_threshold':blockers.append('original_metric_calibration_required_not_pixel_guess')
            if not rule.get('reference_rgb_admitted'):blockers.append('reference_rgb_admission_pending')
            if not rule.get('formal_boundary_admitted'):blockers.append('boundary_admission_pending')
            windows.append(dict(task_id=t['id'],clip_id=x['clip_id'],model=x['model'],seed=x['seed'],prompt_variant=x['prompt_variant'],
                native_duration_s=x['duration_s'],annotation_window_s=x['window_s'],required_horizon_s=rule['required_horizon_s'],
                endpoint_native_frame=binding['generated_endpoint_frame'],endpoint_discretization_s=binding['endpoint_discretization_s'],
                final_human_identity=identity,human_quality=q,human_event_label=label,blockers=blockers,NearAcc=None,PairAcc=None))
    scenes=[]
    for scene in [f'T{i:02d}'for i in range(1,21)]:
        own=[r for r in cases if r['scene']==scene]
        scenes.append(dict(scene=scene,cases=len(own),registered_outputs=sum(r['registered_outputs']for r in own),
            actual_input_matches=sum(r['actual_input_matches']for r in own),human_final=sum(r['human_states'].get('resolved',0)for r in own),
            historical_numeric_cases=sum(r['historical_numeric_records']>0 for r in own),
            interval_candidate_cases=sum(r['live_interval_receipts']>0 for r in own),
            finite_no_flip_cases=sum(r['live_no_flip_receipts']>0 for r in own),
            admitted_reference_cases=sum(r['reference_admitted']for r in own)))
    return dict(schema='core100-execution-evidence-v1',status='numerical_evidence_connected_admission_explicit',
        evidence_checked_at=evidence['checked_at_utc'],summary=dict(scene_count=len(scenes),case_count=len(cases),
        actual_input_matches=sum(r['actual_input_matches']for r in cases),verified_numeric_files=evidence['verified_numeric_files'],
        verified_probe_state_hashes=evidence.get('verified_probe_state_hashes'),
        verified_probe_config_hashes=evidence.get('verified_probe_config_hashes'),
        probe_config_receipt_missing=evidence.get('probe_config_receipt_missing'),
        T12_T13_verified_probe_states=evidence['T12_T13_verified_probe_states'],physical_window_cases=len(physical),
        physical_window_outputs=len(windows),physical_window_statuses=dict(collections.Counter(b for r in windows for b in r['blockers']))),
        scenes=scenes,cases=cases,physical_window_outputs=windows,T17_five_second_boundary=evidence.get('T17_five_second_boundary'),
        note='Existing event and distance rules retained. Numerical receipts, native reference event labels, RGB admission and generated annotations are separate. Finite scans do not establish absence of a global boundary. Current physical-window registry is source-clock evidence; source/replay compatibility is not inferred from equal duration.')
