# 给执行同学：H3 / T15 基础分支与物理反演联调

日期：2026-10-16。任务是重新生成明显不跌落/跌落样本，验证事件评分与 GravTrace 两条路径；不是正式临界距离实验。请完整保留失败样本和日志，不挑最好的一次。不要求重新渲染参考数据。

## 1. 本次固定范围

使用已准备的 Genesis T15 V11 home / earth 同上下文参考：

| 内部点位 | 条件初速度 | 参考分支 | 反演资格 |
|---|---:|---|---|
| case01 | 1.728 m/s | 不跌落 | 原登记 not_applicable；仍必须生成与评事件 |
| case02 | 2.832 m/s | 跌落 | pending_reference_validation；先做参考反演验证 |

注意此处 case01/case02 是 H3 输入包的编号，不是之前五条 Qwen 诊断的编号。物体是绿色书本、灰色闭合笔记本和地面黑色手机；重力9.81 m/s²。目标初速度属于书本，不是笔记本自由飞行起点速度。

两个点各用种子41000、41001，共4条，全部事先登记。同一种子用于两端，配对标记 coupled_seed；不能按独立端点乘积解释。可先跑41000两条检查部署，但无论结果好坏仍保留两条，正常部署后完成预登记的41001。若OOM/文件损坏则记录工程失败与重试次数；不得为了成功结局换种子。提示仅给初始条件，不给“应当跌落”的答案。

## 2. 交付材料与执行环境

GitHub 分支 codex/critical-boundary-pipeline 已包含 H3 runner、scripts/prepare_t15_h3.py、examples/t15_h3 下的条件图/提示与参考事件来源、筛查评分模块和 GravTrace。直接 clone 即可获取，无需交接包。仓库不含H3或Qwen权重，先记录 git commit 和环境版本。

执行同学先回填：可连接主机、Python路径、H3权重路径、GPU编号与空闲显存、torch/diffusers版本。历史H3路径只是旧配置，不能默认存在。不必使用hupanwen；任何已有兼容H3部署的主机均可。runner需torch、diffusers（支持ModularPipeline）、av、imageio_ffmpeg、Pillow等；不要盲目升级已可工作的环境。若接口不兼容，回传报错和版本后修复。

## 3. H3生成合同及命令

固定：I2V单条件帧，896×512画布，124帧，24fps，50步，原生末帧时间123/24=5.125秒。输入854×480，以左右各21、上下各16像素padding；输出裁回854×480，禁止拉伸物理几何，禁止视频变速或补帧到6秒。runner使用 --pad-input。音频不参与评分。

clone 仓库指定分支并进入根目录，在Linux执行（先设置以下真实环境值）：

```bash
export H3_PY=/actual/path/to/python
export H3_MODEL=/actual/path/to/MiniMax-H3
export CUDA_VISIBLE_DEVICES=0,1
"$H3_PY" scripts/prepare_t15_h3.py --out h3_manifest.jsonl
"$H3_PY" physedit/runners/minimax_h3.py \
  --source-manifest h3_manifest.jsonl --out-root h3_t15_run \
  --model "$H3_MODEL" --steps 50 --pad-input
```

脚本为4条分配独立 source_sample_id 和输出目录，防止第二个种子覆盖第一个。runner可在已有兼容环境单卡/多卡运行，但此包不保证任意显存规格可用。运行前检查空闲资源，不终止他人任务。

输出：h3_t15_run/runtime/full_manifest.jsonl、generation_status.jsonl、每条原始和裁回视频。失败的输入登记仍然保留。回传全部4条状态，不能只给成功manifest。

## 4. 统一时间窗和媒体绑定（评分前必做）

参考条件帧为30fps的第29帧，视频输出时间0对应参考29/30秒。本次参考评分窗为[29/30,29/30+5.125]秒；用已有逐帧状态核对这个窗内的事件真值，不直接把旧6秒合同当成新真值。截图/状态检查不足的标签记待核验。精确事件时刻记录实际帧时间，不伪造插值帧。

每条输出全解码，核对124帧、24fps、854×480与时间戳；计算SHA256。使用 importer 按预登记 source_sample_id 绑定视频，它从全部4条出发，全解码媒体并保留缺失/失败。参考事件帧均已在5.125秒窗口内核对，来源保存在 examples/t15_h3/reference_provenance.json；不代表反演资格已验证。

```bash
python scripts/collect_t15_h3.py --manifest h3_manifest.jsonl --generated h3_t15_run --out RUN
```

输出评分注册、事件标注模板及 RUN/qwen/inputs.jsonl（只含实际有效媒体，不含答案）。评分全集仍为4条。请勿修改已哈希的注册文件。


## 5. VLM筛查和事件判读

先让部署的Qwen判读：目标身份是否保持、是否消失/融合、镜头/几何是否变化，以及可观察的跌落结果和证据帧。对象说明可以给；参数侧别、参考结局、生成模型名不得给裁判。

均匀抽样覆盖0..5.125秒。仓库 scripts/t15_qwen_judge.py 已按输入manifest读取实际5.125秒窗口并保存帧索引。建议保留26帧的初筛预算。Qwen3VLVideoProcessor的size.longest_edge是整段T×H×W预算：26帧时使用26×262144；核对实际grid（之前为[13,22,42]，672×352/帧），避免误压到128×64。接触事件需在候选区间加密看原生帧，26帧初筛不能验证短暂接触。

