"""Report actual live scores and the remaining individually traced source issues."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];W=ROOT/'review/core100_remaining20_20261101'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
r=read(W/'LIVE_FORMAL.json');receipt=read(W/'DEPLOYMENT.json')
assert receipt['live_api_verified']and receipt['old_scores_preserved']and receipt['preserved_formal_cohorts']==75
cohort=next(c for c in r['cohorts']if c['cohort_id']=='t15_c04-original-observable')
with (W/'T15_C04_MODEL_RESULTS.csv').open('w',encoding='utf-8-sig',newline='')as f:
    rows=[{k:m[k]for k in('model','matching_registered','known','TargetAccuracy','blockers')}for m in cohort['per_model']]
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
trace=read(W/'ARCHIVED_STATE_TRACE.json');frames={x['clip_id']:x for x in read(W/'ORIGINAL_TRANSFER_FRAME_PROOF.json')}
assert len(frames)==14 and all(x['status']=='original_config_parent_and_all210_active_frames_verified'for x in frames.values())
audit=[]
for x in trace:
    cid=x['clip_id'];state=x['states'][0]
    audit.append(dict(clip_id=cid,target_reference_admitted=False,original_video_config_hash_verified=True,
        all210_parent_and_reference_decoded_frames_identical=True,located_state_sha256=state['sha256'],
        located_state_declared_video=state['declared_video'],
        blocker='Other declared camera; same-trajectory provenance for current cam01 not established',
        original_protocol_thresholds_changed=False,old_results_changed=False))
for x in read(W/'FULL_FRAME_DECISIONS.json'):
    audit.append(dict(clip_id=x['clip_id'],target_reference_admitted=x['status']=='passed',
        reviewed_native_frame_count=len(x['reviewed_native_frames']),status=x['status'],notes=x['notes'],
        original_protocol_thresholds_changed=False,old_results_changed=False))
assert len(audit)==20 and sum(x['target_reference_admitted']for x in audit)==1
(W/'ALL20_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
text='''# 剩余20条核验与正式接入结果

已发布到 https://label.yeegoods.cn/physics/ 。本轮增加T15_C04，正式原目标参考由80增至81；原边界区间仍40条，Near参考仍10点，合法配对仍3组。没有扩写原事件、物理阈值或配对规则。

T15_C04的原视频210帧全部解码、编号并逐帧查看，覆盖0至209，无时间抽帧。笔记本从桌边落下、落在手机左侧，至原五秒观察窗结束保持分离，手机在相关过程中持续可见。原状态的全子步接触汇总也没有笔记本—手机接触。按原规则准入“laptop_contacts_phone=0”，仅准入该目标事件，不准入距离、NearAcc或PairAcc。

本轮新增26条可判定输出，15条正确。累计2916条关联输出中935条可判定、114条正确；这些是覆盖与计数，不能当作完整Core100准确率。

T15_C04单案例结果（每模型原有3条prompt/seed组合）：

| 模型 | 已判定/匹配输出 | 原目标正确率 |
|---|---:|---:|
'''
for m in cohort['per_model']:
    score='N/A'if m['TargetAccuracy']is None else f"{m['TargetAccuracy']:.1%}"
    text+=f"| {m['model']} | {m['known']}/{m['matching_registered']} | {score} |\n"
text+='''
以上仅T15_C04单案例，不是模型全测试集排名。N/A保留完整分母，不能把2/3完成或缺标签的情况当作完整成绩。

## 其余19条的核验结论

T06_C01/C02/C03/C05、T09_C01–C05、T10_C01–C05共14条：

1. 14条原视频、原配置均已找到，文件SHA全部与原TRANSFER_MANIFEST对应。
2. 当年genesis_reuse_plan中12条记录为复用、T09_C04/C05记录为另行渲染。两类分别处理，不把旧mu轨迹转给新mu配置。
3. 14条原父视频与当前重定时参考的全部210个解码帧分别精确相同，已排除当前参考重定时过程中换轨迹的疑问；没有使用图像近似相似度阈值。
4. 已取回14份旧状态候选，包括原来没有定位到的5份T10状态。但文件虽命名cam01，内部render.save_video指向cam02或cam03，不能仅凭文件名认定是当前cam01实际轨迹。归档批次部分存在H.264兼容转码记录，转码也不能解释或消除机位身份缺口。
5. 已查p25原工程、原上传缓存、HF固定修订缓存、上传暂存、配置绑定与参考存储备份等9处，共23188个目录；另查看p26已有工程/备份、p29已有工作目录，未发现可闭环的当前cam01原状态。找到的其他机位状态与重算状态未提升为正式真值。

另读取原生产队列和临时执行日志72份（约3.22MB），匹配了具体样本ID。可见旧生产失败记录，以及T10后续Isaac复现/物理探针记录；未找到把当前Genesis cam01视频SHA与原状态SHA绑定起来的成功执行证据。旧FAIL不视作当前最终视频质量失败，Isaac复现的位移数字也不转为Genesis原真值。逐文件和逐行证据见 EXECUTION_LOG_SEARCH.json。

逐条的状态SHA、内部视频路径、原视频及配置验证状态见 ALL20_AUDIT.json；完整原上传来源、归档状态与备份搜索证据保留在本目录。当前14条均未因缺状态而移出训练清单或标注任务。

T11_C01–C05：

五条各210帧、共1050帧全部解码并逐帧查看。三目标确实能看到早期下落，但在原五秒窗口末帧154全部不在画面内，后续直到209帧也没有恢复所需末态视野。原状态与原“末态中心世界z<-0.10m”标签仍保留；“此前下落”不能替代该末态事件。当前固定视角不能补出缺失画面，因此没有把这5条伪报为已通过可观察性准入。

## 保留与上线验证

- 上线前80条参考所在75个评分组的参考定义、逐视频结果和各模型成绩完整比较一致；原per_model/admitted_cohort/contact_amendment/vlm_human_agreement字段也一致。
- 没有更新任务、人工标签、prompt、物理参数、训练清单或旧结果；全部3600条任务保持原样。
- 39项针对性测试通过；线上服务active、页面HTTP200；6项认证导出验证通过、匿名导出拒绝。
- 本轮只更新3个参考/媒体证据/进度资源文件；不覆盖并行修改的数值边界登记。
- 视频继续由Hugging Face链接评测；没有向网站数据盘上传视频，没有运行新仿真或VLM调用。
'''
(W/'RESULTS_ZH.md').write_text(text,encoding='utf8')
print(json.dumps(dict(registered=r['summary']['formally_registered_reference_cases'],new_scored=26,new_correct=15,remaining=19)))
