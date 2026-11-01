# CVPR实验执行入口

整体主线是“受控物理参数→事件分支→因果过程→定量运动”。GravTrace为其中的数值测量模块。本文为当前工作入口；详细研究比较、历史审计和私有证据见`review/cvpr_experiments_20261031/CVPR_GAP_AUDIT.md`。私有实验目录不能整体公开。

## 优先完成的证据

1. 当前Core100输入与事件/观察窗逐项准入，以及公平的生成模型主表。
2. VLM与人工复核的可靠性：独立观察、分歧裁定、覆盖率与失败处理。
3. 同输入的物理反演比较，保持窗口、投影、轨迹和版本绑定。
4. 固定训练预算和同基座的Base/LoRA配对比较，不按测试效果选择检查点。

## 当前实验与限制

运行状态优先查看`review/cvpr_experiments_20261031/INDEPENDENT_SERVER_SNAPSHOTS.json`中各服务器的`observed_unix`、连接结果和具体进程；`LIVE_EXECUTION_SNAPSHOT.json`保留为此前全量快照，可能更旧。排队、加载、优化步、出片和评分分别记录。下表是已核验证据摘要；持续变化的数量以各自时间戳为准。

|项目|已取得的证据|仍缺什么|
|---|---|---|
|Core100生成库存|固定HF revision下10800个登记路径存在，Core100的100案例×12模型×3种prompt×seed0，共3600个模型生成槽|其中T19五例的180槽使用替换前输入；路径存在不等于媒体QA或当前版本评分完成|
|人工覆盖|原冻结快照2223；只读快照1793491275经相同输入匹配检查为2246个seed0质量终审位置|相对3600槽缺1354；原1377和前次1356留存作历史；不含本轮新Base/LoRA标签，不把质量记录当独立事件gold|
|临界参考|当前登记85条距离依据，另15条不完整；含T05_C02完整窗CPU64条件结果，保留后端差异|正式参考/配对仍2/1，完整NearAcc/PairAcc未完成；数值准备度不等于媒体或评分准入|
|T05物理时钟|原代码前27帧不执行物理步进，条件帧4与静态末帧26状态一致；物理5秒为源帧27–176|仅建立T05候选修订，不统一删除其他模板片头；正式登记仍保留原版本|
|T05_C03边界|物理5秒摩擦候选区间[0.04916015625,0.049240234375000004]；完整有效过程区间[0.050521484375,0.0506015625]|两个端点均完成原光追/854×480复跑：第175/177帧通过，最大位置差0.019/0.064毫米；RGB与版本登记尚未准入|
|T05_C04/C05|C04原渲染区间[1.143203125,1.1434716796875]恢复，正端点独立复测通过；C05原两端点已复现|两条不同seed分别保留；归一化距离至少相差0.212601，超过0.02容差，不构成距离匹配对；正式RGB/窗口准入仍待完成|
|可测性帧数诊断|118条×8/24帧完成|这是20261028 binary策略及既有标签诊断，不是四缺陷scene-v2独立验证|
|scene-integrity-v2|48/48机器运行完成，29条拒绝复核候选、19条通过；48条匿名人工包已验证|独立人工标签尚未取得；机器路由不是确认质量或准确率|
|T19参考RGB可判性|固定24时刻ROI恢复了5/5运动识别；接触仍仅2/5正确；5条匿名参考包已验证|需独立人工观察，不能由可见运动推断细微接触可判，也不能用ROI试验充当独立验证|
|Cog匹配训练效用|600条两arm任务持续生成；同基座/输入/噪声设置、step1000适配器和301份编码均核验；逐视频解码和SHA收据|完整生成与物理观察未完成；首例LoRA画面稳定不是总体物理提升证据|
|H3训练链路|四卡正式训练继续；checkpoint100、1200次实际呈现及精确输入顺序已核验，416个adapter张量保存；四份优化器分片元数据与抽样张量检查通过|完整预算3780步未完成；实际文本含27次已登记时钟补充。预览与训练loss均不证明物理提升，固定预算后的匹配生成和独立评测仍待闭合|
|摩擦响应补充|6摩擦×3prompt×两arm共36条完成；全量SHA、解码、规格与18组配对输入核验通过|机器事件预评与人工复核；仅一个物理上下文，不作新场景泛化或独立样本CI|
|几何/阻尼信息对照|36条生成及解码核验完成，连同摩擦组共72条|增加已知物理信息的对照，不是纯字数效应；独立人工复核待取得|
|补充实验预评|质量与事件各72/72完成；7人人工包已完成分配，5人各24条、2人各12条，每条双人|人工0；VLM世界坐标事件未标定，不能直接计正式准确率；视觉辅助字段不能替代正式指标|
|公平训练预算|Cog1000步×global batch12=12000次呈现已预登记；Cog/Hunyuan顺序文件SHA相同|Hunyuan实际global batch10，并有早期批次带来的样本游标偏移，不能把1000步写成同样12000次；按runtime的samples_seen核算，仍需独立同基座Base，不混旧step-distilled库存|
|Hunyuan恢复|从checkpoint70恢复后已实际越过74步旧失败点，checkpoint80结构核验通过；新快照1793493393到97步，五rank仍存活|完整预算4534步未完成；global batch10与预登记batch12有偏差，须如实区分；不把重放的未保存步骤当新增独立呈现|
|最终检查点|预登记Cog最终3780步追加对照|等待最终检查点；不按Core100择优改步数|
|主稿和反演|找到本地dataset_description.tex及旧开发结果，旧Overleaf链接到登录页|完整主稿/参考文献和新PhysProbe轨迹、投影、可复算结果工作区尚未取得；旧开发成绩不能填新表TBD|

## 复核入口

均位于`review/cvpr_experiments_20261031/`：

- 统一运行：`INDEPENDENT_SERVER_SNAPSHOTS.json`、`independent_server_snapshots/`；旧全量证据另见`LIVE_EXECUTION_SNAPSHOT.json`、`execution_snapshots/`。
- 主对照：`cog_matched/SCORING_PROTOCOL.json`、`MATCHED_BUDGET_PREREG.json`、每arm的`RECEIPT.json/results.jsonl`。
- T05：`critical_t05_friction/TIME_ORIGIN_RECOMMENDATION.md`、`T05_C03_PHYSICAL_CLOCK_V4_RESULT.json`、`GAP_PHYSICS5_LAUNCHED.json`、`physical_clock_endpoint_validation_v1/`。
- 补充实验：`controlled_friction_sweep/GENERATION_COMPLETE_VERIFICATION.json`；两组各有`EXPLICIT_WAIT_CLOCK_AUDIT.json`。23/30秒等待按有效物理过程换算后，末帧153/208，所选六点标签均未改变；冻结生成文本不改写。
- 补充预评：`auxiliary_review/POLICY.json`、`REVIEW_PROTOCOL.md`、`QUEUE_LAUNCHED.json`。全部质量路由均做事件观察，不据机器拒绝删除视频。
- 完整72条匿名人工包及7人分工：`auxiliary_review/human_bundle_72_7254d6746d78/seven_reviewers/reviewer_packets.zip`。A–E各24条，F/G各12条，每条由两位不同观察者复核，共144次观察；不含私有映射、生成参数、仿真答案或机器预测。原正确36条任务ID与定义保持，避免重复计算同一观察者。
- 已完成36条匿名人工包：`auxiliary_review/human_bundle_36_7ad87afe65e4/human_only_review.zip`。12,726,043字节，36条包内MP4哈希逐条核验；不含私有映射、生成参数、仿真答案或机器预测，需两位独立观察者。保留正式事件阈值作为判据定义。原8c1975040edf包因将目视完整通过误写为正式gate_passage，已标记SUPERSEDED，不用于正式事件标注。
- 独立质量验证与参考可判性：`independent_review/human_only_review.zip`、`reference_rgb_review/human_only_review.zip`。前48条加后5条，每条两人，共106次观察尚待取得。
- H3来源保全：`h3_queue_recovery/h3_preview_initial_base/`。Base收据已另存，避免后续同场景LoRA收据覆盖其来源记录。

