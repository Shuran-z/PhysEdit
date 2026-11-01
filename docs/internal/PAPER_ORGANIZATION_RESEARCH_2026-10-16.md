# 论文组织调研与建议（2026-10-16）

## 建议结论

将论文组织成**受控物理干预视频生成的 benchmark 与分层评测**，不是 GravTrace 单算法论文，也不是只报告数据集规模的数据说明。核心问题建议写成：

> When a video generator is given a controlled physical intervention, does the generated motion change by the intended amount, and does the downstream event outcome change accordingly?

这条主线连接数据侧的干预/反事实样本与本仓库的 PhysEdit 生成流程、GravTrace 数值测量。只有当分支标签、评分协议和测试来源组均经验证后，才能把“下游事件结果评估”写成已交付贡献；否则应把当前论文收敛为可验证的参数控制评测，并将完整因果分支评估写成未来工作。

## 相关工作对结构和主张的影响

| 工作 | 已覆盖内容 | 对本文的约束 |
|---|---|---|
| PhyParam (2026-07) | 130K 模拟视频、稠密物理参数；参数控制视频模型；380 条测试 benchmark，含动力学、空间稳定性和语义-物理一致性 | 不把“带物理参数的视频数据”或“显式重力控制”作为唯一新意。需对比本文围绕临界干预、结果分岔及可追踪状态监督的增量。 |
| WorldBench (2026-01，v2 于 2026-08) | 按物理概念解耦评测，也涉及摩擦等物理常数估计 | 不泛称“首个可诊断物理 benchmark”；明确本文的测试单元是干预组/结果分支，和单概念物理规律评分有何不同。 |
| PhyGround (2026-05) | 250 个提示、13 类物理规律、人工标注和经校准的物理 VLM judge | “使用 VLM 评分”不是新意。若本文采用 VLM，必须以独立人工标注验证偏差、分项一致性及排序稳定性。 |
| VideoPhysEdit / PCVE-RigidBench (2026-09-28) | 20 个合成场景、129 个成对物理编辑任务、物理真值和 PES；编辑包括速度、质量、摩擦、恢复系数等 | 对“物理反事实视频编辑”“配对干预和下游交互”构成直接近邻。不能声称首个物理反事实评测；需比较任务输入、干预设计、临界分支、状态真值和评分粒度。 |

潜在区分点是**预先定义的同场景干预组，尤其临界点附近的干预，联合检查参数响应与后续事件分支**。这只是待实验验证的差异，不等于已经证明首次或唯一。双引擎、多视角和大规模目标容量可作为数据覆盖属性，不能单独承担新颖性主张。

## 建议的主文结构

### 1. Introduction

从“看起来合理”与“按干预正确改变”之间的差距切入。用一个同场景小图展示 factual / intervention / expected counterfactual：只改变一个已核实参数，随后比较动力学量和事件结果。

四段逻辑：

1. 视频生成模型的物理评测常看一般合理性，但这不足以测模型是否响应特定参数变化。
2. 受控评测需要可追踪配置、成组反事实和明确的下游结果真值；评分也必须区分视觉不可读、评测器失败和模型没响应。
3. 提出本文 benchmark/task 与评测层级，突出临界物理干预和数值+事件结果的互补测量。
4. 列出 3 项贡献，每项都对应一张图/表和一个实验结果，不写未经验证的“首个”“最大”或“通用物理理解”。

### 2. Related Work

建议压成三小节：

- **Physics-aware video generation and parameterized data**：包含 PhyParam 及物理生成控制工作。
- **Physics evaluation and evaluator validation**：包含 WorldBench、PhyGround；讨论规律级诊断、人工评估和 VLM judge 的边界。
- **Counterfactual video editing and intervention benchmarks**：重点讨论 VideoPhysEdit/PCVE-RigidBench；逐项说明任务输入、是否给源视频、干预范围、临界族、ground truth 和指标。

Related work 末尾放一个紧凑比较表，维度只保留能解释本文差异的项目，不堆论文列表。

### 3. Task and Benchmark Design

先正式定义模型输入、输出和一次评测样本：条件图像/源视频、可见提示中的参数、生成视频、隐藏真值及评测器允许读取的信息。把 I2V、视频编辑等不同输入轨道分开报告。

关键协议风险：当前 `scripts/phyediting_gen.py` 的 EVENTS 提示词直接写出部分后续结果。因此该协议能测试“已指定事件下的重力控制”，不能作为模型自行预测下游因果结果的证据。要测分支预测，需另设 outcome-blind 输入，不得把目标结果提示给生成模型。

### 4. Dataset Construction and Split

描述事件类别、模拟参数、背景/视角、临界族采样、状态/接触/事件标签、渲染与 QA；再定义来源组和 split 规则。把设计规模、绑定路径库存、QA 通过量、最终测试量分列。

