"""Review the 21 no-flip exclusions against original families and records.

No simulation is launched. A finite constant replay is not an applicability
proof. Original calibration values and measured intervals stay distinguishable.
"""
import copy
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_no_flip_reaudit_20261031'


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def build():
    baseline=read(WORK/'before_registry.json')
    cases={r['clip_id']:r for r in baseline['cases']if r['status']=='not_applicable_in_registered_scan'}
    assert len(cases)==21
    hits=read(WORK/'original_ledger_hits.json')
    t02={r['sample_id']:r for r in read(ROOT/'review/original_search_tasks_20261018/t02_original_family_bindings.json')}
    windows={r['clip_id']:r for r in read(ROOT/'review/core100_binding_20261028/t02_existing_window_recovery_20261030.json')['cases']}
    rows=[]
    for cid,old in cases.items():
        row=dict(clip_id=cid,sample_id=old['sample_id'],reference_video_sha256=old['reference_video_sha256'],
            previous_parameter=old['parameter'],previous_theta=old['theta'],previous_event_ids=list(old['reference_events']),
            previous_horizon_s=old['horizon_s'],review_status='original_binding_pending',
            no_flip_is_not_proof_of_inapplicability=True,original_records=[],evidence=[])
        if cid.startswith('T02'):
            original=t02[old['sample_id']]
            record=next(r for r in hits if r['core_clip_id']==cid and r.get('original_critical_value')is not None)
            assert record['videos']['cam01']['sha256']==old['reference_video_sha256']
            value=original['original_calibrated_star'];theta=original['theta'];span=record['normalization_span']
            row.update(review_status='original_calibration_value_recovered',reason_zh='原C族校准值存在；5秒截断使信号触发未被观察到。恢复原值距离，校准点不冒充精确物理阈值。',
                parameter=original['parameter_name'],theta=theta,horizon_s=205/30,condition_frame_index=4,end_frame_index=209,
                reference_events={'C2_signal_displaced_0p05m':windows[cid]['old_full_video_label']},
                original_calibration_reference=dict(value=value,reference_kind='original_calibrated_centre',
                    raw_absolute_distance=abs(theta-value),normalized_absolute_distance=abs(theta-value)/span,
                    normalization_span=span,calibration_report=original['calibration_report'],
                    calibration_report_sha256=original['calibration_report_sha256'],
                    calibrated_triplet=original['calibrated_triplet'],exact_physical_threshold_certified=False),
                evidence=['review/original_search_tasks_20261018/t02_original_family_bindings.json',
                    'review/core100_binding_20261028/t02_existing_window_recovery_20261030.json'])
        elif cid in ['T05_C04','T05_C05']:
            original=next(r for r in hits if r['core_clip_id']==cid and r.get('refinement_status')=='original_backend_conditional_interval')
            path=ROOT/'review/scene_family_completion_20261018/completion_states/T05'/(old['sample_id']+'.json.gz')
            packed=path.read_bytes();assert hashlib.sha256(packed).hexdigest()==original['reference_state_sha256']
            s=json.loads(gzip.decompress(packed));threshold=s['experiment']['geometry_contract']['phone_center_full_pass_x_m']
            first=next((f['frame_index']for f in s['frames'][5:]if next(o['position'][0]for o in f['objects']if o['name']=='t05v2_moving_phone')>=threshold),None)
            assert int(first is not None)==original['reference_label']
            row.update(review_status='original_interval_recovered',reason_zh='原gate_passage族和边界区间存在；正侧第173帧通过，被原5秒窗口截掉。',
                parameter='gap_ratio',theta=original['theta'],horizon_s=205/30,condition_frame_index=4,end_frame_index=209,
                reference_events={'gate_passage':int(first is not None)},first_event_frame=first,
                interval=original['original_boundary_interval'],endpoint_labels=[0,1],normalization_domain=original['normalization_domain'],
                normalization_span=original['normalization_span'],original_record=original,
                evidence=['review/scene_family_completion_20261018/original_value_distance_ledger/t04_t05_supplemental_sample_distances_refined.jsonl'])
        elif cid.startswith('T05'):
            path=ROOT/'review/scene_family_completion_20261018/completion_states/T05'/(old['sample_id']+'.json.gz')
            s=json.loads(gzip.decompress(path.read_bytes()));design=s['experiment']['formal_design']
            assert design['changed_variable']=='phone_tray_friction'
            row.update(review_status='original_axis_mismatch',parameter='phone_tray_friction_coefficient',
                theta=s['experiment']['parameter']['phone_tray_friction_coefficient'],original_design=design,
                reason_zh='原global_16改变phone_tray_friction，之前误统一按gap_ratio扫描；这不能判定原摩擦轴不适用。',
                evidence=['review/core100_no_flip_reaudit_20261031/t05_original_friction_readback.json'])
        elif cid.startswith('T11'):
            p=ROOT/'review/scene_family_completion_20261018/original_value_distance_ledger/t11_current_published_parameters.jsonl'
            original=next(r for r in (json.loads(l)for l in p.open(encoding='utf8'))if r['sample_id']==old['sample_id'])
            assert original['family_id']=='joint_global_configuration'
            row.update(review_status='joint_global_point_not_single_original_family',
                parameter='joint_global_configuration',theta=original['theta'],original_record=original,
                reason_zh='原G_global_06是速度、间距、边缘、质量联合点；之前只按速度坐标扫描，不能代表A/B/C/D四个原族。',
                evidence=['review/scene_family_completion_20261018/original_value_distance_ledger/t11_current_published_parameters.jsonl'])
        elif cid.startswith('T04'):
            row.update(review_status='original_family_event_alignment_pending',
                reason_zh='原support_release速度族有0.1/0.15/0.2三分支；此前用末端full_chain不翻转判断整族不适用，原支撑释放判据尚需对齐。',
                original_sampling_triplet=[.1,.15,.2],recorded_sampling_centre=.15,
                evidence=['review/scene_family_completion_20261018/original_completion_sources/audit_t04_v4_quality.py'])
        elif cid=='T03_C02':
            original=next(r for r in hits if r['core_clip_id']==cid and r.get('original_rendering_star')is not None)
            row.update(review_status='rendering_centre_not_solved_threshold',original_records=[original],
                reason_zh='已找回原C族采样中心0.035；当前是global_C_05、r032发布样本。保留中心，但不能把它自动当作此固定上下文的求解阈值。')
        elif cid=='T03_C03':
            row.update(review_status='original_release_search_binding_pending',
                reason_zh='原r014的global_C_05与原C族有关；已有新有限网格不翻转，但尚未绑定该发布版本的原搜索值，不能判不适用。')
        elif cid.startswith('T06'):
            row.update(review_status='original_gap_family_search_binding_pending',
                reason_zh='当前是Genesis gap族；旧台账中已恢复的impact_force/J族边界不能移植到gap。有限gap扫描不翻转不等于原值不存在。')
        elif cid=='T09_C01':
            row.update(review_status='original_event_definition_alignment_pending',
                reason_zh='此前使用末帧仍接触桌面，原要求是散塌后曾接触桌面；已重读现有8点曾接触标签，均0，但仍不能据此认定不适用。',
                evidence=['review/core100_no_flip_reaudit_20261031/t09_ever_contact_readback.json'])
        elif cid.startswith('T10'):
            row.update(review_status='original_support_family_search_binding_pending',
                reason_zh='原support_x族身份已确定；现有旧边界主要对应地球条件，不能套到月球/火星。仍需同重力、同事件原搜索记录。')
        elif cid=='T14_C03':
            row.update(review_status='joint_global_point_not_single_original_family',
                reason_zh='原G_global_07是间隙、姿态、进入速度联合覆盖；不能用一次固定姿态的A轴CPU扫描证明原A/B/C族都不适用。',
                evidence=['review/original_search_tasks_20261018/t14_original_family_bindings.json'])
        elif cid=='T20_C01':
            original=[r for r in hits if r['core_clip_id']==cid and r.get('original_boundary_interval')]
            row.update(review_status='original_event_definition_alignment_pending',original_records=original,
                reason_zh='已有同来源局部接触区间，但标签是book-can末态接触；当前族为box_cup_gap、扫描目标为完整传播。二者不能混用，也不能据完整传播不变否定原局部边界。')
        else:raise AssertionError(cid)
        assert row.get('reason_zh')
        rows.append(row)
    result=dict(schema='core100-original-no-flip-review-v1',cases=rows,reviewed_cases=21,
        original_intervals_recovered=2,original_calibration_values_recovered=2,
        original_binding_pending=17,confirmed_not_applicable=0,new_simulations_started=0)
    (WORK/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Core100原21条“不适用”复核','',
        '原21条统一不适用结论撤回：有限扫描无翻转不能代替原参数族、原事件和原观察窗核对。',
        '已恢复2条原边界区间、2条原校准值；17条保留待对齐，不宣称原临界值不存在。未启动新仿真。','',
        '| 案例 | 复核结论 |','|---|---|']
    lines += [f"| {r['clip_id']} | {r['reason_zh']} |"for r in rows]
    (ROOT/'docs/critical_boundary/CORE100_ORIGINAL_REFERENCE_REAUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k!='cases'}))


def apply_review(cases,review):
    for proof in review['cases']:
        r=cases[proof['clip_id']]
        assert r['reference_video_sha256']==proof['reference_video_sha256']and r['sample_id']==proof['sample_id']
        r['previous_no_flip_binding']=copy.deepcopy(r)
        r['original_reference_review']=proof
        r['boundary_records']=[]
        r.update(status='incomplete',reason=proof['reason_zh'])
        if proof['review_status']=='original_calibration_value_recovered':
            r.update(status='distance_ready',binding_kind='original_recorded_calibration',
                parameter=proof['parameter'],theta=proof['theta'],horizon_s=proof['horizon_s'],end_frame_index=209,
                reference_events=proof['reference_events'],original_calibration_reference=proof['original_calibration_reference'])
        elif proof['review_status']=='original_interval_recovered':
            from physedit.core100_bindings import interval_distance
            r.update(status='distance_ready',binding_kind='original_interval_recovered',
                parameter=proof['parameter'],theta=proof['theta'],horizon_s=proof['horizon_s'],end_frame_index=209,
                reference_events=proof['reference_events'],normalization_domain=proof['normalization_domain'],
                normalization_span=proof['normalization_span'])
            r['boundary_records']=[dict(event='gate_passage',bracket=proof['interval'],endpoint_labels=[0,1],
                distance=interval_distance(r['theta'],proof['interval'],r['normalization_span']),
                interval_kind='original_backend_conditional_interval',exact_theta_star=None)]
        elif proof['review_status']=='original_axis_mismatch':
            r.update(parameter=proof['parameter'],theta=proof['theta'],normalization_domain=None,normalization_span=None)
        elif proof['clip_id'].startswith('T11'):
            r.update(parameter=proof['parameter'],theta=proof['theta'],normalization_domain=None,normalization_span=None)
        r['evidence'].append(dict(file='review/core100_no_flip_reaudit_20261031/review.json',detail=proof['review_status']))


if __name__=='__main__':build()
