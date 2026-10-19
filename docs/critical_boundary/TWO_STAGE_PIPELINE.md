# 独立质量筛查 → 事件预标注 → 人工回填 → 评分

## 边界来源绑定与离散样本恢复（2026-10-18）

`boundary score` 和本流水线均接受 `--boundary-bindings FILE.json`，绑定文件锁定原答案文件SHA256、参考样本/状态哈希、固定上下文、目标事件和参数值；原登记不改写。该侧文件仅进入评分，不暴露给VLM。

`boundary.status=verified` 使用已审定的边界点或区间及预登记归一化尺度。`status=observed` 保存现有参数点上异侧事件形成的 `intervals`，评分输出绝对距离范围，`bin=null`，不自动纳入NearAcc。这些区间不证明唯一单调阈值；不能取中点伪装精确临界值。单点、标签未知、重复标签冲突和QA失败不作为已证实两侧；中间有未知点时不能跨过去拼接端点。工具为 `physedit.boundary_recovery`。

发布目录的delivery/config/QA哈希匹配不等于新物理审查通过。修复版本必须检查控制量和固定物理上下文；仍待视觉审核的组导出复核队列，不自动记正式通过。无搜索记录且无现有异侧样本时，保留未解析状态并准备后续搜索，不由VLM凭视频猜测精确参数边界。

2026-10-17。正式软件入口，**不等于Qwen已经通过独立裁判可靠性认证**。保留完整注册分母，默认只将人工确认事件送入正式分数。

## 调用

先通过 `python -m physedit.boundary run` 完成原生成登记，得到RUN中的inputs、answers、snapshot_hashes及observed_rows。然后：

```bash
python -m physedit.boundary_pipeline --run-dir RUN --protocol protocol.json --out-dir EVAL --execute
# 也可以用 python -m physedit boundary-evaluate ...
```

协议必须覆盖RUN中的所有sample_id和注册事件名称。事件名称与定义来自冻结协议，**不能把历史falls_to_floor名称直接解释成落地**。显式说明实际语义。协议示例：

```json
{
  "confidence_threshold": 0.9,
  "timeout_seconds": 3600,
  "quality_command": ["python", "-m", "physedit.qwen_boundary_judge", "--stage", "quality", "--model", "/models/Qwen3.5-9B", "--manifest", "{manifest}", "--output", "{output}"],
  "event_command": ["python", "-m", "physedit.qwen_boundary_judge", "--stage", "events", "--model", "/models/Qwen3.5-9B", "--manifest", "{manifest}", "--output", "{output}"],
  "samples": {
    "sample_001": {
      "target": "the closed laptop initially beside the book",
      "events": {
        "departure": {"definition": "Complete separation from the initial tabletop support within the observation window.", "minimum_evidence_times": 1},
        "descent": {"definition": "Downward motion after complete separation; ground contact is not required.", "minimum_evidence_times": 2}
      }
    }
  }
}
```

示例ID/事件必须替换为真实注册表。协议的samples字段可选roi=[x1,y1,x2,y2]、generated_track路径和generated_track_sha256。轨迹必须来自**生成视频**的SAM2等观测结果，其video_sha256与生成视频绑定，不能放入参考仿真轨迹。启用时用运动峰值加密抽帧，ROI提供同步局部图及框；无轨迹时使用均匀13帧全图回退，receipt记录配置。Qwen适配器只读本地模型，不下载权重；需已部署兼容Transformers、Torch、Pillow、OpenCV。通过CUDA_VISIBLE_DEVICES和可选--max-memory-json指定已确认可用GPU预算；正式入口不会自动抢占GPU或终止其他任务。没有执行额外远程生成任务。

quality与events是**两次独立调用、独立提示**。质量只收到生成媒体、目标、时域和可选观测轨迹/ROI；事件再收到事件定义。参考答案、参数侧别、临界值及参考事件时刻均不导出。argv不经过shell。质量未通过者不进入事件任务。空任务不会加载模型。