当前新版协议是 Genesis+Isaac 联合训练，T03/T20 为 OOD-1，T11/T19 为 OOD-2，其余 16 类按来源组约 80/10/10 划分。明确两个 OOD 是整事件迁移，不是引擎留出，也不是纯短链到长链。最终 split 尚未物化，72,960 是容量目标；不能在结果中写成已发布有效总量。

### 5. Evaluation Protocol

建议分成互补的三个分量，分别报分，不急于压成一个总分：

1. **Intervention response**：同场景/同来源组的参数响应误差、方向/单调性或干预量级；只在物理上可辨识的任务上计算。
2. **Outcome and event sequence**：关键分支正确率、完整干预组全对率、可观察事件及顺序。因果边本身不能只由时间先后推断。
3. **Measurement and visual validity**：GravTrace 只测合适视频片段中的重力；另报失败率、覆盖率、置信/残差诊断和视觉可读性。它不代表摩擦、接触和整个事件链正确。

如果用 VLM 判断对象、事件或分支，把它定义为候选自动评测器：先用冻结规则与独立人工小样本校准，报告混淆矩阵/分项一致性/组级排序稳定性；在得到这些结果前，不把 VLM 分数当权威 ground truth。仿真配置和状态提供数值真值，人工可见性标注提供视频是否可判定的真值，两者职责分清。

### 6. Experiments

主文实验建议按以下顺序组织：

- **Dataset and QA statistics**：最终视频、轨迹、来源组、干预族及各层 QA 通过数；展示参数/事件覆盖，不报计划容量冒充实际数据。
- **Evaluator validation**：在真实参考视频和受控正负样本上验证 GravTrace、分支标签/检测器；固定评测窗口与阈值，不得按目标分数逐例择窗。
- **Main benchmark results**：多种代表生成模型，在相同提示/条件/种子/来源组上比较；所有尝试保留分母，区分生成失败、物理响应失败和测量失败。
- **Intervention analysis**：临界与非临界组、不同参数/事件的成对响应；按来源组聚类统计，避免把视角/背景/重复误当独立样本。
- **Generalization and diagnostics**：ID 与整事件 OOD 分开；只在最终划分冻结后报告。跨引擎结果单列管线迁移解释，不归因于纯 solver shift。
- **Ablations / human validation**：干预输入信息、评测层去除、VLM 与人工对齐、评测失败分类；正文只留直接支撑主张的消融。

建议主图 1 张：任务与干预组示意；主图 2 张：数据/评分流程和评测结果分解。主表分别给 benchmark 总结果和按维度分解。详细 schema、全部模型设置、提示词、额外结果和失败案例放补充材料。

### 7. Limitations and Conclusion

明确模拟器和刚体范围、合成到真实的差距、相机和初始状态等可观测信息限制、临界重复中的随机性、GravTrace 的适用域，以及事件类型覆盖不均。结论只重述已经在冻结数据和独立测试上证实的发现。

## 当前最重要的收敛判断

截至 2026-10-16，本地记录显示最终组级 split 未完成，生成视频分支/事件链评分尚未形成完整结果，GravTrace 的 1,038 条是开发数据且存在与旧 ID 测试的 ID 重叠记录。现有 I2V 重力实验中，六个模型各 40 条清单任务的重力阈值命中很少，不足以支撑稳定模型排名。因此当前最稳妥的是先写一个**两轨论文草稿**：主线围绕已能冻结并验证的参数控制协议；将因果分支评测列为必须通过门槛的扩展。若 10 月 20 日前无法拿出独立来源组上的有效分支评测和 evaluator validation，删去“完整因果评测已经实现”的主张，而不要依靠 future work 掩盖这一缺口。

投稿时间紧：CVPR 2027 官网列出注册截止 2026-11-10 AoE、全文截止 2026-11-16 AoE、补充材料截止 2026-11-23 AoE。CVPR 的同期工作政策要求引用和讨论 2026-09-15 后出现的工作，并在可行时做比较；VideoPhysEdit 属于这一时间范围。官方页面列出数据集/benchmark、视频生成、物理视觉等主题，整体选题范围匹配，但这不代表录用判断。

## 主要外部来源

