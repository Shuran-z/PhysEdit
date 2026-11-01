"""Bind Core100 to generation-time source IDs; never promote invented thresholds."""
import collections
import copy
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT=Path('review/original_contract_audit_20261023')
RES=Path('annotation_site/resources')
BASE=Path('review/annotation_event_contracts_20261023')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_csv(name,headers,rows):
    s=io.StringIO(newline='');w=csv.writer(s);w.writerow(headers);w.writerows(rows)
    data=('\ufeff'+s.getvalue()).encode();(ROOT/name).write_bytes(data);(RES/name).write_bytes(data)


def build():
    ROOT.mkdir(exist_ok=True)
    prior=json.loads((BASE/'event_contracts.json').read_text(encoding='utf-8'))
    headers=json.loads((BASE/'merged_source_headers.json').read_text(encoding='utf-8'))
    manifest_path=Path('review/formal3600_hf_20261023/formal_manifest.json')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    tasks=collections.defaultdict(list)
    for t in manifest['tasks']:tasks[t['clip_id']].append(t)
    audit=json.loads((RES/'core100_readiness.json').read_text(encoding='utf-8'))
    old_gaps={r['clip_id']:r for r in audit['rows']}
    recovery_path=RES/'recovered_event_definitions.json'
    recovered=json.loads(recovery_path.read_text(encoding='utf-8')) if recovery_path.exists() else {}
    recovery_report=json.loads((RES/'remaining50_recovery.json').read_text(encoding='utf-8')) if recovered else {'rows':[]}
    recovery_rows={r['clip_id']:r for r in recovery_report['rows']}
    # These sets certify a definition's provenance, never reference/boundary/pair admission.
    targets={
      'T01':['full_chain'],'T02':['C2_signal_displaced_0p05m'],
      'T05':['gate_passage'],'T06':['complete_required_contact_chain'],
      'T07':['motion_ge_1cm'],'T09':['upper_nonpulled_book_on_table_at_end'],
      'T10':['support_pen_displacement_reaches_source_threshold'],
      'T14':['passed_channel','terminal_contact_after_full_exit'],
      'T18':['upper_nonpulled_book_on_table_at_end']}
    observation_only={
      'T03':['book_contacts_upper_can','can_contacts_lower_phone','phone_leaves_lower_support'],
      'T04':['stack_book_can_1_contact','can_1_can_2_contact','can_2_mug_contact'],
      'T08':['lower_book_translation','upper_book_translation','lower_book_mug_contact'],
      'T11':['driver_pencil_case_contact','pencil_case_eyeglasses_case_contact'],
      'T12':['stapler_contacts_tissue_box','tissue_box_moves_after_contact'],
      'T13':['driver_to_falling_book_contact','falling_book_to_drink_contact','drink_loses_original_support'],
      'T16':['folder_loses_original_support','folder_downstream_contact'],
      'T17':['can_tissue_box_contact','can_leaves_table'],
      'T19':['can_contact','can2_motion_after_contact'],
      'T20':['contact_book_can','contact_can_box','contact_box_cup']}
    provenance={
      'T01':'review/scene_family_completion_20261018/t01_current_sources/audit_t01_v2.py',
      'T02':'review/scene_family_completion_20261018/t02_original_auditor/audit_t02_v2_causal_gate.py',
      'T05':'review/scene_family_completion_20261018/original_completion_sources/audit_t05_v2.py',
      'T06':'scripts/register_t06_t10_replay_distances.py',
      'T07':'review/scene_family_completion_20261018/original_completion_sources/audit_t07_motion.py',
      'T09':'docs/critical_boundary/T09_COLLAPSE_THRESHOLD.md',
      'T10':'scripts/register_t06_t10_replay_distances.py',
      'T14':'review/scene_family_completion_20261018/t14_analyzer_source.py',
      'T15':'docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md',
      'T18':'docs/critical_boundary/T18_TABLE_CONTACT_PROTOCOL.md'}
    pending={
      'T03':'原配置因果图已匹配；缺同源版本的临界目标二分类提取合同（A/C族分别登记）',
      'T04':'实际配置为V4；所恢复数值审计器为V3，缺同版本规则绑定',
      'T08':'实际V4配置事件图已匹配；8cm判据未找到可核实的同版本原始定义',
      'T11':'实际R011配置已匹配；-0.20m规则来自旧版探针，缺R011正式提取合同',
      'T12':'实际R002原合同未声明1cm阈值；缺原R002运动分支提取合同',
      'T13':'实际F5源头按已知条件头哈希定位；缺F5临界二分类合同，不采用BG版本或新增1cm/5cm',
      'T16':'原配置事件序列已匹配；缺同版本临界目标及二分类提取合同',
      'T17':'原配置事件与结果类别已匹配；缺临界目标和精确二分类提取合同',
      'T19':'生成条件为旧Genesis双罐；缺此版本临界合同，不采用后来的Isaac参考',
      'T20':'原配置三段接触链已匹配；缺同版本临界目标和完整传播判据'}
    catalog={};records=[];removed=[];template=[]
    for clip,old in prior['clips'].items():
        scene=clip[:3];h=headers[clip];ts=tasks[clip]
        source_ids={t['source']['generation_metadata']['source_video_id'] for t in ts}
        if len(source_ids)!=1 or re.sub(r'__cam\d+$','',re.sub(r'^(genesis|isaac)__','',next(iter(source_ids))))!=h['sample_id']:raise ValueError('Exact source-ID conflict '+clip)
        if len(ts)!=36:raise ValueError('Not 36 actual generated videos '+clip)
        p=copy.deepcopy(old);events=copy.deepcopy(p['events']);excluded={}
        for key,d in list(events.items()):
            added='benchmark_observation_v2' in str(d.get('criterion_origin','')) or (scene=='T12' and key=='tissue_box_max_displacement_ge_1cm') or (scene=='T13' and key in ('t13_drink_box_motion_ge_1cm','drink_drop_ge_5cm'))
            unbound=(scene in ('T04','T08','T11') and bool(d.get('metric_rule')))
            if added or unbound:
                why='助手额外添加，删除活动阈值' if added else pending[scene]
                excluded[key]={'definition':d,'reason':why,'formal_scoring_allowed':False}
                removed.append([clip,key,why,json.dumps(d.get('metric_rule'),ensure_ascii=False)])
                del events[key]
        # Any composite depending on a removed or unverified numerical rule is also quarantined.
        for key,d in list(events.items()):
            if any(k not in events for k in d.get('derived_from',{}).get('all',[])):
                excluded[key]={'definition':d,'reason':'依赖被撤下或未核实的数值判据','formal_scoring_allowed':False};del events[key]
        score=list(targets.get(scene,[]))
        if scene=='T07' and ('cf_B_' in h['sample_id'] or h.get('experiment',{}).get('family_id')=='B_initial_longitudinal_position_m'):
            score=['phone_table_contact_after_release']
        if scene=='T15':
            if 'cfB_' in h['sample_id']:score=['laptop_contacts_phone']
            else:
                key='laptop_reaches_original_fall_criterion'
                events[key]={'name':'笔记本达到原跌落判据','definition_zh':'原笔记本质心曾低于原世界坐标z=-0.15m；不能用失去支撑或落地替代。',
                  'definition':'The original closed laptop center reaches world z strictly below -0.15 m at some time in the observation window, as defined by the original T15 V11 protocol. Support loss or floor contact alone is not this event.',
                  'minimum_evidence_times':1,'applicable':True,'actors':['t15v4_closed_laptop'],
                  'metric_rule':{'clauses':[{'quantity':'laptop_min_center_world_z_m','operator':'<','threshold':-.15,'unit':'m'}],'combine':'all','unit':'m'},
                  'original_reference_alias':'laptop_falls_to_floor'}
                score=[key]
        if clip in recovered:
            restored=recovered[clip]
            events.update(copy.deepcopy(restored['events']))
            # Recovered original definitions supersede their prior quarantine;
            # historical exclusions remain in excluded_thresholds.csv.
            for key in restored['events']:excluded.pop(key,None)
            score=list(restored['events'])
            provenance[scene]=restored['source']
        main=score or observation_only[scene]
        # Observe source conjunctions directly; do not force nine redundant inputs or invented timestamps.
        for key in main:
            if events[key].get('derived_from'):
                events[key]['source_conjunction']=events[key].pop('derived_from')
                events[key]['direct_observation_of_source_conjunction']=True
        main_set=set(main)
        # T01 full_chain needs its genuine numerical definition, kept inside the compound contract.
        if scene=='T01':events['full_chain']['component_definitions']={k:events[k] for k in events['full_chain']['source_conjunction']['all']}
        if scene=='T06':events['complete_required_contact_chain']['required_contact_pairs']=h['experiment']['required_contact_pairs']
        if scene=='T14':events['terminal_contact_after_full_exit']['component_definitions']={k:events[k] for k in ['passed_channel','contacted_eraser']}
        active={k:events[k] for k in main}
        short_names={'full_chain':'第2罐接触杯子且杯子末态位移超过3厘米','complete_required_contact_chain':'全部相邻书本的接触链完成','laptop_reaches_original_fall_criterion':'笔记本达到原跌落判据（质心z < -0.15m）'}
        for key,d in active.items():
            if key in short_names:d['name']=short_names[key]
        auxiliary={k:{**d,'role':'auxiliary','formal_scoring_allowed':False} for k,d in events.items() if k not in main_set}
        for k,d in active.items():
            d['role']='original_protocol_target' if k in score else 'source_observation_pending_protocol'
            d['formal_scoring_allowed']=k in score
            d['prompt_definition_source']='original_source_configuration_and_registered_protocol; never inferred from generated video'
        source_file=provenance.get(scene)
        proof={'source_video_id':next(iter(source_ids)),'source_sample_id':h['sample_id'],'source_config_path':h['path'],
          'source_config_sha256':h['sha256'],'source_binding_kind':h.get('source_role'),'exact_source_id_match':True,
          'protocol_source':source_file,'protocol_source_sha256':sha(source_file) if source_file else None,
          'reference_admission':'pending','vlm_defines_events':False}
        p.update(version=('core100-original-contracts-v3.2-' if clip in recovered else 'core100-original-contracts-v3.0-')+clip,status='frozen',freeze_scope='source_event_definitions_only',
          events=active,auxiliary_events=auxiliary,excluded_events=excluded,formal_score_event_ids=score,critical_targets=score,
          critical_contract_status='original_definition_reference_pending' if score else 'original_critical_target_pending',
          original_contract_audit=proof,required_order=[],notes=[],annotation_policy_zh='判断质量与事件是否发生；无法判断选不可判。',
          scoring_blockers=[] if score else [pending[scene]],
          formal_scoring_admission='requires_original_reference_window_boundary_and_pair_registrations')
        p['target']=old['target'].split('。')[0]+'。'
        p['actors']=[a for a in p.get('actors',[]) if any(a['id'] in d.get('actors',[]) for d in active.values())]
        catalog[clip]=p
        prompt_records=[{'task_id':t['id'],'model':t['model'],'seed':t['seed'],'prompt_variant':t['prompt_variant'],
          'prompt_sha256':hashlib.sha256(t['source']['generation_metadata']['prompt'].encode()).hexdigest(),
          'condition_frame_index':t['source']['generation_metadata'].get('condition_frame_index'),'native_prompt_truncation':t['source']['generation_metadata'].get('native_prompt_truncation'),
          'source_video_id':t['source']['generation_metadata']['source_video_id']} for t in ts]
        gap=old_gaps[clip]
        record={'clip_id':clip,**proof,'prompt_records':prompt_records,'formal_score_event_ids':score,'observation_event_ids':list(active),
          'auxiliary_event_ids':list(auxiliary),'excluded_event_ids':list(excluded),'protocol_gaps':p['scoring_blockers'],
          'reference_gaps':gap.get('reference_blockers',[]),'boundary_gaps':gap.get('boundary_blockers',[]),
          'pair_gaps':gap.get('pair_registration_blockers',[]),'window_gap':gap.get('window_alignment'),
          'NearAcc_eligible':False,'PairAcc_eligible':False}
        record['prompt_input_gaps']=['需核验原生截断后关键干预参数是否保留：'+','.join(sorted({r['model'] for r in prompt_records if r['native_prompt_truncation']}))] if any(r['native_prompt_truncation'] for r in prompt_records) else []
        record['source_material_status']=h.get('status')
        record['conditioning_frame_indices']=sorted({x['condition_frame_index'] for x in prompt_records if x['condition_frame_index'] is not None})
        record['generated_windows_s']=sorted({t['window_s'] for t in ts})
        record['measurement_gaps']=['生成视频原单位坐标与标定未登记'] if any(d.get('metric_rule') or any(x.get('metric_rule') for x in d.get('component_definitions',{}).values()) for d in active.values()) else []
        if clip in recovery_rows:
            rr=recovery_rows[clip]
            record['source_recovery']={k:rr[k] for k in ['source_state_sha256','contract_recovered','state_binding_notes','source_spec_differences','published_reference_binding','missing','reference_admission']}
            record['reference_gaps']=list(dict.fromkeys(record['reference_gaps']+rr['state_binding_notes']))
            if not score:
                p['scoring_blockers']=rr['missing'];record['protocol_gaps']=rr['missing']
            gap['source_recovery']=record['source_recovery']
        if len(record['generated_windows_s'])>1:record['window_gap']='各模型观察窗不同，需登记共同对比时域；'+str(record['generated_windows_s'])
        records.append(record)
        gap['original_protocol_gaps']=p['scoring_blockers']
        gap['formal_score_event_ids']=score
        gap['observation_protocol_version']=p['version']
        gap['event_fields']=len(active)
        if score:
            for field in ['near_blockers','pair_blockers']:
                gap[field]=[x for x in gap[field] if x!='original_critical_target_pending']
        if not score:
            for field in ['near_blockers','pair_blockers']:
                if 'original_critical_target_pending' not in gap[field]:gap[field].append('original_critical_target_pending')
        for scope,group in [('main',active),('auxiliary_optional',auxiliary)]:
            for k,d in group.items():template.append([clip,p['version'],scope,k,d['name'],k in score,'','',''])
    summary={'fixed_cases':100,'generated_videos_bound':3600,'exact_source_id_matches':100,
      'cases_with_source_backed_score_definition':sum(bool(r['formal_score_event_ids']) for r in records),
      'cases_with_critical_target_pending':sum(not r['formal_score_event_ids'] for r in records),
      'main_observation_fields':sum(len(p['events']) for p in catalog.values()),
      'auxiliary_fields':sum(len(p['auxiliary_events']) for p in catalog.values()),'excluded_fields':sum(len(p['excluded_events']) for p in catalog.values()),'excluded_threshold_fields':len(removed),'assistant_added_threshold_fields':sum('助手额外' in r[2] for r in removed),
      'native_truncation_input_videos':sum(bool(t['source']['generation_metadata'].get('native_prompt_truncation')) for t in manifest['tasks']),'NearAcc_eligible':0,'PairAcc_eligible':0,'reference_admission_granted':False}
    result={'schema':'core100-original-contract-audit-v1','manifest_sha256':sha(manifest_path),'summary':summary,'rows':records}
    (ROOT/'original_contract_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (RES/'original_contract_audit.json').write_bytes((ROOT/'original_contract_audit.json').read_bytes())
    audit['summary'].update(source_backed_score_definitions=summary['cases_with_source_backed_score_definition'],source_protocol_pending=summary['cases_with_critical_target_pending'])
    if recovered:audit['summary']['remaining50_recovery']=recovery_report['summary']
    audit['reason_guide']['original_critical_target_pending']='缺对应原配置版本的临界评分目标或提取合同'
    (RES/'core100_readiness.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    new={'schema':'phy2-core100-original-contracts-v3','version':'core100-original-contracts-v3.2',
      'policy_zh':'按生成时原配置及已登记协议判断；VLM不定义事件。人工只判断质量和事件标签。',
      'human_review_policy':{'version':'label-review-v3','manual_timestamps':False,'manual_rationale':False},
      'clips':catalog,'summary':summary}
    (RES/'event_contracts.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'event_contracts.json').write_bytes((RES/'event_contracts.json').read_bytes())
    write_csv('original_contract_audit.csv',['clip_id','source_video_id','config_path','config_sha256','protocol_source','source_material_status','source_binding_kind','formal_score_events','observation_events','auxiliary_events','excluded_events','protocol_gaps','reference_gaps','boundary_gaps','pair_gaps','window_gap','conditioning_frame_indices','generated_windows_s','measurement_gaps','prompt_input_gaps'],
      [[r['clip_id'],r['source_video_id'],r['source_config_path'],r['source_config_sha256'],r['protocol_source'],r['source_material_status'],r['source_binding_kind'],';'.join(r['formal_score_event_ids']),';'.join(r['observation_event_ids']),';'.join(r['auxiliary_event_ids']),';'.join(r['excluded_event_ids']),';'.join(r['protocol_gaps']),';'.join(r['reference_gaps']),';'.join(r['boundary_gaps']),';'.join(r['pair_gaps']),r['window_gap'],json.dumps(r['conditioning_frame_indices']),json.dumps(r['generated_windows_s']),';'.join(r['measurement_gaps']),';'.join(r['prompt_input_gaps'])] for r in records])
    write_csv('excluded_thresholds.csv',['clip_id','event_id','reason','old_rule_json'],removed)
    write_csv('event_annotation_template.csv',['clip_id','protocol_version','scope','event_id','event_name','source_backed_score_definition','task_id','quality','event_label'],template)
    text='# 原配置与临界协议逐条核对\n\n'+json.dumps(summary,ensure_ascii=False)+'\n\n100条均按生成清单中的source_video_id精确对应；不是按VLM结果定义事件。\n\n补查50条：原状态50条已找齐，T03/T04/T08/T11/T16/T17/T19/T20共40条恢复原始结果提取定义；T16/T17/T19/T20的20条重算结果与原生产QA逐条一致。T08 V4生产worker明确调用analyze_t08_v3_metrics.py，8cm确为原规则；T04使用独立V4审计器。T08的v6参考视频与同目录状态LFS哈希已全部核对，旧候选配置不代表实际发布规格。逐条参考结果和剩余10条缺项见remaining50_recovery.csv。\n\nT12新增1cm及T13新增1cm/5cm仍禁止进入正式评分。T11 R011正式放行记录与可参数化原提取脚本已核对，恢复末帧z < -0.10m；不借用R009的-0.20m；T13 F5的1cm起始检测不是跌落定义。T15区分原z=-0.15m跌落判据与失去支撑。\n\n有原始定义和原状态结果不等于参考准入。缺协议、参考、边界、配对与共同观察窗分别见original_contract_audit.csv；NearAcc/PairAcc尚未准入。辅助项单列且不进入正式评分。\n'
    (ROOT/'ORIGINAL_CONTRACT_AUDIT.md').write_text(text,encoding='utf-8')
    (RES/'ORIGINAL_CONTRACT_AUDIT.md').write_text(text,encoding='utf-8')
    for name in ['EVENT_ANNOTATION_GUIDE.md','CORE100_READINESS.md']:
        (RES/name).write_text(text+'\n人工只选择质量、发生/未发生/不可判；辅助项可选，原始数值判据未测量时不能自动计为正式成绩。详细事件表在网站事件口径页，原始配置与缺项见original_contract_audit.csv。\n',encoding='utf-8')
    for name in ['event_registration_gaps.csv','core100_readiness.csv']:(RES/name).write_bytes((RES/'original_contract_audit.csv').read_bytes())
    return summary


if __name__=='__main__':print(json.dumps(build()))
