# VLM 先筛查、失败保留与分任务覆盖率

2026-10-15。此补充覆盖此前“不可判直接删除”或用反演成功子集定义临界评测的处理。它不改变已冻结的物理反演适用性，也不将质量、事件与重力误差合成为任意加权分数。

## 流程与状态

固定全部注册样本 N → 媒体检查 → VLM 筛查 → 疑似问题人工复核 → 按事件及反演分别派发工作 → 回到完整注册表统计。

| 状态 | 意义 | 后续处理 |
|---|---|---|
| pass | 未发现需阻断的问题，或复核通过 | 可进入事件判读；参考适用的样本进入反演 |
| suspect | VLM 报告质量异常或不可判 | 暂停自动后续测量，待人工确认；不等于生成失败 |
| confirmed_failure | 复核确认目标消失、融合、身份改变等生成失败 | 明确 blocked_events 与 block_inversion；仅停止相应测量 |
| evaluator_failure | VLM 缺失、执行或格式失败 | 修复评测器或人工接管，不归因于生成模型 |
| missing | 评分阶段未找到应有的筛查记录 | 保留样本、待补判，不能默认为通过 |

当前 Qwen T15 五条开发诊断尚不能支持无人复核自动拒绝：它会报告形变，但仍断言没有跌落。所有 quality_flags（包括相机运动）先作为疑似信息，不能直接当生成失败；人工可判定为 pass。pass 也不是经过独立验证的正确事件标签，仍需独立事件证据并随机抽检通过样本。

确认失败须绑定 sample_id、video_sha256、reviewer、证据，以及具体受影响事件列表和反演阻断标志。比如跌落已清楚发生、之后目标消失，则保留跌落标签，阻断后续手机接触和依赖消失阶段的反演。不要把跟踪器失败或正常遮挡直接记为目标消失。

## 统计定义

设 M_e 为事件有可靠标签的注册样本数，C_e 为其中正确数；M_chain 为所有登记事件和必要时序均可判的样本数；N_g 为事先登记反演适用数，M_g 为通过绑定与有效性检查的反演数。

- 事件全样本成功率 C_e/N；有效事件覆盖率 M_e/N；条件事件准确率 C_e/M_e。
- 完整事件链覆盖率 M_chain/N；条件 EventExact 仅在该有效子集计算。错误标签仍是有效测量，不从覆盖率中排除。
- 每种事件另报其登记数与可判数；不同事件的分母不强行相同。
- 反演报告 M_g/N（registered_coverage）、N_g/N（eligibility_rate）、M_g/N_g（eligible_fit_coverage），误差只在 M_g 上计算。空有效集误差为 null，不填零；不适用样本仍留在 N。
- task_success_rate：完整事件链及顺序正确且筛查通过的数量/N。它是样本微平均的生成有效性与事件联合诊断，不包含反演阈值，不取代原来的分组宏平均主指标。
- NearAcc、距离分层准确率、独立或共享种子配对、EventExact 仍从完整注册点/种子计算。受阻断或缺失的事件不能记成功，不因筛查删点、删种子、删配对。已确认的前序事件可以继续为对应事件指标提供证据。

例：100 条中 20 条目标身份失败，剩余 80 条有 60 条事件正确，则全样本成功率 60%，事件有效覆盖率 80%，条件准确率 75%。覆盖率与条件准确率乘积等于这里的微平均成功率；不能直接将全局覆盖率乘原有分组宏平均 NearAcc。

必须分开报告生成失败、待复核和评测器失败。未解决样本在分母中暂记未成功，所以存在这些状态时结果是未完成评测的保守统计，不应当作已完成的模型能力排名。代码提供 unresolved_count；还应检查未完成事件标注与反演状态。

## 执行接口

```bash
python -m physedit.boundary screen --run-dir RUN --judgements qwen_results.jsonl --reviews reviews.jsonl --out-dir SCREEN_NEW
python -m physedit.boundary score --run-dir RUN --screening SCREEN_NEW/screening.jsonl --annotations events.jsonl --gravity gravity.jsonl --out score_new.json
```

reviews 可省略，此时疑似状态保持待复核。screen 导入已有 Qwen runner 的逐条 JSONL（sample_id、video_sha256、status、judgement），不启动新的远程推理。judgement 至少含 quality_flags 数组、assessable 布尔值和 reason。原始 Qwen 回答及模型/提示/采样配置须与其结果文件一起保存；screen receipt 记录导入文件哈希。

人工复核 JSONL 示例（事件名必须属于该样本的登记事件）：

```json
{"sample_id":"example","video_sha256":"ACTUAL_SHA256","status":"confirmed_failure","reviewer":"annotator_01","evidence":"目标从2.4秒开始与背景融合；此前跌落已明确可见","blocked_events":["phone_contact"],"block_inversion":true}
```

输出 screening.jsonl 与 routing.jsonl。routing 保留每个注册 ID，event_work 和 inversion_work 仅决定后续工作，不定义计分样本集合。评分时将与筛查范围冲突的事件标签/反演值屏蔽，即使旧标注文件仍含数值也不能算有效。评分从 answers.jsonl 完整表开始，禁止将 routing 的可工作子集另建为新的计分全集。

历史调用不带 --screening 仍可重现，但明确标记 enabled=false、legacy_not_screened，不能声称执行了新版 VLM 前筛查。正式新版报告必须带 --screening。该入口实现结果导入、派发与统计；模型推理与 GravTrace 求解仍由各自 runner 执行，不宣称已完成端到端自动裁判验证。

主要输出：screening、event_measurement（target_coverage、chain_coverage、per_event、条件分数）、inversion（两个覆盖分母与误差）、task_success_rate，以及逐样本的阻断原因。论文主表须同时展示覆盖率、条件性能和失败/未完成数量。