## 计分边界

原视频、已提交prompt、原标签与旧实验收据保留。生成侧始终从首帧计时，不按开始运动时间重置时钟；原生窗口不足不以补帧、慢放或循环弥补。机器不确定、未复核标签、未准入参考、执行失败和确认生成质量失败分别报告，不能统一填0或悄悄删掉。

两HF数据仓库在本次认证审计时为private，未改分享权限。完整稿件与审稿入口仍需核对。相关研究与官方投稿要求见详细审计；不宣称首次物理参数或反事实视频benchmark。

补充预评v2保留正式gate_passage的质心世界坐标判据，以及独立的visible_full_clearance定性辅助字段。缺少标定的VLM/人工观察不能直接产生正式gate_passage真值，后者也不得映射为NearAcc/PairAcc。原v1等待监督在任何推理前确认并停止，代码与协议保全，未产生预测；v2监督重新登记，生成任务未中断。两组均另存SCORING_ELIGIBILITY.json，维持正式计分待定。

T05相机与测量敏感性：5例原相机信息已找回；C03初帧无偏移拟合的物理框/简单暗区框IoU约0.83。原渲染两端点在5秒截止帧的中心投影相距约3.47原生像素（512宽约2.08像素）；这不是RGB坐标反演结果。正式测量仍需验证相机稳定性、物理中心定位与误差，详见`critical_t05_friction/T05_CALIBRATION_FEASIBILITY.md`。

为继续做源像素测量验证，已单独启动`critical_t05_friction/native_pixel_control_v1`一次C03原参数/原相机/原seed回放，仅在隔离副本启用视频保存；冻结参考未替换，未来产物须核对原状态差异，不能冒充原发布视频。

T05新增数值候选见`critical_t05_friction/T05_PHYSICS5_NUMERICAL_CANDIDATES.json`：C03归一化距离约[0.002464,0.003696]，为Near候选；C05为Far候选。C04旧raster区间已隔离；原渲染恢复区间为[1.1432031249999999,1.1434716796875]，正端点独立复测通过（5秒窗最大手机位置差约5.15微米）。其归一化距离[0.440758,0.444323]与C05至少相差0.212601，超过0.02配对容差，故这两例不能作为距离匹配的PairAcc对。此文件不修改正式登记；原渲染边界、坐标测量及窗口准入分别核查。

其余17项已按已有profile逐项核对，见`REMAINING17_RECONCILIATION.md/.json`及远端结果哈希复核。特别是CPU64质检通过与GPU32质检失败记录并存时，不跨后端覆盖来源绑定。C04旧raster区间不可直接移植；新原渲染曲线及独立正端点复测已保全，更新数值候选但不修改正式登记。

C04恢复使用`gap_original_render_recovery_v2`：已对实际首个探针配置逐字段比较，渲染字段仅save_first_rgb/save_last_rgb/save_video路径与write_video开关不同，物理对象、scene_overrides和原seed保持一致。v1中沿用快速扫描采集覆盖的诊断已单列保留并停止，不拼入v2曲线，也没有证明这些选项就是差异原因。H3正式训练已有第19步快照，完成数以最新progress为准。

## 存储恢复及本轮闭环证据

SG磁盘满导致Cog全量训练在1829步停止。95个训练产物（26,174,955,671字节）逐文件校验后迁移到NVMe，原training路径通过符号链接保持，全部检查点保留。1750为最近完整检查点；恢复时核验optimizer/scheduler、三rank随机状态、adapter、训练顺序和固定清单，再撤销本次迁移创建的专用hold。已确认三rank进程及1751步更新，最终预算仍3780；重算79个未保存更新，不修改主对照step1000。凭据见`h3_queue_recovery/feature_transport/COG_RESUME_PREFLIGHT.json`。运行时清单相对原始清单仅省略编码器/训练器不读取的parameter_facts和external_control_inputs；45,357条其余字段逐项相同，保留原始清单和历史哈希。

72条补充视频的质量及事件预评均已完成（各72/72、格式状态均ok），人审0。未标定的正式事件输出14个no、41个not_observed、17个uncertain，全部仍无正式计分资格；独立视觉辅助字段也不能代替世界坐标事件。见`auxiliary_review/MACHINE_PREANNOTATION_REPORT.json`。机器质量拒绝仅为复核候选，不能删除样本或作为准确率。

## Hunyuan训练预算偏差核查

p21现行Hunyuan训练已转五卡/global batch10，当前活动输出为hunyuan_formal_baseline_20_1793461585，进程与五个worker已核验。续训链先用batch12完成10步/120次呈现，再沿batch10的20步检查点、12步原baseline性能测试检查点续训；被拒绝的性能优化分支未接入现行权重。第39步累计410次呈现；按当前路径第1000步仅10020次呈现，不能称预登记的12000次呈现复验。理论第1198步为12000次，但学习率更新/批大小不同，单纯改检查点名称不能恢复原协议。保留原预登记及当前训练，差异见`HUNYUAN_RUNTIME_BUDGET_AUDIT.json`；第二架构严格预算复验仍待补足。

已启用只读CPU出片核验：逐条SHA、原生帧数/分辨率/FPS/时间戳、实际prompt与条件图绑定及Base/LoRA配对。几何组36/36通过；主对照随新视频增量检查至600条，核验收据为各组`EXPORT_INTEGRITY_VERIFICATION.json`。该核验不能代替物理事件评分。

## 主对照质量预评已并行接入

`matched_quality_review`按全部600个已登记输出运行scene-integrity-v2质量预标注。仅选择双arm均通过独立出片核验的现成视频，每批最多64条；每条完整8秒中均匀13帧，不读取生成prompt、参数、仿真结果或模型身份。目标为原前景参与对象和直接支撑几何，不要求满足任何预测物理结果。首批64条已在p25 GPU1执行，首条预测完成、状态ok、13帧覆盖0–8秒、视频哈希与任务绑定核验通过。两arm生成worker继续在GPU4/5运行；预评以GPU1/2空闲门槛和共享lease申请，不停止其他任务。

该批为机器质量候选，不是新的独立评价器验证。全部视频保留，错误物理不自动作为质量拒绝，也没有写入生产人工标签。当前事件/临界/反演计分仍受各自准入条件约束。策略、启动和首条证据见`matched_quality_review/POLICY.json`、`QUEUE_LAUNCHED.json`、`FIRST_PREDICTION_VERIFICATION.json`；持续运行状态纳入统一快照。

## 固定最终检查点对照已接入等待队列

已按原`MATCHED_BUDGET_PREREG.json`启动本地等待进程`cog_final_queue.py`，具体PID与命令核查纳入统一快照。等待SG训练completion与checkpoint-003780收据；不会以训练进度文件替代最终权重。权重生成后逐文件哈希、canonical/inference 504个张量精确一致验证后复制；固定原300个输入、seed0、3prompt及原生生成设置，新增最终LoRA视频300条，复用原Base300条。p25执行器另等原600条全部生成结束和GPU4/5空闲，不停止任何现有任务。当前仅等待，未完成最终训练、传输或扩散生成。

`cog_final_epoch/QUEUE_PLAN.json`保存原预登记/输入/父代码哈希；`WORKER_STATIC_VERIFICATION.json`确认生成代码仅变更固定检查点与arm字面值，反向替换与原代码完全相同。最终结果仍需独立质量、事件与计分准入。

## Core100逐条清单

当前可复核的逐条入口为`review/cvpr_experiments_20261031/CORE100_EVALUATION_CHECKLIST.md/.json`：100条均有观察定义；登记距离84、待补16；登记准入参考2条、配对1组。原`REMAINING17_RECONCILIATION`保留为此前17项的历史审计，不覆盖此最新逐条清单。T05_C03新增的是完整条件后6.833秒窗口的登记距离；本轮有效物理5秒候选单列，不能混算。冻结标注快照的1377个缺槽也逐条列明，不当作本轮新增生成的人工标签。

