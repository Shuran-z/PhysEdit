# 临界评测流水线

2026-10-17：新增[两阶段正式入口与人工回填说明](TWO_STAGE_PIPELINE.md)，命令 `python -m physedit boundary-evaluate`。先独立质量调用，再仅对质量通过者调用事件判读；预标注与人工确认分离，失败/待审保留注册总分母。该入口接入原score，不代表自动裁判可靠性已认证。

本目录的统一协议见 [`CRITICAL_BOUNDARY_PROTOCOL.md`](CRITICAL_BOUNDARY_PROTOCOL.md)。完整的从安装、登记、运行、事件标注到评分步骤见仓库根目录 [`BOUNDARY_EVALUATION.md`](../../BOUNDARY_EVALUATION.md)。协议为 benchmark 设计；代码实现的是登记/生成/导入标注/聚合，不含已验证的自动事件识别器。

新增独立入口 `python -m physedit boundary`（也可用 `python -m physedit.boundary`）。它不调用旧 fleet 或以自由飞行反演资格作为生成门槛；可移植到 GitHub 新版代码旁使用，不替换冻结 GravTrace。

## 登记与执行

输入为两份 ID 完全一致的 JSONL：`inputs` 只包含条件图、提示、seed、原生帧率/帧数与时域；`answers` 单独保存参数、来源组、参考事件、边界、配对及反演资格。生成 argv 只收到 allowlist 导出的 `generation_rows.jsonl`，没有参考标签、临界值或反演资格。

```powershell
python scripts/build_t15_boundary_run.py --out review/new_t15_registration
python -m physedit boundary run --spec boundary_spec.json --run-dir runs/t15_new
python -m physedit boundary run --spec boundary_spec.json --run-dir runs/t15_new --execute
python -m physedit boundary score --run-dir runs/t15_new --annotations events.jsonl --out runs/t15_summary.json
```

`boundary_spec.json` 登记 `model`、`inputs`、`answers` 和 `generation_command` argv 列表；仅支持 `{manifest}`、`{run_dir}` 替换，不经过 shell。运行目录必须不存在。未知运行失败逐例保留，不自动重试。参考图片不存在或哈希不符会阻止该点推理，但仍保留其 ID；**反演不适用不会阻止生成**。

T15 LTX 有界适配器是 `physedit/runners/boundary_ltx.py`，最多两条，每条161帧/25fps、50步、CFG3；需要调用方提供本机已安装的 Diffusers 与模型路径，不下载权重。启动前检查登记 GPU 剩余显存和利用率，不终止其他任务。只用于工程 pilot，不代表所有模型正式接入完成。其他模型通过 `generation_command` 适配器接入；其输出仍必须遵守登记的时钟、尺寸与帧数合同。

## 分母与输出

| 文件 | 作用 |
|---|---|
| registered.json / inputs.jsonl / answers.jsonl / snapshot_hashes.json | 全部登记及固定快照；评分时检查哈希 |
| preparation.jsonl | 每条输入校验结果，反演资格不进入过滤 |
| generation_rows.jsonl | 实际推理清单，只含模型输入 |
| observed_rows.jsonl | 全部原ID的媒体核验或生成失败 |
| generation_receipt.json | 登记数、推理数、媒体成功数及进程状态 |
| event_annotation_template.jsonl | 与视频SHA绑定的未知事件模板，初始全为 null |
| 独立评分 JSON | 全部逐例结果、组级准确率、配对分数、NearAcc覆盖与反演分母 |

合法负例、反演不适用、反演资格待核对、生成失败和标注缺失始终保留。事件缺失/不可判在主正确率中计未正确，原因另列。参考没有可核验临界值时 NearAcc 为 null，而不是填0或用三点中值伪造阈值。

反演记录可通过 `score --gravity predictions.jsonl` 读取冻结输出的适配记录，每行必须有 `sample_id`、`status`、`gravity`、`video_sha256`、`reference_registration_sha256`。只有参考已登记 eligible、预测 status=ok 且两类绑定一致时进入有效请求重力偏差。at_bound 不计成功。此适配只消费预测，不重新拟合，不把不适用输入送入旧反演器。

当前 T15 两点无已冻结反演资格：不跌落点 not_applicable，跌落点 pending_reference_validation。保持其真实状态，重力结果为不可测/待验证；这不影响分支和事件链评分。

## 事件标注

模板需要独立人工或经过验证的事件评估器填写，包含 `events`（0/1/null）、`event_times_s`、`method`、`evidence` 与原视频SHA。不把参考答案抄入生成标注，不把通用Qwen“没有违规”转换成事件完全正确。顺序关系需要发生时间；只有事件位正确但未提供必要时间，不能获得 EventExact。

本入口先实现登记、推理、媒体核验、独立标注导入与评分闭环；自动事件检测器、自动调用冻结重力环境尚未接入。单次视觉审核只作 pilot，不代表评估器已通过独立准确性验证。

聚合为种子→点→族内正负类平衡→来源组→场景。独立配对使用两端点正确率乘积，不能把 K² 组合当独立实验；T15 pilot 每点仅一个独立seed，不产生可靠的模型排名结论。当前首次错误统计按登记事件顺序解释，复杂并列事件图需专门报告节点而非线性阶段。

## 验证

```powershell
python -m unittest discover -s tests -p test_boundary.py -v
```

回归覆盖：负例不被反演筛掉、答案不进入推理字段、全部生成失败保留、缺标注、恒定答案配对失败、at_bound、快照/视频漂移、陌生ID、区间距离跨桶、短时域拒绝、输出不覆盖，以及 Windows 构建 Linux 路径。合成测试与真实模型结果分开记录。
# 2026-10-15：筛查接入补充

先运行 `python -m physedit.boundary screen --run-dir RUN --judgements QWEN_JSONL --out-dir SCREEN_NEW`，需要复核时加入 `--reviews REVIEWS_JSONL`。随后 score 必须带 `--screening SCREEN_NEW/screening.jsonl`。详情、字段及分母公式见 [失败处理](FAILURE_HANDLING.md)。screen 导入已有 VLM 输出，不自动启动远程模型。routing 只控制后续工作，不能用它过滤评分注册表。

