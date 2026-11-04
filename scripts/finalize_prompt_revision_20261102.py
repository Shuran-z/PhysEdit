from pathlib import Path
import sys,json,gzip,hashlib,shutil,zipfile,collections,math,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'review/prompt_revision_20261102';OLD=ROOT/'review/prompt_revision_20261101'
from physedit.compact_prompt import MODEL_BUDGETS
from scripts import verify_prompt_revision as verifier

def main():
    (OUT/'backup').mkdir(exist_ok=True)
    for name in ['backup/Core100_original.json','backup/original_72000.jsonl.gz','Core100_revised.json','Core100完整对照.md','CORE100_REPORT.json','三组完整对照.md']:
        shutil.copyfile(OLD/name,OUT/name)
    verifier.BASE=OUT;verifier.main()
    stats=collections.Counter();issues=collections.Counter();bindings=collections.Counter();max_tokens=collections.Counter()
    source=ROOT/'review/prompt_rewrite_release_20261101/source/videos.jsonl.gz'
    with gzip.open(source,'rt',encoding='utf8') as old,gzip.open(OUT/'revised_72000.jsonl.gz','rt',encoding='utf8') as new,gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst:
        for a,b in zip(old,new):
            r,n=json.loads(a),json.loads(b);assert r['canonical_video_id']==n['video_id']
            initial=hashlib.sha256(json.dumps({k:r.get(k) for k in ['canonical_video_id','sha256','download','split','source_group_id','parameter_facts']},sort_keys=True).encode()).hexdigest()
            r['prompt_revision']={k:n[k] for k in ['status','issues','original_prompt_variant_sha256','moved_to_metadata','changes','control_keys','source_control_clauses','primary_input_metadata','resolved_controller_metadata','runtime_binding'] if k in n}
            r['prompt_revision']['version']='existing-prompt-revision-20261102'
            if n['status']=='revised':
                for tc in n['token_counts']:
                    for model,cap in MODEL_BUDGETS.items():assert tc[model]<=cap,(n['video_id'],model,tc[model]);max_tokens[model]=max(max_tokens[model],tc[model])
                r['prompt_variants_en']=n['prompt_variants_en'];r['prompt_en']=n['prompt_en'];r['prompt_variant_sha256']=n['prompt_variant_sha256']
                r['selected_parameter_keys']=[k for k in r.get('selected_parameter_keys',[]) if k not in n['moved_to_metadata']]
            else:assert r['prompt_variants_en']==n['prompt_variants_en'] or 'parameter_conflict_original_values_preserved' not in n['issues']
            assert initial==hashlib.sha256(json.dumps({k:r.get(k) for k in ['canonical_video_id','sha256','download','split','source_group_id','parameter_facts']},sort_keys=True).encode()).hexdigest()
            stats[n['status']]+=1;issues.update(n['issues'])
            if n.get('runtime_binding'):bindings[r['scene']]+=1
            if n.get('primary_input_metadata'):
                assert r['scene']=='T11'
                for value in n['primary_input_metadata']['selected'].values():
                    # Inputs retain literal decimal or equivalent source-backed rational.
                    for text in n['prompt_variants_en']:
                        values=[]
                        for t in re.findall(r'(?<![\w])[-+]?\d+(?:\.\d+)?(?:/\d+|[eE][-+]?\d+)?',text):
                            if '/' in t:
                                x,y=t.split('/');values.append(float(x)/float(y))
                            else:values.append(float(t))
                        assert any(math.isclose(value,v,rel_tol=1e-12,abs_tol=1e-12) for v in values),(n['video_id'],value)
            dst.write(json.dumps(r,ensure_ascii=False)+'\n')
    assert sum(stats.values())==72000
    validation=json.loads((OUT/'VALIDATION.json').read_text(encoding='utf8'));validation.update(max_token_counts_revised=dict(max_tokens),runtime_bound_by_scene=dict(bindings),t11_primary_inputs_verified_in_all_three_variants=True,previous_release_preserved=True)
    (OUT/'VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    core=json.loads((OUT/'Core100_revised.json').read_text(encoding='utf8'));conflict=next(r for r in core if r['clip_id']=='T10_C05')
    (OUT/'Core100_T10_C05_conflict.json').write_text(json.dumps({'clip_id':'T10_C05','reference':conflict['reference'],'conflicts':conflict['parameter_conflicts'],'config_provenance':'registered pre-generation reconstruction; not recovered original execution config','decision':'original values preserved; unresolved'},ensure_ascii=False,indent=2),encoding='utf8')
    text=f'''# 提示词与使用说明

保留每条三种短英文变体。新版Core100采用替换8条后的100案例名单。

- 全量72000条：{stats['revised']}条修订通过检查，{stats['needs_review']}条待核；待核条目在videos.jsonl.gz中保留原prompt，不排除任何视频。
- Core100：99条通过当前检查；T10_C05的support_x登记为0.1909 m，原prompt/已登记重建配置为0.2171429 m，原执行配置尚未核实，保留原值。
- 120条T10：原prompt速度3 m/s，发布配置1.8 m/s。已逐条核对当前视频、原输出视频、发布配置及上传记录哈希；未找到能消除冲突的当次执行日志/状态绑定，因此不自行改值。
- 视频、链接、物理参数、训练测试划分与旧评测均未改；未覆盖线上发布。

使用videos.jsonl.gz，按canonical_video_id对应原视频；prompt_variants_en[0/1/2]是三种变体，prompt_en等于第一种。相同模型对比须用同一变体。

原始完整物理输入仍在parameter_facts及config_download中。prompt_revision里记录移入metadata的字段、关键输入、补齐的控制公式和来源证据；旧external_control_inputs保留作原登记，新补证控制见prompt_revision.resolved_controller_metadata。

Core100_revised.json是新候选，含完整原版文本、改稿及冲突。三组完整对照.md与Core100完整对照.md可直接查看；backup是完整旧版备份。needs_review不可当作已解决，新prompt不可倒绑已有生成结果。

本包包含结构、真实tokenizer长度、关键参数、三变体控制一致性及不变项核验；没有声称新一轮视频生成效果已验证。T10_conflict_audit.json记录120条原始证据，pending_review.json逐条列出待核项。
'''
    (OUT/'README.md').write_text(text,encoding='utf8')
    included=['videos.jsonl.gz','revised_72000.jsonl.gz','Core100_revised.json','Core100完整对照.md','三组完整对照.md','README.md','REPORT.json','CORE100_REPORT.json','VALIDATION.json','pending_review.json','T10_conflict_audit.json','Core100_T10_C05_conflict.json','runtime_evidence.json','T01_original_headers.json','t18_repair_contract.py','t18_repair_render.py','t14s_renderer.py','backup/Core100_original.json','backup/original_72000.jsonl.gz']
    with zipfile.ZipFile(OUT/'提示词修订包.zip','w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for name in included:z.write(OUT/name,name)
    with zipfile.ZipFile(OUT/'提示词修订包.zip') as z:assert z.testzip() is None
    print(json.dumps({'status':dict(stats),'issues':dict(issues),'runtime_bound':dict(bindings),'max_tokens':dict(max_tokens),'package':str(OUT/'提示词修订包.zip')},ensure_ascii=False))

if __name__=='__main__':main()