已区分known_conditions中的source_video_sha256（原始来源）与reference.sha256（当前参考）；15条时间戳修正与6条已封存参考版本均按当前reference查绑定，不能只按原始来源哈希比较。6条封存参考已下载固定修订并核验视频SHA；与冻结条件图的frame4在两个解码器下均非逐像素一致，ffmpeg平均RGB差0.253–0.432/255、尺寸一致。该差异不能单独证明场景/参数改变，也不能代替条件图来源绑定；原图、生成输入、数值台账未修改。比对记录见`REFERENCE_CONDITION_AUDIT.json`。

## 当前训练时间预算实测

同一存活运行段核算：Cog1755–1829步约15.89秒/更新，按当前速度完整训练剩约8.61小时；H3第1–24步约266.42秒/更新，完整训练剩约277.97小时；Hunyuan五卡batch10正式支线39–45步约225.43秒/更新，完整训练剩约281.09小时。这些含实际缓存等待和共享资源影响，不是完成保证，人工复核与正式计分不包含在内。原进程、预算、学习率与检查点选择均未改变。详细测量窗口见`EXECUTION_RATE_AUDIT.json`；出片时间另按每arm最近10条收据计算，见`GENERATION_RATE_AUDIT.json`。

## Cog缓存生产恢复与时间预测更正

恢复训练到1829步后等待下一批缓存，两个原缓存生产进程均已退出。实测一份149,524,872字节缓存的image张量仅含1,769,472字节有效元素，但背后storage保留143,327,232字节的81帧原像素。此前按计算阶段估的8.61小时已失效，原测量保留但标记不可用于当前ETA。

旧cache约3TB、22748份缓存和旧text_cache全部保留原文件inode/字节。通过原子目录交换建立NVMe写入覆盖目录：已有文件仍逐项链接原目录，新缓存和文本文件写NVMe，不迁移3TB或删除原件。两个原prepare_full编码器通过封装恢复，仅在保存时将张量写入最小storage，并精确保留shape/dtype/stride和值；原编码代码SHA不变。单份测试压缩至7,966,796字节，所有元数据与固定RNG潜变量采样结果逐项精确相同。训练器与权重不重启、不改数学。预检/启动见`h3_queue_recovery/feature_transport/COG_CACHE_COMPACTION_PREFLIGHT.json`、`COG_CACHE_OVERLAY_SETUP.json`、`COG_CACHE_PRODUCERS_LAUNCHED.json`；须观察新缓存和新优化步再确认供给恢复。

缓存等待期间原DDP随后发生600秒ALLREDUCE超时，旧launcher2126444及三worker已由elastic退出；没有将存活的进程当作继续更新。核验已终止和两个新缓存生产器确实出片后，从同一1750完整检查点重新恢复，三rank/globalbatch12及训练数学不变；旧失败日志、launch/status收据另存。新launcher2711910的步骤必须由本次launch之后更新的progress确认，收集器增加progress_from_current_launch，避免加载期间把旧1829步误报为新进度。

## T04独立时钟核查与原渲染控制

本次核验的T04_C01/C02静态前导为24帧（不同于已核验T05的27帧），每有效状态录于物理步进之后；条件帧4与静态末帧23的全对象位置、姿态在10个哈希核验CPU64/profile1探针中一致。有效物理5秒候选为24–173帧，原条件后5秒仍5–154帧；现有协议未改。T04_C01五个唯一速度点在三窗口均0；T04_C02速度0.10处原窗0、物理5秒/完整窗1，0.125及以上四点均0。0.10处can2/mug接触第146帧已发生，但原窗最大位移0.0247004米，物理5秒窗达到0.0449210米，跨越既有0.04米阈值；不是修改阈值制造翻转。

此为已有CPU轨迹读回，非原渲染复现。已在`critical_t04_clock_v1`启动原raytracing/854×480/原seed控制：先对照发布参考原点0.15，初态和事件通过后才跑0.10/0.125两端点。实际配置对比仅改输出路径和write_video；保留原动态对象、场景、控制力和渲染参数。配置来源是已核验发布state header的重建，原独立config文件未认证，继续保留该限制。粗区间、距离候选另存`T04_PHYSICAL_CLOCK_CANDIDATES.json`，不加入当前84/16正式台账，也不把T04_C01有限无翻转宣布不适用。

## 标注增量核查与T04端点反证

标注平台只读新快照3600任务，当前3425 resolved。按同一seed0、非替换T19、输入/视频/协议身份及终审规则计算，质量终审2244条，比旧冻结2223多21条，缺槽降为1356。新快照、SHA、增量任务ID和当前计分结果保存在`annotation_refresh/`；旧annotations_snapshot.json.gz SHA仍为6f8bd38c6112b9ab44f547c88c6b15414f350c34369df8472410701dccc8a7e9，118条帧密度实验的金标与选择不改。新记录不自动成为独立人工gold，也不转移到本轮新生成视频。NearAcc/PairAcc仍N/A。逐条清单新增当前/原冻结两套覆盖字段。

T04_C02原光追0.10端点的registered_condition5/effective_physics5/full_existing均0，未复现CPU64的物理5秒阳性，因此[0.10,0.125]及其距离已隔离，不再作为有效候选区间。原CPU轨迹读回证据保留；0.125端点继续完成原定控制。当前正式84/16台账不改。

T04三个原渲染控制现已完成：0.10阴性、0.125阳性、0.15阴性（有效物理5秒及完整窗）；原条件5秒均阴性。原CPU正负粗区间继续隔离，不和原生数据拼接。原生结果出现两个相邻翻转方向，不能假定全域单调。已在`critical_t04_native_refinement_v1`启动有上限的原生补算：先独立重复0.125完整事件向量，若不一致立即停止；通过后分别二分[0.10,0.125]和[0.125,0.15]，tolerance0.0005、最多新增13探针，原seed/场景/渲染/物理对象固定。所有三个窗口均记录；不宣称全局最近临界值，不改当前输入或成绩。

Cog缓存恢复已越过旧1829步边界：同一新launcher2711910在1831步、三训练worker及两个缓存生产器存活，恢复后539份缓存已出片。证据见`COG_CACHE_FRONTIER_PASSED.json`，这是当前供给恢复的实测证据，不代表最终训练完成。

T04原生0.125重复门槛未通过，补算器按预设在1个新探针后终止，未执行二分。两次配置仅输出路径不同、同random_seed1212927170、初态位置完全相同；首次满足full-chain判据分别在155/179帧，即有效物理4.4/5.2秒。物理5秒位移45.637/37.582毫米，完整窗48.231/40.189毫米；因此物理5秒标签1/0，完整窗均1。此证据不能唯一归因于GPU数值非确定性，不能从同seed推定标签稳定。物理5秒候选继续待定，也不据两次完整窗同1自动改主协议。新`critical_t04_original_grid_extension_v1`仅补原0.1–0.2域尚未测的0.175/0.2两个原生粗点，主观察仍原5–154帧，不重启失败二分、不改原阈值；最多2个新探针。

补充核查父项目已有质量评价器证据：V3/V4历史fresh64共有15个clip/14个登记来源组，与其原200开发集85个clip不相交；但与本轮帧密度AB重叠8个来源组、scene-v2开发pilot重叠2组。32个failure标签均未注明细分缺陷，所以不能拿这64条替代当前scene-integrity-v2四类缺陷的独立gold。V4 combined历史二值质量一致率70.3%、正类召回50%等结果保留为已有效度证据及过拒风险，不重新命名成当前v2准确率；详见`RELATED_EVALUATOR_EVIDENCE.json`。


## Hunyuan缓存缺供恢复与T04原窗口粗扫描收尾

Hunyuan原正式运行在58步发生600秒ALLGATHER超时后已终止，旧日志和checkpoint保留。p20奇数特征进程此前停在global601，603起缺供；保留存活的偶数进程，在空闲GPU1上以原编码代码、原local-cache模式恢复奇数worker，从603开始，只跳过已存在缓存。不改变编码数学或已保存特征。恢复进程7305已核验实际命令与存活；新特征仍需实际产物验证，启动不等于恢复成功。