- PhyParam: [arXiv:2607.18924](https://arxiv.org/abs/2607.18924)
- WorldBench: [arXiv:2601.21282](https://arxiv.org/abs/2601.21282)
- PhyGround: [arXiv:2605.10806](https://arxiv.org/abs/2605.10806)
- VideoPhysEdit: [arXiv:2609.35134](https://arxiv.org/abs/2609.35134)
- CVPR 2027 CFP: [official page](https://cvpr.thecvf.com/Conferences/2027/CallForPapers)

## 本地证据入口

- `docs/BENCHMARK_CONTEXT.md`
- `docs/joint_split_v3/README.md` and `plan.json`
- `docs/CVPR_PROGRESS_2026-10-09.md`
- `docs/COMPETITIVE_REVIEW_2026-10-09.md`
- `scripts/phyediting_gen.py`

## 补充：评测整体性与是否需要总分（2026-10-17）

顶会 benchmark 没有“多指标必须压成一个总分”的统一做法。能看到两类成熟方案：

- VBench 将视频质量拆成 16 个层次化维度，每个维度有对应的 prompt 和评估方法，并逐维度做人工偏好对齐。其定位强调细粒度诊断；项目代码另提供可选的 Quality/Semantic/Total 加权分数。因此论文既可以保留维度向量，也可以另外提供明确标注用途的 leaderboard summary。
- Ref4D-VideoBench 以 4 个评测维度组织 12 个指标，强调 reference-based 证据和人类判断对齐，官方摘要没有把一个任意总分当成主要结果。
- FlatSounds（CVPR 2026）将单变量反事实配对与单视频趋势测试纳入同一物理审计框架，报告九项物理/时间相关指标、权衡图和多维图表；其补充材料用成对人工偏好验证物理指标。它是“统一问题、多个互补结果”的直接组织先例。
- EvalCrafter（CVPR 2024）确实产生最终总分，但先用用户意见拟合各客观指标的系数，并报告该总分比简单算术平均更贴合用户意见。这说明综合分数要有经验校准，不应只凭作者指定权重。

### 对本项目的建议

将三层指标统一到一个**构念**，暂不强行统一为一个**算术分数**：

> Intervention fidelity：给定可核验的物理干预，生成视频是否在数值动力学、临界结果分支、下游事件演化上遵循相应的真值变化？

三项对应不同层次：

1. **参数/动力学响应**：GravTrace 测适用片段中的重力响应与测量覆盖。
2. **临界转移**：干预前后是否落入预期分支，是否在阈值两侧出现正确结果改变。
3. **事件链**：关键后续交互及其顺序是否符合对应物理轨迹/标签。

要证明三者整体，需把它们连到相同的干预单位上：来源组/初态、干预变量、目标变化、参考轨迹、终态或事件链和生成输入都可追溯。主文应给出因果/评测图，显示从干预到连续状态、分支和事件链的对应关系，并展示互补失误案例（例如 g 数值吻合但分支错误；分支正确但动力学量级错误）。若三项来自完全无关的样本、无共同测试协议或不能追溯到同一干预，就只能称为评测套件的多维组成，不能宣称它们共同测量一个整体能力。

### 综合主指标的决策

当前建议**不设置加权总分作为主指标**。先把三类维度分别设预注册的 primary endpoint，并报告完整结果向量、覆盖率、所有尝试的分母和按来源组的置信区间。理由是：GravTrace 目前只在可测物理片段上有效；分支与事件链评分仍需独立验证；不同项目缺失/失败语义不一样；加权平均可能允许高重力分数抵消严重分支或事件失败。

如果以后需要一个易读的 headline number，优先考虑不是加权均值，而是**完整干预组端到端成功率**：一个来源组只有在所有预先声明且适用的维度均通过冻结阈值时才算成功。必须预先说明适用条件和分母，某层不可测应按单独的不可评测状态处理并同时报覆盖率，不能悄悄删样本。这个合取指标回答“完整干预任务是否成功”，不替代各分项诊断。

只有满足以下条件后，再考虑从多指标拟合总分：足量的独立人工/专家偏好或明确决策效用标注；预先固定的训练/验证来源组，避免对测试数据拟合权重；证明该总分在留出来源组上比简单基线更能预测判断/下游用途；报告权重敏感性与单项结果；验证指标方向、尺度和失败处理具有稳定解释。若目标是科学诊断而非单一排行榜，维度向量通常更合适。

### 顶会先例来源

- VBench CVPR 2024 [论文页](https://openaccess.thecvf.com/content/CVPR2024/html/Huang_VBench_Comprehensive_Benchmark_Suite_for_Video_Generative_Models_CVPR_2024_paper.html)；[官方项目页](https://vchitect.github.io/VBench-project/)；[聚合分数实现说明](https://github.com/Vchitect/VBench)
- Ref4D-VideoBench CVPR 2026 [论文页](https://openaccess.thecvf.com/content/CVPR2026/html/Wei_Ref4D-VideoBench_Four-Dimensional_Reference-Based_Evaluation_of_Text-to-Video_Generative_Models_CVPR_2026_paper.html)
- FlatSounds CVPR 2026 [论文页](https://openaccess.thecvf.com/content/CVPR2026/html/Li_Benchmarking_Single-Factor_Physical_Video-to-Audio_Generation_CVPR_2026_paper.html)；[官方项目页](https://research.nvidia.com/labs/cosmos-lab/flatsounds/)
- EvalCrafter CVPR 2024 [论文页](https://openaccess.thecvf.com/content/CVPR2024/html/Liu_EvalCrafter_Benchmarking_and_Evaluating_Large_Video_Generation_Models_CVPR_2024_paper.html)
