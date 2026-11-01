"""Produce a keyed, evidence-bound 100-case readiness list, without scoring gaps."""
import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_resolution_20261027'
RES=ROOT/'annotation_site/resources'
sys.path.insert(0,str(ROOT/'annotation_site'))
from input_contract import matches_frozen_input
from workflow import final_annotation
from protocol_rules import has_numeric_rule
from scoped_critical import calculate_scoped


def read(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw)if path.suffix=='.gz'else raw)


def main():
    admission=read(RES/'core100_admission.json')
    definitions=read(RES/'core100_contact_protocol_20261027.json')['clips']
    contact_truth={r['clip_id']:r for r in read(RES/'core100_contact_reference_truth_20261027.json')['references']}
    admitted=read(RES/'reference_window_admission.json')
    admitted_refs={r['clip_id']:r for r in admitted['references']}
    windows=read(RES/'core100_physical_windows_20261027.json')['cases']
    clock={r['clip_id']:r for r in read(ROOT/'review/reference_admission_20261024/clock100_metadata_audit.json')}
    policy=read(RES/'core100_final_input_policy.json')
    manifest=read(WORK/'formal_seed0_v6_manifest.json')
    tasks=read(WORK/'continuation_site_snapshot.json.gz')
    scoped=calculate_scoped(tasks)
    publishable_models=[m['model']for m in scoped['per_model']if m['NearAcc']is not None or m['PairAcc']is not None]
    inputs=collections.defaultdict(list);site=collections.defaultdict(list)
    for row in manifest['tasks']:inputs[row['clip_id']].append(row)
    for task in tasks:site[task['payload']['clip_id']].append(task)
    contact_records=read(RES/'core100_contact_boundaries_20261027.json')['records']
    t13=read(RES/'core100_t13_contact_boundaries_20261027.json')
    contact_records+=t13['records']
    new_numeric=collections.defaultdict(list)
    for row in contact_records:new_numeric[row['clip_id']].append(row)
    c05_path=WORK/'t16_C05_verified_boundary.json'
    c05=read(c05_path)if c05_path.exists()else None
    records=[]
    for point in sorted(admission['points'],key=lambda r:r['clip_id']):
        clip=point['clip_id'];own=site[clip];slots=inputs[clip];definition=definitions[clip]
        source_ready=clip in admitted_refs
        horizon=admitted_refs[clip]['horizon_s']if source_ready else windows[clip]['required_horizon_s']if clip in windows else 5.
        horizon_status='已准入参考窗'if source_ready else'4.1秒物理窗已修复'if clip in windows else'新接触协议已登记5秒'if clip in contact_truth else'5秒候选窗，参考事件/边界仍需同窗核验'
        numeric=new_numeric[clip]
        old_numeric=point['numerical_distance_records']
        numeric_status='已核验新接触边界'if numeric else'已有历史数值记录，同窗准入待核验'if old_numeric else'尚无同事件可用边界，先核验指标适用性'
        bins=sorted({r['distance_bin']for r in numeric})
        c05_valid=clip=='T16_C05'and c05 and c05['all_probe_hashes_valid']and c05['source_trajectory_reproduced_1mm']
        if c05_valid:
            interval=c05['intervals'][0]['bracket'];theta=84.82758620689656
            lower=(theta-interval[1])/25.;upper=(theta-interval[0])/25.
            numeric=[dict(target_event='folder_downstream_contact',bracket=interval,horizon_s=5.,normalized_distance_interval=[lower,upper],distance_bin='near',reference_admitted=False,pair_admitted=False)]
            bins=['near'];numeric_status='原版5秒边界及轨迹已核验，但原参考物理质量未过关；独立修复候选同样未过关，不准入'
        if clip=='T16_C04':
            numeric_status='原参考5秒接触真值已提取；正事件复现前缀通过1毫米门槛，但新版上下文边界重算未通过接触深度质量检查';bins=[]
        if source_ready:near_status='参考Near资格已准入，模型输入/覆盖/人审另核验'
        elif 'near'in bins:near_status='Near数值候选，尚未正式准入'
        elif bins:near_status='当前已测为'+','.join(bins)+'；不作为Near样本'
        elif old_numeric and all(r['bin']in('far','mid')for r in old_numeric):near_status='历史记录为非Near；新观察窗资格待核验'
        else:near_status='未准入；需同目标、同版本、同窗边界证据'
        pair_status='参考配对已准入；输出配对覆盖/人审待核验'if source_ready else'原C04/C05候选对拒绝：几何、求解器及执行上下文不同'if clip in ('T16_C04','T16_C05')else'不适用：不属于已准入的跨界对；不强行为每条配对'
        candidates=[r for r in slots if r['exact_v6_available']and clip not in ('T16_C02','T16_C04')]
        live_eligible=[t for t in own if matches_frozen_input(t['payload'],policy)]
        human_bound=[];recheck=[]
        for task in own:
            p=task['payload'];human=final_annotation(task)
            if human and (abs(p['window_s']-horizon)>1e-6 or human.get('protocol_sha256')!=p['protocol_sha256']):recheck.append(task['id'])
            if human and matches_frozen_input(p,policy)and p['duration_s']+1e-6>=horizon and abs(p['window_s']-horizon)<1e-6 and human.get('video_sha256')==p['video_sha256']and human.get('protocol_sha256')==p['protocol_sha256']:
                human_bound.append(task['id'])
        model_coverage={}
        for model in sorted({r['model']for r in slots}):
            m=[r for r in slots if r['model']==model]
            covers=all(r['native_frames']is not None and r['native_fps']and (r['native_frames']-1)/r['native_fps']+1e-6>=horizon for r in m)
            model_coverage[model]=dict(native_covers=bool(covers),required_slots=len(m),available_v6_candidates=sum(r in candidates for r in m))
        numeric_events=[key for key,value in definition['events'].items()if has_numeric_rule(value)]
        missing=[]
        if clip.startswith('T19'):missing.append('作者已退役旧参考；须绑定合格替代参考，不能沿用旧参考成绩')
        if clip in ('T16_C02','T16_C04'):missing.append('生成条件图逐像素匹配旧版而非当前规范参考，且布局参数改变：36槽缺正确条件图版本')
        if clip=='T16_C04':missing.append('旧C04/C05边界不可继承；新版固定上下文求界已结束但物理质量检查失败，未形成准入边界')
        elif len(candidates)<36:missing.append(f'精确v6、seed 0正式视频仍缺{36-len(candidates)}槽（旧视频不删除、不冒充新输入）')
        if clip in ('T16_C01','T16_C03'):missing.append('原版保留；几何对照中选定点事件标签未变，但临界边界稳定性未证实，原参考接触深度超过1毫米质量门槛')
        if clip=='T16_C05':missing.append('原版保留；几何对照三项事件翻转，原版及独立修复候选均未通过物理质量检查，暂停正式临界评分')
        if not source_ready:missing.append('参考RGB、源状态/配置与当前目标及观察窗的正式准入')
        if clip not in admitted_refs and clip not in windows and clip not in contact_truth:missing.append('5秒窗下重新核验源事件真值及边界；不能直接继承更长原窗末态')
        if not clock[clip].get('clock_evidence_complete'):missing.append('原物理时钟/条件帧对应证据')
        if not numeric and clip!='T16_C04':missing.append('缺同窗边界或适用性结论；不把所有样本强制当Near')
        if 'near'in bins and not source_ready:missing.append('Near参考准入；单侧样本不能单独声称已完成平衡Near或Pair')
        if numeric_events:missing.append('生成视频数值标定：'+','.join(numeric_events))
        if recheck:missing.append(f'{len(recheck)}条已有最终记录需核对新窗口/协议（保留原标签）')
        missing.append('按正确视频、协议与原生窗口完成VLM预评和最终人工复核')
        source_event=windows[clip]['source_event']if clip in windows else contact_truth.get(clip)
        if source_ready:source_event=dict(target_event=admitted_refs[clip]['target_event'],reference_label=admitted_refs[clip]['reference_label'],horizon_s=horizon,reference_admission='admitted')
        conclusion='参考侧可评Near/Pair；生成侧尚未满足整组正式出分条件'if source_ready else'可按新窗口做事件观察；正式分数待参考/边界准入'if clip in windows else'可做新接触观察；Near候选准入另计'if clip in contact_truth else'正式输入/参考/同窗协议仍待补齐'
        if clip=='T16_C04':conclusion='须换正确条件视频并完成参考版本修复后正式评'
        if clip.startswith('T19'):conclusion='旧参考退役，正式评测暂缓'
        records.append(dict(clip_id=clip,source_sample_id=point['source_sample_id'],target_definition_ready=True,
                            event_annotation='可记录可见原对象事件；数值阈值项须标定，未知保留未知',
                            formal_status=conclusion,can_publish_whole_case_score_now=source_ready and bool(publishable_models),
                            publishable_admitted_cohort_models=publishable_models if source_ready else [],
                            required_horizon_s=horizon,window_status=horizon_status,
                            available_physical_reference_horizon_s=clock[clip].get('reference_available_horizon_s'),
                            expected_slots=36,available_exact_v6_seed0_candidates=len(candidates),
                            live_input_eligible_records=len(live_eligible),final_human_identity_window_input_bound_records=len(human_bound),
                            new_numerical_records=numeric,legacy_numerical_records=len(old_numeric),numerical_status=numeric_status,
                            NearAcc_status=near_status,PairAcc_status=pair_status,source_event_evidence=source_event,
                            numeric_calibration_events=numeric_events,model_coverage=model_coverage,
                            native_short_models=[m for m,v in model_coverage.items()if not v['native_covers']],
                            longer_or_changed_window_final_human_records=recheck,missing=missing,
                            reference_admitted=source_ready,reference_configuration_status=point.get('reference_configuration_status')))
    assert len(records)==100 and len({r['clip_id']for r in records})==100
    # The author's T19 replacement is an active reference version, not a
    # restoration of the retired five videos or their old model annotations.
    from physedit.core100_release import load as load_active_release
    from physedit.boundary import distance
    active_root,active_manifest,_,_=load_active_release(RES/'active_reference_release.json')
    active_answers={r['point_id']:r for r in map(json.loads,(active_root/'answers_t19.jsonl').read_text(encoding='utf8').splitlines())}
    active_cases={r['clip_id']:r for r in active_manifest['replacements']}
    for row in records:
        cid=row['clip_id']
        if cid not in active_cases:continue
        key=active_answers[cid];case=active_cases[cid];d=distance(key)
        row.update(reference_release_version=active_manifest['version'],source_sample_id=case['native_sample_id'],
            historical_source_sample_id=next(p['source_sample_id'] for p in admission['points'] if p['clip_id']==cid),
            historical_available_v6_candidates=row['available_exact_v6_seed0_candidates'],
            formal_status='新版参考已接入；须生成并标注对应新版输入',can_publish_whole_case_score_now=False,
            required_horizon_s=key['evaluation_horizon_s'],window_status='full_original_isaac_window_from_frame0',
            available_exact_v6_seed0_candidates=0,live_input_eligible_records=0,
            final_human_identity_window_input_bound_records=0,publishable_admitted_cohort_models=[],
            new_numerical_records=[dict(target_event=key['target_event'],theta=key['theta'],
                distance_bin=d['bin'],normalized_distance_interval=d['normalized_absolute_interval'])],
            numerical_status='原区间与参数已绑定' if cid!='T19_C05' else '同上下文右侧转变区间已绑定；距离跨mid/far，不强制分桶',
            NearAcc_status='参考可用；等待新版生成及事件标注' if d['bin']=='near' else '非Near',
            PairAcc_status='参考配对已绑定；共享/独立种子按运行方案分别报告' if key['pair_ids'] else '未配对，保留普通事件评分',
            source_event_evidence=dict(target_event=key['target_event'],reference_label=key['events'][key['target_event']],
                horizon_s=key['evaluation_horizon_s'],reference_admission=key['reference_admission']),
            reference_admitted=True,reference_configuration_status='hash_bound_isaac_source_config',
            numeric_calibration_events=[],model_coverage={},native_short_models=[],
            longer_or_changed_window_final_human_records=[],
            missing=['按新版条件图与三种短prompt生成模型输出','按新版事件协议与完整原生时域完成筛查和事件标注'])
    new_near=sum(distance(k)['bin']=='near' for k in active_answers.values())
    recovered_path=RES/'core100_recovered_numerical_bindings.json'
    if recovered_path.exists():
        for recovered in read(recovered_path)['records']:
            row=next(r for r in records if r['clip_id']==recovered['clip_id'])
            d=distance(recovered)
            row.update(new_numerical_records=[dict(target_event=recovered['canonical_event'],theta=recovered['theta'],
                boundary_interval=recovered['original_boundary_interval'],distance_bin=d['bin'],
                normalized_distance_interval=d['normalized_absolute_interval'])],
                numerical_status='同源Isaac固定种子补算已回收并接入；旧跨引擎数值保留为被替代记录',
                NearAcc_status='当前为mid，不计Near；普通事件与参考准入另核验',
                recovered_numerical_binding=recovered)
    sources=[RES/'core100_admission.json',RES/'core100_contact_protocol_20261027.json',RES/'core100_contact_reference_truth_20261027.json',
             RES/'reference_window_admission.json',RES/'core100_final_input_policy.json',RES/'core100_physical_windows_20261027.json',
             RES/'core100_contact_boundaries_20261027.json',RES/'core100_t13_contact_boundaries_20261027.json',
             WORK/'formal_seed0_v6_manifest.json',WORK/'continuation_site_snapshot.json.gz',
             ROOT/'catalog/active_core100_conditions.json',active_root/'MANIFEST.json']
    out=ROOT/'docs/critical_boundary/CORE100_READINESS_20261027.json'
    result=dict(schema='core100-per-case-readiness-v1',generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                summary=dict(cases=100,target_definitions=100,repaired_physical_windows=len(windows),
                             admitted_near_reference_cases=len(admitted_refs)+new_near,admitted_pairs=len(admitted['pairs'])+len(active_manifest['pairs']),
                             active_reference_release=active_manifest['version'],T19_reference_replacements=5,
                             T12_completed_cases=read(RES/'core100_contact_boundaries_20261027.json')['completed'],
                             T13_completed_cases=t13['completed_cases'],available_upstream_v6_seed0_candidates=sum(r['available_exact_v6_seed0_candidates']for r in records)),
                notes=['可标注不等于可报正式分；正式参考、边界、配对和生成侧证据分别核验。',
                       '正式输入候选数量不证明条件图/参考几何全部准入；已知错误的T16_C04已剔除。',
                       '非Near或未成对样本不强行补成Near/Pair；不适用与尚未完成分开。',
                       '短原生时域、不明标签和争议不填零；旧版本记录保留。'],
                evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources},cases=records)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Core100逐条评测准备清单','',f"更新时间（UTC）：{result['generated_at_utc']}",'',
           '**“能开始标注观察”与“能报告正式成绩”分开。当前没有证据支持100条整体NearAcc/PairAcc已完成。**',
           '',f"目标定义100/100；T19已替换接入5条，其中4条Near、2组配对。合计已准入Near参考{result['summary']['admitted_near_reference_cases']}条、配对{result['summary']['admitted_pairs']}组；生成侧成绩另计。",'',
           '其余95条沿用冻结v6输入，T19采用独立新版输入，旧生成结果不继承。下表“上游候选”保留原字段口径；新版T19在新模型输出到齐前计0。配对按独立种子或共享种子分别报告。完整版本和逐项证据见JSON。',
           '', '| 样本 | 物理观察窗 | 上游候选/36 | 能否评及指标状态 | 还缺什么 |','|---|---|---:|---|---|']
    for r in records:
        numeric='；'.join(f"{x['target_event']}={x['distance_bin']}"for x in r['new_numerical_records'])
        status=r['formal_status']+'；'+r['numerical_status']
        if numeric:status+='；'+numeric
        status+='；Near：'+r['NearAcc_status']+'；Pair：'+r['PairAcc_status']
        missing='；'.join(r['missing'])
        if r['native_short_models']:missing+='；时长不足模型：'+','.join(r['native_short_models'])
        lines.append(f"| {r['clip_id']} | {r['required_horizon_s']:g}s（{r['window_status']}） | {r['available_exact_v6_seed0_candidates']} | {status.replace('|','/')} | {missing.replace('|','/')} |")
    lines+=['','逐条结构化证据：[CORE100_READINESS_20261027.json](CORE100_READINESS_20261027.json)。',
            '','100个案例槽位保留，T19的5条参考按作者授权更换并独立版本化；旧输入、生成结果与标注保留。参考接入不等于模型成绩完成。']
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(result['summary']))


if __name__=='__main__':main()