p21已验证checkpoint50五rank runtime一致、samples_seen520、scheduler/scaler及五份分布式状态分片齐全。恢复控制器20377预先读取并验证520–639共120份特征的来源、prompt、manifest、有限值与文件哈希，再在原五卡均有显存余量且无其他Hunyuan训练器时启动；保持world5/globalbatch10，从50重放未保存的8次更新，不覆盖旧58步日志。当前原五卡可用，特征已核验101/120，训练尚未重新启动。原训练器不保存RNG状态，不能声称与不间断训练逐位相同。入口`HUNYUAN_FEATURE_RECOVERY.json`与`h3_queue_recovery/resume_hunyuan_after_features.py`；统一快照增加源特征进程、恢复控制器和缓存等待状态。

T04_C02剩余原生0.175/0.2两探针已完成，state压缩字节和解压raw SHA逐项符合RESULT。两点三个窗口均阴性；结合既有0.10/0.125/0.15，原registered_condition5五点全阴性，没有观测到可用于原协议的翻转。有限网格无翻转不证明全域无临界点。effective_physics5的0.125曾阳性但独立重复失败，仍不准入。证据`T04_ORIGINAL_GRID_COMPLETION.json`，当前84/16距离台账、2参考/1配对不变。


## 当前scene-v2的80视频盲审队列

已冻结不按结果筛选的80视频质量验证集：T01–T20每类C01/C04，prompt1、seed0、Base/LoRA1000各40条。两位不同观察者独立复核每条，共160次观察；沿用七人分工，A–E各26条，F/G各15条。该子集在部分输出已生成后登记，选择规则未读取VLM判断或物理成绩，不能称生成前预注册或未见物理来源的独立测试。当前已有38/80条通过文件与原生导出验证，等待其余选定输出；队列PID1544757已核验命令存活，不重复生成视频、不调用新API。

包中仅含随机顺序的匿名视频、四类缺陷定义与空模板，不含模型身份、参数、仿真答案或VLM预测；协调者关联表另存。生成视频首帧作锚点，匹配当前机器质量策略；不能以该验证证明条件图一致性。人工完整8秒视频对机器13帧比较同时包含采样差异，报告时须分辨。未收取人工记录，不报告gold或准确率；分歧需另裁定，不自动转写线上平台。计划与实际队列见`matched_quality_human80/SELECTION_PLAN.json`和统一快照。

Hunyuan恢复后第603份特征已实际生成15,878,844字节，p20源缓存与p21训练端SHA完全一致；见`HUNYUAN_FIRST_RECOVERED_FEATURE.json`。这是供给恢复证据，仍需等待120份预备输入齐全及真实训练更新。


## 反演实现版本与实际时钟诊断

当前latest_results登记的8个实现SHA中7个精确相同，motion_parameters.py与其冻结050366e4版本不同：c46214c8只在摩擦时间基中新增initial_time_s，保留初态到首个观测的真实时间差；默认路径仍等价。没有修改代码或旧开发成绩。四份登记原结果SHA在本地docs/scripts里均未找到对应原文件，不能单凭汇总表宣称已完成全量复算。审计见`INVERSION_IMPLEMENTATION_AUDIT.json`和精确差异补丁。

实际跑完540次已知解析真值的时钟/噪声对照：3上下文×6延迟×3噪声×5重复×2实现。全部拟合ok；无噪声时0.5秒错置使旧路径平均误差43.667%，1像素噪声下44.149%，保留声明初态时间为2.047%。此为同方程正反算的数值诊断，不能作为独立真实视频准确率或Core100成绩。无噪声五次重复是相同输入，不据此扩大独立分母。设置/逐例结果/汇总见`friction_clock_diagnostic/`。

现有相关回归89项：74通过、15失败。失败为12项旧Gravity100 caption fixture和3项自由文本参数fixture被新的英文结构化prompt合同拒绝，不是本轮修改的回归。没有放宽生产输入门槛或改写冻结prompt让测试通过；时钟、评测入口与旧fixture迁移需分开处理。


## 已交付首批40条盲审包与T17事件队列

80条冻结验证集已有40条视频通过完整性验证，已实际封包、下载、逐层ZIP及媒体SHA复验：`matched_quality_human80/ready_40_16c74cd4e21b/reviewer_packets.zip`（25,529,661字节）。A–G首批分别12/14/10/15/11/8/10条，共80次独立观察；完整80条分工仍A–E各26、F/G各15，首批是该固定分工的就绪部分。每条两位不同观察者，标签均未填；包内不含模型名、物理参数、仿真答案或机器预测。后续按(sample_id,reviewer_id)去重，不重复累计。尚无人工提交，不报告独立gold或清理准确率。

另已实际启动T17已准入两案例的匹配事件等待队列1675449，覆盖Base/LoRA1000、3prompt、seed0共12条；不改变原生成顺序或再生成视频。等待这12条原生8秒输出通过文件/输入检查后，复用现有Qwen3.5-9B与共享GPU1/2租约，24帧独立判断can_tissue_box_contact，原观察窗6.4秒，不送参考分支答案和参数。16fps最后窗内帧为6.375秒，边界尾隙0.025秒和稀疏采样的不可判保留，不能强行给no或将迟到接触挪进窗口。输出仅是待人工复核的观察，不自动形成NearAcc/PairAcc。当前12条尚未生成到该位置；状态见`t17_matched_event_review/POLICY.json`及统一快照。


Hunyuan在120/120份预备特征全部核验后，于1793476797从checkpoint50实际启动五rank续训：launcher38914，workers38942–38946，输出独立目录`hunyuan_formal_feature_recovery50_1793476797`。checkpoint适配器SHA为dbc1aefdfd884995c112c11e21d99a65fa2071fef8fb2b053ad68e51d9c73144，样本520–639的120份绑定/有限值/文件哈希见`HUNYUAN_RECOVERY_PRESTAGED_INPUTS.json`。五个实际进程已核验，仍处加载阶段时不把旧58步当新进度；须再看到新目录中的真实optimizer更新才确认训练供给闭环。


## T17三条参考：绑定已补证、瞬时事件采样风险

T17_C01/C02/C03的发布视频、压缩/解压状态SHA、原干预值和固定物理上下文均与登记源逐项一致，已取回原文件。三个冻结条件PNG与原生FFmpeg第4帧RGB逐像素相同；OpenCV解码最大相差2级/255是此处解码路径差异，不能当作输入版本更换。原窗5–154帧、30fps不变。读取证据见`t17_reference_admission_readback_v1/READBACK.json`和`NATIVE_VISUAL_AND_BINDING_AUDIT.json`。初版联系帧图用了854宽排版但源为1280宽，不能用于视觉结论；已保留原图并另生成按原生尺寸的contact_sheet_native.jpg，实际检查采用单帧原图。

C02原生接触仅在第31帧记录，13/24帧均匀网格都没有直接采到该帧；C03有持续接触，C01没有目标接触。该网格相交诊断不等于实测VLM错误率。已经实际启动3条参考×13/24帧共6次事件控制（队列1760754，13帧worker1762758），不送参考答案、保持同一目标定义。参考片段只截取声明条件帧4至154，151帧、30fps、原5秒时域；FFV1解码帧MD5与原段全部相同，不按运动开始重新计时，也未改任何生成视频。结果仍需收取。

三条读回不是新的正式边界准入：原seed局部端点复现和参考RGB可观察性接受尚未闭合，不能将不同重力上下文当配对；当前2参考/1配对保持。逐例清单已把这些案例从泛化缺项细化到实际已核验和待核验项。

Hunyuan新输出目录已实际更新到52步（恢复点50）；world5/globalbatch10、manifest、scheduler恢复收据一致，1312个非零梯度张量。已完成两次真实更新，但尚在重放旧运行未保存的8步，必须越过旧58步、经过缺供位置后才报告已越过原缓存瓶颈。


## T17事件控制完成：原始输出揭示格式故障