运行（QWEN_PY/QWEN_MODEL 使用已有部署，GPU编号按主机实际选择）：

```bash
"$QWEN_PY" scripts/t15_qwen_judge.py --root RUN/qwen --gpu 3 --model "$QWEN_MODEL"
```

无有效媒体时跳过推理，创建空结果文件，后续评分仍保留4条。该有界runner要求指定GPU至少22500MiB空闲，并限制最多6条。环境不兼容请回传版本/错误，不用低分辨率静默替代。脚本保存模型/输入哈希与原始结果。

使用 quality_flags / assessable / reason 的结构化输出并保存原始回答、模型/提示/采样版本。出现形变等标记先suspect，不直接删除。人工复核：确认身份丢失后标 confirmed_failure，写 reviewer、时间段、受影响事件和 block_inversion；仅镜头漂移但跌落仍明确时可保留事件，反演另审。评测器失败不要归因模型。

将 RUN/event_annotation_template.jsonl 复制为 events.jsonl，填写判读来源和证据；reviews.jsonl 格式见 FAILURE_HANDLING.md。逐项判读：book_contacts_laptop、laptop_crosses_support_boundary、laptop_falls_to_floor、laptop_contacts_phone、phone_slides，以及登记的必要时序。标签0/1/null，给证据。先判生成视频实际发生什么，再与参考答案比较；不要用参考标签填生成标签。失败前的可靠事件保留。论文级验证建议两位独立标注者盲标并仲裁。

```bash
python -m physedit.boundary screen --run-dir RUN \
  --judgements RUN/qwen/results.jsonl --reviews reviews.jsonl --out-dir SCREEN
python -m physedit.boundary score --run-dir RUN \
  --screening SCREEN/screening.jsonl --annotations events.jsonl \
  --out event_score.json
```

## 6. GravTrace：参考先验收，再拟合生成视频

不跌落点不强行反演重力。跌落点也不能看到运动就登记eligible：必须验证目标的自由飞行段、时间标尺、物体几何与相机条件确实满足现有反演假设。

先在2.832m/s参考视频上：用状态选取笔记本失去支撑后、首次接触地面/手机前的连续段；逐帧跟踪目标，准备真实timestamps/boxes或masks、标定相机、尺度与适用运动模型。不得跨碰撞窗口拟合。当前代码最低观测帧数为4，但达到4帧不自动等于可辨识；需检查有效位移、旋转、遮挡、投影和拟合残差。缺字段或短到不足时回报不可测原因，不制造运动轨迹。

相机/尺度/几何及模型假设按gravtrace既有schema准备。运行现有接口：

```bash
python -m gravtrace fit reference_fit_manifest.jsonl -o reference_predictions.jsonl
python -m gravtrace score reference_fit_manifest.jsonl reference_predictions.jsonl -o reference_fit_summary.json
```

这两条命令不是manifest自动构建器。当前T15没有已冻结的参考反演登记；务必回传manifest、轨迹叠图、残差及状态供验收。fit入口会剥离truth；9.81只用于事后验证，不能固定g=9.81再声称反演成功。不能在该生成视频上反复调相机/窗口使结果靠近9.81。

参考通过后冻结相机/尺度/规则、有效窗口选择方法、误差与残差验收阈值及reference_registration_sha256，并在新版本注册中将适用点改eligible（保留旧版本，不修改已哈希快照）。阈值优先沿用既有已验证配置；若T15尚无适用阈值，先作为开发校准报告，不临时凭结果制定“通过线”。

对筛查通过且有适用飞行段的H3输出独立提取轨迹；不得复制参考轨迹当生成观测。镜头漂移会破坏固定相机反演假设，需标该项不可测，即使跌落事件还能判断。执行同样fit命令，将原生预测适配为boundary gravity.jsonl：sample_id、status、gravity、video_sha256、reference_registration_sha256。原生gravtrace输出不是该适配文件，不能直接改扩展名导入；at_bound、轨迹丢失、无飞行段、未收敛均保留原因，不计有效拟合。

```bash
python -m physedit.boundary score --run-dir RUN \
  --screening SCREEN/screening.jsonl --annotations events.jsonl \
  --gravity gravity.jsonl --out joint_score.json
```

## 7. 回传表与完成标准

每条回传：ID/种子、生成状态、视频hash、筛查状态/人工证据、五事件与时间、反演参考资格、拟合状态/估计g/误差或失败原因。

汇总必须包含：登记4条、失败数量；跌落事件有效数/4、全分母成功数/4、有效子集准确率；整链有效数/4和EventExact；共享种子配对成功数/2；反演有效数/4、已批准适用数/4、有效数/适用数及误差。适用数为0时条件覆盖率=null。NearAcc本次不报，边界记录尚未绑定。

“流程跑通”指4条均有状态和可重算记录，包括失败；“基础分支通过”指两个方向均有正确可判生成，并报告两种子实际成功数，不能据此断言统计稳定；“反演跑通”至少需参考验收及1条生成输出获得可审计有效拟合。如果H3全部未跌落或相机漂移，则反演未跑通，应如实交付，不能绕过失败门控。

请回传全部视频、源manifest、运行环境/日志、参考窗口核对、Qwen原始结果、人工表、轨迹/相机/拟合manifest及两份评分JSON。如果只能先完成生成，回传4条视频和runtime目录即可由维护者继续；明确哪些步骤未执行。