也可导入预先计算的同合同输出：

```bash
python -m physedit.boundary_pipeline --run-dir RUN --protocol protocol.json --out-dir EVAL_IMPORT --quality-predictions quality.jsonl --event-predictions events.jsonl
```

每行必须有sample_id、video_sha256、status。质量字段quality包含status(measurable/unmeasurable/uncertain)、failure、target_integrity、support_integrity、confidence、evidence_times_s、reason。事件字段events按注册名包含label(yes/no/not_observed/uncertain)、confidence、evidence_times_s、reason、contradictions列表。API/自定义适配器必须确认时间来自实际送入模型的帧；内置Qwen适配器执行此检查。导入适配器对内容真实性负责，外层另检哈希、时域与格式。

## 路由与分母

- 高置信可测且对象/支撑面完整：质量候选pass，进入事件调用。
- 高置信明确破坏并有两时刻证据：auto_rejected，停止事件和反演候选调度，保留总分母和质量复核项。**未经人工不能升级confirmed_failure。**
- 低置信、未知、格式/调用失败：review。生成媒体缺失为media_unavailable，仍保留注册数。
- 每事件高置信、证据满足定义、contradictions为空：preannotated，仅写预标注文件，不直接进入正式分数。
- not_observed为observation_only，不自动转负类，不计二分类可判覆盖。若任务必须取得该事件二分类答案，可通过人工回填；不必为辅助落地字段强行补答案。
- 人工锁等特定限制应由调用方保留在人工流程中；正式通用入口不硬编码clip03/clip06等开发样本。
- inversion_candidates只表示质量通过且参考已eligible；尚需独立反演适用性检查和实际拟合，不等于反演完成。

## 人工入口与回填

EVAL/review_queue.jsonl提供质量/事件待审项，EVAL/preannotations.jsonl供人工确认预标注。完整roster在routing.jsonl。按下面格式保存reviews.jsonl，再使用**新输出目录**重跑汇总：

```json
{"sample_id":"sample_001","video_sha256":"实际SHA256","reviewer":"reviewer_01","evidence":"人工证据及审核备注","quality_status":"pass","events":{"descent":{"label":1,"time_s":1.7,"evidence":"已离桌并持续下降"}}}
```

质量确认失败：quality_status=confirmed_failure，events={}，必须写审核人和证据。当前通用入口保守阻断该目标全部注册事件及反演，不自动保留损坏前事件。未知事件不填写，不能填0代替。

```bash
python -m physedit.boundary_pipeline --run-dir RUN --protocol protocol.json --out-dir EVAL_REVIEWED --quality-predictions EVAL/quality_predictions.jsonl --event-predictions EVAL/event_predictions.jsonl --reviews reviews.jsonl
```

若人工将原质量待审样本改为pass、该样本尚无事件预测，可以只回填人工事件；或省略--event-predictions并加--execute重新生成当前可测集合的事件预测。质量人工pass只打开判读，不推断事件正确。

## 输出与验证

scores.json调用原boundary评分器，保留全注册分母；annotations.jsonl仅含人工确认标签；screening.jsonl区分pass、suspect、confirmed_failure。receipt记录候选计数、调用退出码、输入输出哈希及inversion_completed=0。pending不算已确认生成失败；原评分器的全分母未正确率包含待审，因此待审尚未解决时不得当作最终模型排名，结合screening unresolved_count解释。

```bash
python -m unittest tests.test_boundary_pipeline tests.test_boundary_triage tests.test_boundary_window tests.test_boundary_event_judge
```

测试覆盖两次调用先后顺序、质量拒绝不进入事件、全部分母保留、参考答案不进入judge manifest、预标注不进入正式分数、哈希拒绝、人工回填及质量确认失败。六条H3/LTX开发实验支持拆分调用，尚非独立准确率验证。新通用接口经过合成端到端回归；本次未重新进行GPU模型实验。