3参考×13/24帧共6次推理已完成，原始文件精确字节取回至`t17_reference_event_density_v1/remote_originals/`。6条均返回了事件判断，但遗漏顶层events，旧适配器因此全部标记evaluator_failure。未重新推理，只在键集合与登记事件完全一致时恢复缺失包壳：6条可恢复，原严格时间校验仅5条通过，另有2条没有时间证据。24帧C01输出时间四舍五入，不放宽原时间校验；所有原始失败状态和数值保留。13帧对C03给no、24帧给yes；不能据这3条控制写“24帧准确率100%”。C02两档虽给yes，引用时刻却早于原生接触记录，标签一致不证明接触定位可靠。详见该目录REPORT.md和OFFLINE_SCHEMA_REPLAY.json。

已修复当前代码的严格事件包裹恢复：只接受完整、精确登记键集合，不改标签、时间、理由和置信度；推理/校验失败前保存实际供给帧、时间及图像哈希。新增事件包裹与现有场景质量共19项针对性测试通过。没有覆盖冻结质量评价器源或已完成预测。

未来T17匹配12条事件队列已切换至独立`t17_event_source_v2`源。旧1675449进程仅在核验仍等待0/12、无GPU子进程、无预测后退出，留SUPERSEDED记录；新1806561队列实际存活，仍等待生成，未重复推理。活动指针`t17_matched_event_review_active.json`，统一快照跟随新指针。质量600条任务继续使用原冻结源，不因事件格式修复重新跑。本轮未写生产人工标注或正式物理成绩。


## 主事件预标注已实际运行，数值/顺序逐项留待测量

固定100条原主事件逐项核对：47条含可交VLM观察的非数值事件，60条含需独立标定/数值测量的判据，两类重叠7条；53条没有可单独交VLM的非数值主事件。T13五条派生接触逻辑与T19五条登记顺序均留待人工确认，不由两个yes推定先后。没有增加替代事件或改原阈值。逐例见`matched_primary_event_review/CASE_ROUTING.md`。

已实际启动270条已有生成视频上的事件预标注（45案例×3prompt×2模型），另有T17两案例的12条既有队列，不重复推理。采用隔离的格式修复源、24帧、现有Qwen3.5-9B、GPU1/2共享租约；没有因机器质量拒绝删掉视频，也没有将数值判据交VLM猜测。首批32条实际完成，32条结构有效，7条使用精确登记键包裹恢复；62项事件中58项缺时间证据，均保留人工复核，不能把结构有效当成事件可靠或正式分数。原始输出、收据、媒体/定义哈希及审查清单已取回`matched_primary_event_review/batch_001/`。后续批次仍运行。

100条输入的实际prompt哈希均与冻结要求一致。21条输入元数据引用原始来源视频哈希，活动参考则使用另外的时间修正/封存版本；已将两种身份分别保留，不把来源哈希冒充活动参考，也未重写已提交输入。本队列只提供生成视频观察；参考/边界/时域及最终评分仍走独立准入。

Hunyuan已实际越过旧58步及缺失global603位置，60检查点五rank runtime一致、分布式状态齐全、适配器SHA相较50步已改变。恢复后100个训练样本的顺序、来源SHA与冻结allowlist逐项一致，确实消费了603。收据`HUNYUAN_CACHE_FRONTIER_PASSED.json`。这是恢复训练闭环，不是完整训练或物理成绩完成。

统一采集器现自动刷新每案例的生成/完整性覆盖及事件预标注格式、缺时间证据计数，逐条清单同步这些信息；不再靠旧静态库存推断当前完成数。


### Seed 0 primary-table workorders (snapshot 1793472550.5809562)

Recomputed all 3,600 desired slots from the pinned annotation snapshot, keeping task IDs and labels intact. `review/cvpr_experiments_20261031/seed0_workorders/README.md` and `MISSING_SLOTS.jsonl` partition 1,356 unfinished slots into 1,044 missing seed0 tasks, 132 existing seed0 tasks pending final quality, and 180 new-input T19 generations. 2,244 existing final quality records are not event scores or independent gold. The historical media locators require byte/input verification before admission; no platform import or new inference was performed by this workorder build. Newly trained Base/LoRA comparisons are a separate experiment and do not fill the 12-model baseline table.


### Seed0 missing-task media bound and CPU verification launched

Pinned HF metadata at revision65a65b26a37d4ceb7dc2b0273f0382e842df888e matched the recorded full SHA. All1,044 missing-task candidates now have exact actual-submitted prompt SHA, condition SHA, LFS video SHA and native metadata bindings. Total candidate media426,211,447bytes. All declared native windows cover the task windows; actual byte/decode verification is a separate running CPU job, PID2105297. Live snapshot verifies the command identity; no training GPUs or production task writes. Existing T19 new-input180-task queue recovered in review/core100_completion_20261031/t19_generation; no duplicate generation launched.

25 protocol-template conflicts traced to existing5s versus registered4.1s versions. A separate resolution manifest reuses exact existing4.1s protocols for170 affected T06/T09/T10 candidates; all event definitions compare identical after removing only version and observation-window-binding fields. All25 conflicts covered. Old tasks/labels and the running media manifest remain unchanged; no event scores claimed.


### Existing scene-integrity-v2 supplement actually dispatched

Fixed all1,044 missing-task seed0 media into the existing13-frame/Qwen3.5-9B/scene-integrity-v2 preannotation pipeline, with exact frozen source hashes, no answers/prompts/model identities passed to the judge, native windows and registered4.1s overrides. Supervisor2133512 and first64-video worker2133515 are both live with matching commands; the first worker has no completed predictions yet in this snapshot. Uses existing shared GPU1/2 idle-memory and flock leases; does not take the Cog generation GPUs or force other workloads off their GPUs. Every output remains a machine review candidate, not independent gold, deletion authorization or a physical score. No production DB writes. Source-byte/decode verifier is separately live and at180/1044 verified with0failures. Collector now follows both exact process identities and batch output counts.


### T17 published endpoint source evidence recovered

Recovered15 unique original state files for T17_C01/C02/C03:3 source members and12 boundary endpoints spanning6 registered intervals. Exact compressed/decompressed SHA, intervention values, fixed context and original5s contact-window labels all pass. Archived SOURCE_EVIDENCE.zip hash640acc1681580d86d58613bf1a411b7ff4162c4005a1019d5f61edc1d0b56cac; downloaded and recounted contacts independently. No simulations were started and formal admission unchanged. The100-case checklist now records this evidence separately from original-seed resimulation and RGB acceptance still pending.


### T17 fixed-source-seed controls queued and media transport recovered

T17 original published endpoints use distinct simulation seeds from their Core100 source trajectories (exact per-point seeds recorded in t17_fixed_seed_endpoint_control_v1/PLAN.json). This does not alter generated-model seed0. Prepared and dispatched3 original-source canaries followed by12 original-speed endpoints with each case source seed held constant. Exact historical renderer hashes, Genesis0.4.1, original resolution/raytracing and native window are preserved. Supervisor2221996 is live with matching command, currently waiting for shared idle GPU1/2;0probes complete. Source event mismatch halts endpoint expansion. No formal admission or input changes.

The foreground media-verification SSH proxy disconnected and its original PID2105297 is authoritatively absent. Preserved550attempt records:484verified,66transport failures (1SSL,34readtimeouts,4connection,27proxy). These are not confirmed video defects. A task-local hidden tunnel supervisor31200 now reconnects, with a6hour bound and completion-triggered exit. Detached resume PID2235480 skips484verified media, appends recovery records and processes560remaining slots. First12previous failures recovered, yielding496verified/54remaining old transport failures in current snapshot. No VLM predictions or verified bytes were rerun. Existing quality worker still live,53outputs present.


### Native short-video eligibility and task-schema correction

Correction: matching170existing4.1s protocol versions did not establish that170videos cover4.1s. A second native-grid audit finds110covering and60short clips (DynamiCrafter17,PhysRVG23,VideoGPA20). WINDOW_ELIGIBILITY_AMENDMENT.jsonl pins all1044 quality windows and holds these60from full-window event admission. Scene-integrity quality may still be reviewed on their existing native task windows; no retiming or full-window physical score is inferred. The original quality queue completed64outputs, allformatok, then its coverage assertion stopped before any unsupported-window inference. Those64exact predictions have been SHA-verified and reused by quality_preannotations_v2, PID2271941, rather than rerun; active pointer and collector updated. No original output/manifest/policy was overwritten.

