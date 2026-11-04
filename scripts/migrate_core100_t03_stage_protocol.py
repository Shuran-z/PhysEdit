"""Apply the author-approved T03 stage without inheriting complete-C2 scores."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load,primary,sha
from physedit.core100_bindings import interval_distance
from physedit.t03_visual_events import EVENT,PHONE,CAN,SUPPORT,contract

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'benchmarks/t03_observable_stage_candidate_v1_20261103'
OUT=ROOT/'benchmarks/core100_critical_protocol_v4_20261103'
APPROVAL=ROOT/'review/core100_v3_remaining8_20261103/AUTHOR_T03_STAGE_APPROVAL.json'


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))


def checked(name):
    pointer=read(CANDIDATE/name);path=CANDIDATE/pointer['path']
    if sha(path)!=pointer['sha256']:raise ValueError('t03_stage_evidence_changed:'+name)
    return read(path),path


def migrate(base,readback,axis_contract,reviews,approval,corrected_R032=None):
    if approval['cases']!=['T03_C02','T03_C03']or approval['primary_event']!=EVENT:
        raise ValueError('t03_stage_author_scope_changed')
    result=copy.deepcopy(base);visual={r['clip_id']:r for r in reviews['reviews']};axes={r['clip_id']:r for r in axis_contract['cases']}
    for row in result['cases']:
        cid=row['clip_id']
        if cid not in approval['cases']:continue
        # Replaying this migration must start from the preserved original
        # event, not reinterpret the previous new-stage answer as old C2.
        if row.get('stage_event_revision'):
            prior=row['stage_event_revision']['old']
            for name in ['reference_events','boundary_records','critical_units','judge_protocol']:
                row[name]=copy.deepcopy(prior[name])
            row['admitted_rgb_events']=[e for e in row['admitted_rgb_events']if e!=EVENT]
            row.pop('original_event_stage_closure',None)
        refs=[r for r in readback['rows']if r['clip_id']==cid];source=next(r for r in refs if r['kind']=='frozen_reference')
        proof=axes[cid];rgb=visual[cid];native=row['reference_native_state_binding']
        if not(source['reference_video_sha256']==proof['reference_video_sha256']==rgb['reference_video_sha256']==row['reference_video_sha256']
               and source['stored_state_sha256']==proof['native_stored_state_sha256']==native['stored_state_sha256']
               and source['measurement']['window_frames']==[row['condition_frame_index'],row['end_frame_index']]
               and proof['physical_objects_solver_controls_verified']and row['parameter']==proof['original_parameter']
               and row['normalization_domain']==proof['normalization_domain']):
            raise ValueError('t03_stage_reference_identity_or_family_changed')
        label=source['measurement']['label']
        if type(label)is not int or label not in[0,1]:raise ValueError('t03_new_stage_truth_unknown')
        endpoints=[r for r in refs if r['kind']=='existing_endpoint'];endpoints.sort(key=lambda p:p['theta'])
        actual={p['theta']:p for p in proof['points']}
        for p in endpoints:
            original=actual[p['theta']]
            if p['decoded_state_sha256']!=original['decoded_state_sha256']:raise ValueError('t03_stage_endpoint_state_changed')
        numerical_valid=(len(endpoints)==2 and all(all(p[k]for k in ['original_C_geometry_verified','physical_solver_matches_original','original_window_clock_matches','original_config_seed_matches','effective_seed_matches'])for p in proof['points']))
        corrected_used=False;excluded=[]
        if cid=='T03_C02'and corrected_R032 is not None:
            excluded=[p for p in corrected_R032['points']if p['status'].startswith('excluded_')]
            fresh=[p for p in corrected_R032['points']if not p['status'].startswith('excluded_')]
            fresh.sort(key=lambda p:p['theta'])
            if len(fresh)==2 and [p['theta']for p in fresh]==[.1,.4]and all(p['status']=='completed'for p in fresh):
                for p in fresh:
                    if not(p['original_C_axis_solver_seed_and_clock_verified']
                            and p['reference_video_sha256']==row['reference_video_sha256']
                            and p['original_native_state_sha256']==native['stored_state_sha256']
                            and p['original_config_sha256']==proof['original_config_sha256']
                            and p['original_random_seed']==proof['source_random_seed']
                            and p['backend']['actual_init_seed']==proof['effective_Genesis_seed']
                            and p['backend']['backend']=='gpu32'):
                        raise ValueError('t03_corrected_R032_identity_or_seed_changed')
                endpoints=fresh;numerical_valid=True;corrected_used=True
        if numerical_valid:
            if [p['measurement']['label']for p in endpoints]!=[1,0]:raise ValueError('t03_new_stage_opposite_endpoints_missing')
            if endpoints[0]['theta']!=row['theta']or endpoints[0]['measurement']['label']!=label:
                raise ValueError('t03_new_stage_source_outcome_conflict')
        observable=(rgb['status']=='observable'and rgb['label']==label)
        if rgb['label']is not None and rgb['label']!=label:raise ValueError('t03_stage_visual_reference_conflict')
        old=dict(reference_events=copy.deepcopy(row['reference_events']),boundary_records=copy.deepcopy(row['boundary_records']),critical_units=copy.deepcopy(row['critical_units']),judge_protocol=copy.deepcopy(row['judge_protocol']))
        row['reference_events'].pop('phone_second_fall_original',None);row['reference_events'][EVENT]=label
        row['judge_protocol']['events'].pop('phone_second_fall_original',None)
        row['judge_protocol']['events'][EVENT]=dict(name='罐碰手机后手机越缘下落',definition=contract()['definition'],actors=[CAN,PHONE,SUPPORT],
            applicable=True,minimum_evidence_times=3,role='author_approved_visible_stage',formal_scoring_allowed=True,
            uncertainty_policy=contract()['unknown_policy'],prompt_definition_source='Registered author-approved stage; never inferred from generated video or reference outcome.')
        span=row['normalization_span'];bracket=[p['theta']for p in endpoints]if numerical_valid else None
        distance=interval_distance(row['theta'],bracket,span)if bracket else None
        row['boundary_records']=([dict(event=EVENT,bracket=bracket,endpoint_labels=[1,0],distance=distance,
            interval_kind='original_C_axis_existing_GPU_states_reread',exact_theta_star=None,
            outside_original_parameter_domain=not all(row['normalization_domain'][0]<=p<=row['normalization_domain'][1]for p in bracket))]if bracket else[])
        unit=dict(reference_id=hashlib.sha256(json.dumps([OUT.name,cid,EVENT,bracket,row['horizon_s']]).encode()).hexdigest(),
            clip_id=cid,axis=row['parameter'],theta=row['theta'],event=EVENT,label=label,
            intervals=[bracket]if bracket else[],normalization_span=span,
            normalized_absolute_interval=distance['normalized_absolute_interval']if distance else None,bin=distance['bin']if distance else None,
            numerical_evidence_status='bound_local_intervals'if bracket else'matching_reference_version_boundary_missing',
            rgb_distance_admitted=numerical_valid and observable,supplemental_axis=False,
            rgb_blockers=([]if numerical_valid and observable else ['reference_stage_observability_pending']if numerical_valid else['original_random_seed_corrected_endpoints_pending']),
            exact_or_unique_physical_root_claimed=False)
        row['critical_units']=[unit];row['numerical_boundary_complete']=row['original_family_boundary_complete']=bool(bracket)
        row['admitted_rgb_events']=[e for e in row['admitted_rgb_events']if e!='phone_second_fall_original']
        if observable:row['admitted_rgb_events'].append(EVENT)
        row['rgb_reference_status']='target_reference_admitted'if observable else'reference_stage_visual_review_required'
        row['rgb_pending_reason']=None if observable else'新阶段的原状态真值已读回，但手机在画面下缘部分裁切；需复核越缘下落能否由画面可靠确认，不能只因出画判跌落。'
        row['distance_admission_pending_reason']=None if numerical_valid and observable else(
            '原R032配置已找回；旧端点漏用原random_seed，已隔离为诊断。正确原种子两侧在补算，参考阶段的下缘可见性另送复核。'if not numerical_valid else row['rgb_pending_reason'])
        row['stage_event_revision']=dict(version=OUT.name,old=old,new_event=EVENT,source_witness=source['measurement'],
            reference_visual_review=rgb,original_axis_contract=proof,
            corrected_original_seed_states_used=corrected_used,excluded_numeric_attempts=excluded,
            original_complete_C2=dict(reference_state_label=old['reference_events']['phone_second_fall_original'],visual_applicability='floor_contact_not_observable_in_fixed_view',
                retained_for_original_state_and_protocol_audits=True,formal_RGB_score=None),
            old_generated_labels_transferred=False,complete_chain_EventExact_claimed=False)
        if numerical_valid:
            replay=endpoints[0]['measurement'];native_onset=source['measurement'].get('first_frame');replay_onset=replay.get('first_frame')
            row['original_event_stage_closure']=dict(source_comparison_scope='Original physical C-axis config, effective seed, solver and state witness; binary edge-fall stage only.',
                source_full_window_position_error_m=endpoints[0]['source_full_window_position_errors_m']if corrected_used else actual[row['theta']]['source_full_window_position_errors_m'],
                onset_offset_frames=replay_onset-native_onset if replay_onset is not None and native_onset is not None else None,
                applicability='Contact-then-edge-fall binary stage and observed local interval only; onset timing, complete C2, whole causal chain and inversion are not certified.')
    result['version']=OUT.name
    cases=result['cases'];summary=result['summary']
    for name in ['numerical_boundary','original_family_boundary']:
        key='numerical_boundary_complete'if name=='numerical_boundary'else'original_family_boundary_complete'
        summary[name+'_cases']=sum(c[key]for c in cases)
        summary['numerical_boundary_pending'if name=='numerical_boundary'else'original_family_pending']=[c['clip_id']for c in cases if not c[key]]
    summary['critical_rgb_distance_cases']=sum(primary(c)['rgb_distance_admitted']for c in cases)
    summary['critical_rgb_distance_pending']=[c['clip_id']for c in cases if not primary(c)['rgb_distance_admitted']]
    summary['admitted_near_cases']=sum(primary(c)['rgb_distance_admitted']and primary(c)['bin']=='near'for c in cases)
    summary['numerical_near_cases']=sum(primary(c)['bin']=='near'for c in cases)
    summary['reference_rgb_target_admitted']=summary['primary_rgb_event_cases']=sum(primary(c)['event']in c['admitted_rgb_events']for c in cases)
    summary['reference_rgb_target_pending']=summary['primary_rgb_event_pending']=[c['clip_id']for c in cases if primary(c)['event']not in c['admitted_rgb_events']]
    result['policy']['T03_stage_revision']='Author-approved visible stage for C02/C03. Full C2 retained separately; no old label transfer or out-of-view floor inference.'
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-active-sha256',required=True);parser.add_argument('--activate',action='store_true');args=parser.parse_args()
    data,parent=load();assert sha(parent)==args.expected_active_sha256
    readback,readback_path=checked('CURRENT.json');axes,axes_path=checked('ORIGINAL_AXIS_CONTRACT.json');review_path=CANDIDATE/'RGB_REVIEW.json'
    corrected_pointer=ROOT/'review/core100_v3_remaining8_20261103/T03_CORRECT_SEED_COLLECT.json'
    corrected=None;corrected_path=None
    if corrected_pointer.exists():
        pointer=read(corrected_pointer);corrected_path=ROOT/pointer['path']
        if sha(corrected_path)!=pointer['sha256']:raise ValueError('t03_corrected_result_changed')
        corrected=read(corrected_path)
    if readback['module_sha256']!=sha(ROOT/'physedit/t03_visual_events.py'):raise ValueError('t03_stage_code_changed')
    result=migrate(data,readback,axes,read(review_path),read(APPROVAL),corrected)
    assert result['input_bindings']==data['input_bindings']and result['pairs']==data['pairs']
    result.setdefault('stage_revision_parent',dict(path=parent.relative_to(ROOT).as_posix(),sha256=sha(parent)))
    OUT.mkdir(exist_ok=True);(OUT/'sources').mkdir(exist_ok=True)
    files=[readback_path,axes_path,review_path,APPROVAL,Path(__file__),ROOT/'physedit/t03_visual_events.py',ROOT/'scripts/recover_t03_original_axis_contract.py',ROOT/'physedit/core100_critical.py']
    if corrected_path:files+=[corrected_path,ROOT/'scripts/recompute_t03_r032_original_seed.py']
    for review in read(review_path)['reviews']:
        image=ROOT/review['evidence']['image_path'];assert sha(image)==review['evidence']['jpeg_sha256'];files.append(image)
    for p in files:
        digest=sha(p);target=OUT/'sources'/(digest+p.suffix)
        if target.exists():assert sha(target)==digest
        else:target.write_bytes(p.read_bytes())
        result['source_hashes'][target.relative_to(ROOT).as_posix()]=digest
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=OUT/('registry_'+digest[:12]+'.json');path.write_bytes(raw);load(path,digest)
    if args.activate:
        pointer=ROOT/'catalog/active_core100_critical_protocol.json';current=read(pointer)
        if current['registry_sha256']!=args.expected_active_sha256:raise ValueError('critical_pointer_changed_concurrently')
        (OUT/'PREVIOUS_POINTER.json').write_bytes(pointer.read_bytes())
        current.update(version=OUT.name,registry='../'+path.relative_to(ROOT).as_posix(),registry_sha256=digest,
                       scope='Author-approved T03 stage revision; all input media, prompts and earlier scores retained.')
        pointer.write_text(json.dumps(current,indent=2),encoding='utf8')
    lines=['# Core100临界点评测当前接入','',f"正式距离 {result['summary']['critical_rgb_distance_cases']}/100；Near参考 {result['summary']['admitted_near_cases']} 条。",'',
           '|场景|已接入|待完成|','|---|---:|---:|']
    for i in range(1,21):
        n=sum(primary(c)['rgb_distance_admitted']for c in result['cases']if c['scene_id']==f'T{i:02}');lines.append(f'|T{i:02}|{n}|{5-n}|')
    lines+=['','## 未完成项','']
    for c in result['cases']:
        if not primary(c)['rgb_distance_admitted']:lines.append('- '+c['clip_id']+'：'+str(c.get('distance_admission_pending_reason')or c.get('rgb_pending_reason')or primary(c)['rgb_blockers']))
    (OUT/'STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(active=args.activate,registry=path.as_posix(),sha256=digest,summary=result['summary']),ensure_ascii=False))


if __name__=='__main__':main()
