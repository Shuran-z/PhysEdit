"""Publish a local reviewable entry only after both complete verification gates pass."""
from pathlib import Path
import collections,gzip,hashlib,itertools,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.full_prompt_config_audit import equal
BASE=ROOT/'review/full_prompt_audit_20261102';OUT=BASE/'audited_release'

def rows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:yield from map(json.loads,f)

def main():
    verified=json.loads((OUT/'INDEPENDENT_VERIFICATION.json').read_text())
    train=json.loads((OUT/'TRAIN_BINDING_VERIFICATION.json').read_text())
    assert verified['status']==train['status']=='passed' and verified['issues']==0
    assert verified['new_manifest_sha256']==hashlib.sha256((OUT/'videos.jsonl.gz').read_bytes()).hexdigest()
    units=json.loads((OUT/'UNIT_REPORT.json').read_text());phase=json.loads((BASE/'repaired/REPORT.json').read_text());final=json.loads((BASE/'final/FINALIZATION_REPORT.json').read_text())
    baseline=ROOT/'review/prompt_revision_20261102/backup/original_72000.jsonl.gz'
    stats=collections.Counter();fields=collections.Counter();samples={};textpool_records=0
    with gzip.open(OUT/'BASELINE_PARAMETER_DIFFS.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst:
        for old,new in itertools.zip_longest(rows(baseline),rows(OUT/'videos.jsonl.gz')):
            assert old and new and old['canonical_video_id']==new['canonical_video_id']
            assert old['sha256']==new['sha256'] and old['split']==new['split'] and old['source_group_id']==new['source_group_id']
            before={f[0]:f for f in old['parameter_facts']};after={f[0]:f for f in new['parameter_facts']};assert set(before)==set(after)
            diff=[]
            for key,a in before.items():
                b=after[key]
                if not equal(a[-2],b[-2]):diff.append({'key':key,'old':a[-2],'new':b[-2],'kind':'numeric'});stats['numeric_fields_changed_vs_original']+=1;fields[key]+=1
                if a[-1]!=b[-1]:diff.append({'key':key,'old_unit':a[-1],'new_unit':b[-1],'kind':'unit'});stats['unit_fields_changed_vs_original']+=1
            if diff:
                dst.write(json.dumps({'video_id':new['canonical_video_id'],'changes':diff},ensure_ascii=False)+'\n');stats['parameter_rows_changed_vs_original']+=1
            if old['prompt_variants_en']!=new['prompt_variants_en']:stats['prompt_rows_changed_vs_original']+=1
            category='T10' if new['scene']=='T10' and any(d['kind']=='numeric' for d in diff) else 'Isaac T11' if new['engine']=='isaac' and new['scene']=='T11' else 'Isaac T15' if new['engine']=='isaac' and new['scene']=='T15' and diff else None
            if category and category not in samples:samples[category]={'video_id':new['canonical_video_id'],'old_prompt':old['prompt_variants_en'][0],'new_prompt':new['prompt_variants_en'][0],'field_changes':diff,'source':new['full_numeric_audit']['source']}
            assert new['full_numeric_audit']['status']=='verified' and not new['full_numeric_audit']['issues']
            stats['videos']+=1
    assert stats['videos']==72000
    files={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['videos.jsonl.gz','train_final_candidates.jsonl.gz','video_prompt_bindings.jsonl.gz','prompt_texts.jsonl.gz','INDEPENDENT_VERIFICATION.json','TRAIN_BINDING_VERIFICATION.json']}
    report={'version':'full-prompt-numeric-audit-20261102','status':'passed','scope':'current 72000-row revised simulation prompt catalog; immutable prior Core100 generation inputs are not rebound',
            'verification':verified,'training_export_verification':train,'changes_against_original_backup':dict(stats),'numeric_changed_keys':dict(fields),
            'new_changes_after_previous_T10_fix':phase['counts']['field_corrections'],'unit_repairs':units,
            'legacy_unbound_background_friction_clauses_removed_rows':final['unbound_background_friction_rows_fixed'],
            'kinematic_object_identity_rows_verified':final['kinematic_identity_rows_verified'],
            'duplicate_variant_rows_fixed':final['duplicate_variant_rows_fixed'],'examples':samples,'files':files,
            'published_or_active_training_changed':False,'independent_video_physics_measurement_claimed':False,'human_semantic_review_claimed':False}
    (OUT/'FULL_AUDIT_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# 全量提示词数值核验结果','',f"72,000条视频、216,000份prompt已全部完成来源对照和导出后复查；未解决字段、数值句和长度问题为0。",'',
        f"来源：{verified['counts']['config_hash_verified']:,}条配置哈希核验，{verified['counts']['original_metadata_verified']:,}条原始仿真元数据哈希核验；共{verified['counts']['field_checks']:,}项数值。",'',
        f"相比最初备份修正{stats['numeric_fields_changed_vs_original']:,}项数值、{stats['unit_fields_changed_vs_original']:,}处单位。本轮在上一版T10修复基础上新增972项数值修正。",'',
        '修正包括：T10速度/角度/位置、Isaac T11实际质量与固定时长施力、Isaac T15初始位置/速度；恢复系数采用Isaac实际运行时覆盖值；计数、帧数和布尔值不再使用力或冲量单位。', '',
        '9条记录中无配置依据的“背景摩擦为1”已移出prompt，原文保留在差异日志。T18抽书物体改用与配置一致的对象编号，1,143条已逐一核对；2,640条重复变体已修复。', '',
        '## 使用入口','',
        '- videos.jsonl.gz：完整72000条最新修订目录。',
        '- train_final_candidates.jsonl.gz：45357条原训练划分候选，已核对与完整目录的文本、参数、媒体及来源族绑定一致。',
        '- video_prompt_bindings.jsonl.gz / prompt_texts.jsonl.gz：216000个文本绑定及去重文本池。',
        '- INDEPENDENT_VERIFICATION.json：重新读取导出后的全量核验结果。',
        '- BASELINE_PARAMETER_DIFFS.jsonl.gz：相比最初原文备份的逐条数值与单位变化。', '',
        '本次只更新本地修订版本；没有切换在线发布、正在运行的训练或旧Core100实际生成输入。全部数值一致指对配置、运行时覆盖值和原始元数据一致，不代表另做了72000条视频的物理质量审核。','', '## 抽取对照','']
    for category,r in samples.items():
        lines += ['### '+category,'',r['video_id'],'','原文：','```text',r['old_prompt'],'```','','核验修订后：','```text',r['new_prompt'],'```','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf8')
    pointer={'status':'full_numeric_audit_passed','version':report['version'],'manifest':str((OUT/'videos.jsonl.gz').resolve()),'manifest_sha256':files['videos.jsonl.gz'],'training_candidates':str((OUT/'train_final_candidates.jsonl.gz').resolve()),'report':str((OUT/'FULL_AUDIT_REPORT.json').resolve()),'readme':str((OUT/'README.md').resolve()),'active_jobs_or_online_release_changed':False}
    for path in [ROOT/'review/prompt_revision_20261102/CONFIG_SPEED_RESOLUTION.json',ROOT/'review/t10_config_speed_resolution_20261102/FULL_CONFIG_ALIGNMENT.json',ROOT/'review/t10_config_alignment_20261102/FULL_AUDIT_SUCCESSOR.json',ROOT.parent/'prompts_72000_unified/CURRENT_AUDITED_PROMPTS.json']:
        path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['examples','files','verification']},ensure_ascii=True))

if __name__=='__main__':main()