A real schema mismatch also surfaced: recover_remaining_contracts deliberately registers minimum_evidence_times0for label-only protocols, while workflow.validate_task rejected0. Fixed that local task-import check to accept nonnegative integer counts, preserving negative/noninteger rejection and every existing scoring/measurement gate.13workflow/media tests plus16subtests passed. Production site has not been deployed or relabeled. Of the pinned590verified-media snapshot,573task payloads pass the actual existing form validator and17are held for short native duration. Owner inheritance is provisional; no partial formal batch was imported because current formal importer requires the full3600-slot roster and quotas.


### Complete missing-task media audit and input-regime comparability

All1044missing-task seed0 media now pass exact byte identity and full native decode. Original66transport-failure rows preserved; latest unique outcomes1044verified/0failed. Local snapshot cross-check confirms1044unique video SHA identities and exact metadata frame/fps bindings. Tunnel exited automatically on completion.984schema-valid payloads are staged,60held because the explicit4.1s protocol exceeds native duration. Schema-valid partial observations are not formal full-window event eligibility. Nothing imported or relabeled.

New experiment_comparability audit checks all3600original seed0 slots and300matched inputs: among285nonT19matched inputs,93prompts exact/192different, and285condition images exact. NewT19has15changed prompts/images as approved. Old main-model inputs agree across models for each case/variant; newBase/LoRApair uses its own pinned manifest and8s settings. Direct cross-cohort score substitution is disabled in the audit. Main native metadata also shows DynamiCrafter1.5s,PhysRVG3.2s,VideoGPA3.333s cover0/285nonT19registered horizons; Cosmos3covers285/285, standard5s profiles264/285, LTX6.4s270/285. These are necessary metadata coverage counts, not scientific admission.

T17 first-probe reservation superseded the owned waiting supervisor2221996 only after verifying0probes, no renderer child and waiting status. Replacement2344192 has identical plan SHA and is live waiting on the shared GPU1 lease; no active worker was interrupted. It will acquire the next release before starting the first source control, then use the original memory/lease scheduling. Source config, seed, renderer and conditions unchanged.


### Hunyuan checkpoint70 supply recovery and paper protocol fragments

Authoritative failure found: the recovery50 trainer stopped at74with NCCL600s ALLGATHER timeout; all old launcher/workers absent. Worker0 source log records CUDA OOM while another1.12GiB process occupied the device; cached even frontier760, odd worker7305continues. Complete checkpoint70has identical5rank runtime records, samples_seen720, scheduler/scaler state, adapter and5distributed shards. Two existing-code even encoders52172/52173 were dispatched on free p20GPU2/3 with nonoverlapping worker0/4 andworker2/4 partitions from762; oddworker1/2 preserved. Source code/precision/window unchanged, existing caches skipped; restart RNG is not claimed bitwise uninterrupted.

Checkpoint70controller pre-stages120exact features720..839 before5rank/batch10resume, replaying4unsaved updates. OriginalGPU5is now occupied by an unrelated user; only the owned waiting controller was retired before any trainer child and replaced by37544on same-SKU V100S slots1,2,3,6,7. No unrelated process stopped. Current status remains feature staging, not resumed optimizer steps. Collector follows active recovery pointer, includes all3feature workers, and prints real formal steps/liveness rather than stale pilot10.

T17_C01source actually re-rendered: original/reproduced contact0, maximum positional difference0.000064790687542m (diagnostic only); formal admission remains pending.

Updated docs/dataset_description.tex for fiveT19replacement and immutable actual input binding; added docs/evaluation_protocol.tex describing metrics, native windows, human/VLM roles, failures/coverage and within-experiment training comparisons. Both are working fragments, not the unavailable complete manuscript. Braces checked; no TeX compiler available. Official native-duration source audit saved in native_horizon_recovery; twoT19C01native frame-count canaries prepared, not launched while original runtime/adapter paths remain unknown.


Checkpoint70 recovery current verification: both restored even encoders produced their first new features (global764and762 respectively); odd source progressed to815. The recovery controller staged71/120validated features and confirms sufficient headroom on same-SKU GPUs1/2/3/6/7. The failed even frontier762has therefore been passed by the feature pipeline, but no resumed optimizer step is claimed yet.


### First187matched machine-quality pairs verified

Read-only diagnostic checks45complete batches against frozen inference receipts (quality scene-v2,13frames,1600tokens, exact source/manifest hashes and8s target).187complete pairs across63distinctcaseIDs:116both machine-unmeasurable,43unmeasurable-to-measurable,17reverse,5bothmeasurable,4unmeasurable-to-uncertain,2measurable-to-uncertain. No human labels, physical scores, balanced100case claim, CI or checkpoint selection. Timestamped local report at matched_quality_diagnostic/20261031T222812Z.

T17 remaining probes were again losing nonblocking GPU leases. Retired only the owned waiting supervisor2344192 after1completed source and0active children; immutable C01result/config/state hashes reverified and reused viahardlinks. Controller2487042 reserves the next sharedGPU1lease for each remaining probe, without interrupting the active GPUworker. Current C02original renderer2487502is actually running. Plan, seeds and renderer unchanged; no completed simulation repeated.


### Author clarification: external colleague generation

Author confirmed PhysRVG/VideoGPA original generation occurred on a colleague machine, not these servers. No further local-environment search or assumed local inference launch. Prepared an exact-input2task packet at native_horizon_recovery/peer_native_horizon_pilot.zip (SHA31a63a34aacb66405fd908beb857d1f6cc884dac4eda8f3fcf6314b09ecb70b3):VideoGPA169frames24fps andPhysRVG113frames15fps, bothnewT19_C01p1seed0. InputPNG and prompt bytes verified; actual original checkpoint/adapter/sampler/etc must be preserved and disclosed by colleague, not filled from localrunner defaults. Package includes results and provenance templates, remains unsent; no new inference claimed. Metadata provenance field audit retained separately: field absence in HF does not mean colleague configs absent.

Live T17source canaries3/3passed; fixed-source-seed endpoint phase has begun (1completed endpoint in snapshot1793485936). Hunyuan71-to101/120feature staging progressed; no recovered optimizer step yet.


### T17fixed-source-seed endpoint interim audit

Downloaded and verified all3source canaries plus7completed endpoint controls: exact state/config hashes, original source seed,210frame completeness, same5s clock and exact source physical context. Configuration comparison removes only output destinations and permits only the registered speed-axis intervention plus parameter metadata.3complete registered intervals retain opposite endpoint labels: twoT17_C01intervals (0->1then1->0) and the firstT17_C02interval. No changed complete interval observed in this snapshot. This supports locally registered transitions without assuming a single monotone critical value or ruling out hidden transitions. Case checklist updated; RGB/generated-label/formal admission remains pending.


Hunyuan actual recovery verified at optimizer76: five ranks consumed exactly the next60source IDs720..779 from checkpoint70, allsourceSHA match the frozen runtime manifest and excluded OOD scenes absent. Required1312gradient tensors allobserved. Former missing global762and old stop74are passed. No new durable checkpoint is proven yet; await complete80state. Receipt preserved at HUNYUAN_RECOVERY70_PASSED74.json. Overleaf authenticated-browser attempt timed out at tool layer and returned no manuscript; not treated as proof of inaccessible project or a completed manuscript review.

### Subsequent checkpoint and T17 resource verification

Checkpoint80 is now structurally complete: five identical runtime records agree on step80 and samples_seen820; five distributed optimizer shards exceed500MB each, metadata exists, and the adapter exceeds1GB. Adapter SHA256 is `20cffc3e39fb98475786731c16c71762d1c43a229cd029068f648cd43fc2f6fe`. Read-only receipt: `review/cvpr_experiments_20261031/HUNYUAN_CHECKPOINT80_CURRENT.json`; reproducible inspector: `verify_hunyuan_checkpoint80.py`. Optimizer tensor deserialization and bitwise uninterrupted replay are not claimed.

