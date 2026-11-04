"""Package revised text with fail-safe original text for unresolved records."""
from pathlib import Path
import gzip
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/prompt_revision_20261101'

def main():
    assert (OUT/'VALIDATION.json').exists()
    applied=0
    with gzip.open(OUT/'backup/original_72000.jsonl.gz','rt',encoding='utf8') as old, gzip.open(OUT/'revised_72000.jsonl.gz','rt',encoding='utf8') as revised, gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8') as dst:
        for a,b in zip(old,revised):
            row,new=json.loads(a),json.loads(b)
            assert row['canonical_video_id']==new['video_id']
            row['prompt_revision']={'status':new['status'],'issues':new['issues'],'original_prompt_variant_sha256':new['original_prompt_variant_sha256'],'moved_to_metadata':new['moved_to_metadata'],'changes':new['changes']}
            if new['status']=='revised':
                row['prompt_variants_en']=new['prompt_variants_en'];row['prompt_en']=new['prompt_en']
                row['prompt_variant_sha256']=new['prompt_variant_sha256']
                # Old selected-key registration remains available in the backup.
                row['selected_parameter_keys']=[k for k in (row.get('selected_parameter_keys') or []) if k not in new['moved_to_metadata']]
                row['prompt_revision']['control_keys']=new['control_keys']
                applied+=1
            dst.write(json.dumps(row,ensure_ascii=False)+'\n')
    core=json.loads((OUT/'Core100_revised.json').read_text(encoding='utf8'))
    examples=(OUT/'Core100完整对照.md').read_text(encoding='utf8').split('## ')
    selected=[s for s in examples if s.startswith(('T04_C01\n','T05_C01\n','T11_C01\n'))]
    (OUT/'三组完整对照.md').write_text('# 新版 Core100 三组完整对照\n\n'+''.join('## '+s for s in selected),encoding='utf8')
    text=f'''# 提示词修订包

以现有 prompt 为底稿，保留每条三种英文短变体。未改视频、链接、物理参数或训练测试划分；未覆盖线上已有 prompt 或成绩。

- `Core100_revised.json`：最新替换8条后的100案例；99条通过本轮结构与长度检查，T10_C05保留原参数、待核。
- `三组完整对照.md`：T04_C01、T05_C01、T11_C01，各含三种变体的完整原文与修订文。
- `Core100完整对照.md`：全部100条逐条对照。
- `videos.jsonl.gz`：完整72000行，{applied}行应用本轮修订；其余{72000-applied}行保留原prompt并标记needs_review。不是全量已定稿声明。
- `revised_72000.jsonl.gz`：全部逐条修订候选及改动记录。不要将needs_review候选直接用于新一轮正式生成。
- `pending_review.json`：逐条列出冲突、长度和控制证据缺口。
- `backup/`：旧Core100和72000条完整原行备份。
- `REPORT.json`、`VALIDATION.json`：数量与不变项核验。

视频仍按原canonical_video_id、sha256、download、split对应。非关键参数移至metadata时仍保留在parameter_facts，完整控制配置按config_download绑定。保留的原prompt和已有视频、标签、评测不能自动转绑到新prompt。

T10_C05：support_x登记为0.1909 m，原prompt/配置为0.2171429 m；修订保留0.2171429，不自行判定哪条登记应覆盖。另有120条T10原prompt初速度3 m/s、绑定配置1.8 m/s，保留原prompt待核。

长度检查使用本地真实tokenizer；结构检查不等于人工逐帧或生成效果验证。尚未发布覆盖线上版本。
'''
    (OUT/'README.md').write_text(text,encoding='utf8')
    files=['Core100_revised.json','三组完整对照.md','Core100完整对照.md','videos.jsonl.gz','revised_72000.jsonl.gz','pending_review.json','REPORT.json','CORE100_REPORT.json','VALIDATION.json','README.md','backup/Core100_original.json','backup/original_72000.jsonl.gz']
    with zipfile.ZipFile(OUT/'提示词修订包.zip','w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for name in files:z.write(OUT/name,name)
    print(json.dumps({'applied':applied,'preserved_pending':72000-applied,'package':str(OUT/'提示词修订包.zip')},ensure_ascii=False))

if __name__=='__main__':main()