T17 v4 reuses all10 completed probes without rerendering and replaces the inherited VLM memory threshold with a renderer-specific12GB start/4GB abort policy. Other live GPU work is preserved. At snapshot1793489108,12/15 probes completed; actual owned renderer peak4654MiB, minimum observed free memory16035MiB for the completed new C03 probe. Local audit1793489132 verifies3 source canaries and9 endpoint controls, with4 complete opposite-label intervals reproduced and0 changed complete intervals. Three endpoints remain pending; RGB observability, generated labels and formal admission remain separate. Current numerical distance readiness remains84/100 and formal reference/pair counts remain2/1.

At the same execution snapshot, matched Cog generation has237 Base and214 LoRA videos (451/600); H3 training is94/3780 and Hunyuan80/4534. These are execution counts, not physical benchmark scores. External colleague native-duration pilot remains prepared but unsent and unexecuted.

### T17 endpoint control completed; reference review handoff ready

At local verification1793489601, all15 probes are complete:3 source reproductions and12 fixed-source-seed endpoint controls. All6 registered transition intervals retain their original opposite labels;0 complete intervals changed. Every completed config, seed, state hash,210-frame grid and5-second observation window passed verification. This closes the endpoint reproduction gap for T17_C01/C02/C03, without asserting monotonicity, unique critical values, RGB observability or generated-model scores. The100-case checklist has been regenerated with these completed gates removed from remaining work; readiness84/100 and formal references/pairs2/1 remain unchanged.

Three original frozen reference videos are packaged for two independent contact observations each at `review/cvpr_experiments_20261031/t17_reference_human_review/reviewer_packet.zip`, SHA256 `af890baeee4c5d7870b947704eca3a2b63dee72a705c12feeaae5273c758862c`. Each browser-compatible lossless clip retains original frames4..154 (151frames,30fps), with decoded pixel MD5 identical for every frame to the previously verified FFV1 window. The package contains anonymous IDs and no truth, parameter, model or machine-label fields; private source bindings remain in the receipt outside the ZIP. JavaScript syntax and ZIP integrity passed; browser rendering remains unverified. No reviewers were contacted and0/6 independent observations have been received.

### Updated wall-clock feasibility and observation gaps

`CURRENT_EXECUTION_FORECAST.json` supersedes the historical compute-only ETA for current planning. From20 distinct observations of the same live H3 run (steps70..97),27 updates took7095.8 seconds:262.81 seconds/update and268.87 remaining hours to the fixed3780-step budget if supply/rate holds (conditional UTC finish2026-11-12T04:25:36). Hunyuan same current recovery output, steps73..83, took2296.3 seconds for10updates:229.63 seconds/update and283.91 remaining hours to4534 (conditional UTC finish2026-11-12T19:29:22). These forecasts include observed waiting but cannot predict future supply interruptions; they exclude inference, human review and manuscript preparation. Neither budget nor learning-rate schedule was changed to fit the deadline. Hunyuan remains a batch10 budget-deviation experiment, not the preregistered batch12 replication.

Snapshot1793489711 verifies H3 four training workers, Hunyuan five workers and all3 Hunyuan feature producers live; supply acknowledgements are even980/982 and odd917 while the trainer cursor is850. This is sufficient recent supply evidence, not a guarantee of all future features. Matched Cog generation is241 Base+217 LoRA=458/600, and primary-event worker2929292 was actually live with a30-video batch after118 previous outputs. Such output counts remain machine observations, not human or physical scores.

SG observation failed in the collector and direct SSH subsequently timed out to the same172.25.72.115 endpoint. Cog training is therefore currently unknown and no current Cog training ETA is issued. A later p25 direct poll also timed out to the configured endpoint; this does not prove termination of its jobs. No process was restarted or duplicated because of either observation timeout. The latest verified per-process snapshot remains the evidence until a fresh observation succeeds.

### Gateway fallback recovered observations and23 additional human-review videos

SG direct access recovered. Its original Cog launcher2711910 and3 workers are live; snapshot1793490421 verifies step2367/3780 and both cache producers plus the H3 teacher encoder alive. Current same-run measured speed is35.60 seconds/update including supply waits, giving a conditional remaining13.97hours. H3 is100/3780 and Hunyuan86/4534 with their original current workers live. Matched generation is246 Base+222 LoRA=468/600. All are execution evidence, not physical scores.

Local direct SSH to the shared121.46.19.2 gateway timed out for all3 configured ports; an SG-side TCP probe connected to those same ports in8–14ms. `collect_independent_server_snapshots.py` now saves each host independently and, after a direct failure, supports SSH TCP forwarding through SG with target authentication remaining on the local machine. No key was copied, credential forwarded by agent, server configuration changed, task restarted or tunnel daemon installed. All4 server sections were freshly observed; transport route/errors are recorded in `INDEPENDENT_SERVER_SNAPSHOTS.json`. The historical monolithic snapshot is preserved rather than relabelled fresh. Forecasts now consume the independent snapshots, use trainer elapsed-time differences where available and invalidate missing-host projections.

The existing80-video frozen human cohort now has63 verified videos. A new immutable packet excludes every sample already in the first40-video package, preserving original reviewer assignments. The23 new videos require46 observations: A12/B6/C10/D7/E7/F3/G1. Local ZIP is `review/cvpr_experiments_20261031/matched_quality_human80/ready_23_5d15889268d5/reviewer_packets.zip` (14,060,447bytes; SHA256 `2ac388459502fb1555c441eff4ca39505624ffedfae8d98bdff4202de4f66ca8`). Both old and new nested ZIPs and every media hash were reverified locally; combined coverage is63 unique videos/126 observation slots, duplicate(sample_id,reviewer_id) pairs0, with no filled quality labels. Combined A–G workloads are24/20/20/22/18/11/11. The remaining17 videos still follow the frozen selection and existing live queue; no quality-outcome selection or new generation was introduced. No packet has been sent externally and0 independent observations have been received.

### T19 original-baseline regeneration gap clarified and exact-input handoff sealed

The earlier statement that the180-task T19 queue was recovered refers to a prepared work-order file, not a running generation supervisor. Its per-model plans explicitly say executed=false and the summary says actual_new_videos_generated=0. The local registered profile covers the209/30-second reference horizon for only15 tasks (Cosmos3-Nano);165 task profiles are shorter. This is a profile check, not evidence of a model's maximum capacity. Actual original peer-run checkpoints/adapters/sampling settings remain unconfirmed; local defaults must not be substituted as provenance. The separately running matched Base/LoRA experiment uses a different generation protocol and does not close these original-baseline slots.

Prepared `review/cvpr_experiments_20261031/core100_t19_generation_handoff.zip` with all180 tasks,5 initial PNGs,15 exact prompt files, per-model15-task lists and unfilled provenance/result templates. It excludes answers, known_conditions payloads, reference videos and future frames. Every task was independently checked against the active Core100 manifest `f9873e65845cf30cfeda72426eb72556beb4f71da0f2ca16ca17af3548ccd6bf`, including exact condition/prompt bytes and seed0. ZIP1,109,499bytes, SHA256 `00a9820ba824f0dc1485108fd3ec1109faa82f6359be02feb58e2a4f2bc7fa9e`; receipts `T19_GENERATION_HANDOFF_RECEIPT.json` and `T19_HANDOFF_ACTIVE_RELEASE_VERIFICATION.json`. Private source joins stay outside the ZIP. Existing two-task native-duration pilot remains the first execution check for PhysRVG/VideoGPA; no unverified duration increase, model download, paid API, external message or new180-task inference was launched.

### Completed quality evidence extended to320 outputs; GPU3 is unhealthy

Retrieved completed immutable supplement batches through the verified SG route, retaining prior64 predictions and all historical first128 artifacts. Local audit now covers320 unique outputs:128 machine-measurable,191 machine-unmeasurable and1 machine-uncertain, all320 evaluator status=ok. Nonexclusive flags: foreign_objects171, identity_loss80, geometry_corruption41, scene_replacement8. Availability-ordered prefix includes Cog84/DynamiCrafter114/Hunyuan63/LTX59; this is not a balanced sample, dataset failure prevalence, confirmed rejection count, evaluator accuracy or model ranking. All videos remain available and independent human adjudications remain0.

`seed0_workorders/CURRENT_COMPLETED_QUALITY_VERIFICATION.json` verifies every output/manifest/media identity,13 native-frame indices and timestamps, stored-normalizer replay, exact Qwen/source/scene-policy hashes, same inference prompt,1600-token budget and completed-batch receipts. Versioned input ZIP `completed_quality_artifacts_1793491121.zip` (SHA256 `9e4adc5ffcfad6c2e6e1fbefd5638ed7677d02ed4b5a1cf5e316df9123cca08f`) retains25 files from5 completed batches. Inference was not repeated and production labels were not changed.

Live p25 resource/process inspection confirms quality workers2989649 onGPU1 (matched batch050) and3009157 onGPU2 (supplement batch005), each using20152MiB, while Cog generation occupiesGPU4/5. GPU3 reports24GB free but utilization=N/A; `nvidia-smi -i3 -q` explicitly reports Product Brand=GPU requires reset and GPU Recovery Action=Reset for UUID GPU-84a2a869-55db-abde-70fe-9f87fa252f7e. It is not an idle healthy device and was not added to the evaluation pool. No GPU reset, service restart, training interruption or memory-policy relaxation was attempted.

Complete manuscript source remains unavailable despite existing dataset/protocol fragments; a concise async question now requests its mainTeX/Bib/figure directory. Work on runnable server jobs continues independently of that answer.

### Fresh read-only platform snapshot: two additional eligible quality finals

Using the existing restricted annotation-server proxy through SG/p25, read only the formal3600_v1 tasks, annotations and independent-observation records in one SQLite read transaction. No account tables or database file were exported. Snapshot1793491275 contains3600 tasks,3427 resolved/169 unstarted/3 draft/1 disputed and4094 annotation rows; private compressed snapshot SHA256 `6ffe73eee50e4f10acd1337047c7d4432da7cf22582620541b0dc7866e5bce27` at `annotation_refresh/live_1793491278`. All old frozen snapshots remain unchanged.

Compared against snapshot1793472550,61 task payloads changed only primary_id (reviewer reassignment); every scientific input/media/prompt/protocol field is identical. This was first held for inspection, then explicitly classified with `PAYLOAD_HOLD_RESOLUTION.json`; no task or assignment was changed by this audit. Two additional seed0 records, f3600_1254 (T04_C03) and f3600_1257 (T04_C04), now pass final quality, media and protocol binding checks. Recomputed on the same2376 existing seed0/non-T19 task cohort, current reusable quality finals2246 and missing desired slots1354. Mixed-seed resolved3427 is not the primary-table coverage count, and none is automatically new independent evaluator-validation gold.

The live Core100 distance registry concurrently advanced to85 ready/15 incomplete through the separately sealed T05_C02 full-window CPU64/original-contact conditional friction result. This was not rerun or relabelled here. Its horizon205/30 seconds, backend variant and lack of global-nearest-boundary/physics-quality approval remain explicit. The earlier84-case metric snapshot stays frozen. `build_core100_checklist.py` now checks historical and active registry versions separately, requires fresh coverage calculation to agree with the active registry, and consumes the hash-bound new annotation snapshot. All100 case totals still reconcile to36 desired slots each; formal admitted reference/pair counts remain2/1 and no generated physics score was created.

### Closest-work update and experiment priorities

Additional direct author-paper checks identified PhysWeep (arXiv2609.06207v1), What-If World (2605.27589v1) and PVBench (2610.26711v1) as close prior work. Conference acceptance was not established for these versions. The new comparison and source links are in `CVPR_GAP_AUDIT.md`; verified citation metadata is staged in `docs/cvpr_related_work_addendum.bib` without editing an unavailable full manuscript. Generic pixel-level parameter recovery, paired single-factor evaluation and numerical physical measurements cannot by themselves support a first-of-kind claim.

The resulting priority is to close actual generated cross-boundary pairs and independent event evidence, then compare their diagnostic behavior against ordinary per-video correctness on the same videos. Source-context/axis/window/version binding and local boundary-distance uncertainty must be explicit. Existing simulator/clock diagnostics do not replace independent RGB measurement validation. Single-seed conclusions remain limited to the author's frozen seed0 setting; no additional seed generation or evaluation was started in response to the literature search. This is a refinement of the original benchmark objective, not a change of metric definitions, frozen inputs, checkpoints or experimental budgets.

### T17 generated-event queue now stages available outputs incrementally

The old T17 event supervisor1806561 was authoritatively waiting with6/12 outputs, no children, no worker-launch receipt and no prediction file. It was briefly stopped to guard the check, then retired only after those conditions were reverified. Old policy, source, logs and SUPERSEDED receipt remain. Replacement3428598 uses `t17_matched_event_review_v3` and follows the same12 planned sample identities, exact frozen evaluator sources, event text,6.4-second horizon,24frames and1400-token setting. Only scheduling changed: ready unprocessed outputs may run before all12 generation outputs exist. No completed inference was repeated.

First staged batch has all6 Base outputs for T17_C04/C05 x3 prompt variants; byte/decode receipts and exact input hashes passed. Local `t17_incremental_v3_audit/VERIFICATION.json` checks unchanged event text/window, deterministic prior-plan IDs and absence of answers in judge input. New scheduler remains live and is currently waiting for an idle healthy GPU under the unchanged22500MiB/<10%/GPU1-or2 lease policy; no GPU worker or event prediction is claimed yet. Other live model/quality tasks were not interrupted. The collector now follows the active pointer, verifies the replacement command and reports staged/completed batch counts separately. Dispatch is recorded in `T17_INCREMENTAL_V3_DISPATCH.json`.

### H3 checkpoint100 and1200 completed presentations verified

`H3_CHECKPOINT100_CURRENT.json` now verifies checkpoint100 on p20, world4/globalbatch12/accumulation3, with four identical runtime states and scheduler step100. Each rank has exactly300 completed presentation records through100, covering source-order indices0..1199 exactly, with source-video SHA, selected prompt hash and exclusion of T03/T11/T19/T20 all checked against the frozen45357-video allowlist. These are presentations, not1200 independent physical trajectories. Prompt variants1/2/3 occur377/394/429 times by the existing deterministic video-ID rule.

The initial verifier incorrectly equated raw prompt hashes with effective training-input hashes. The actual discrepancy was the previously registered `source-clock-disclosure-v1` transform:27 inputs append a reference-frame-rate explanation. The verifier now reconstructs that exact rule with the verified physical clock, checks every effective text hash and deterministic variant, and preserves the first diagnostic in `H3_PROMPT_BINDING_DIAGNOSTIC.json`. No training text, feature cache or running process was modified.

All1677 distributed metadata entries deserialize, and every storage byte range is within its checkpoint shard. Four shards and416 exported adapter tensors exist; two optimizer-moment chunks from each shard and two adapter tensors were CPU-deserialized and checked finite/nonzero. This samples tensor contents; it does not claim full optimizer tensor deserialization or a complete restore rehearsal. Adapter SHA256 `29f162c40aa426ad15a32555c040801ab4404bf76cd2ecbd0cb46a0fae63cb8d`. Exact initially loaded training-code hash was not reconstructed from the running interpreter and is explicitly left unclaimed. No held-out checkpoint selection, new generation experiment, physics score or training-budget change was made.

Separate diagnostic retrieval verified all3 newly rendered source videos by bytes/SHA and full210-frame decode, and produced contact-adjacent sheets at `t17_rgb_canary_diagnostic`. These are resized diagnostic sheets, not official scoring inputs or independent human evidence. The actual human package uses the original frozen reference pixels, not the source reproductions. The default remote FFmpeg lacks libx264; packaging explicitly uses `/usr/bin/ffmpeg` with two CPU threads and lossless encoding, leaving simulation/model jobs untouched.
