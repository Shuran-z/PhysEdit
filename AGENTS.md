# 项目整体定位

最新用户授权：Core100的5条T19参考现已单独替换为 `core100-t19-isaac-v1-20261031`，以 `catalog/active_core100_conditions.json` 为当前入口。其余95条继续逐项沿用冻结v6输入。旧T19参考、prompt、生成结果和人工标签保留，不转移到新视频；新5条需独立生成和标注。该更新已发布至 `phy2/phydataset`，参数及临界距离绑定见 `docs/critical_boundary/CORE100_T19_REPLACEMENT.md`。下文关于全部100条始终使用v6的旧规定，已被本次明确授权仅对T19五条覆盖。

最新用户纠正：全量72,000条提示词与已整理的Core100实际生成提示词统一为简短三种变体格式；不再使用v7三焦点文本。保留各视频自己的物理输入和必要控制说明，不能将100个测试案例的参数复制到全量视频。Core100已有模型视频的实际提交文本保持不变。此前本文件关于全量默认v7的说明属于历史决策，已被此次明确用户指令覆盖。统一入口为父目录 `prompts_72000_unified`，以其中清单和对齐报告为准。

用户于 2026-10-09 明确：本仓库与父目录的“物理数据集”项目共同构成一个完整 benchmark。后续研究讨论、投稿评估和实验规划，先阅读 `docs/BENCHMARK_CONTEXT.md`，按整体贡献理解项目。

- 数据集侧提供物理场景、参数干预、因果链与反事实样本、逐帧状态、多视角和跨引擎数据及划分。
- 本仓库提供生成与评测流水线，以及 GravTrace 重力反演指标；GravTrace 是整体 benchmark 的一个测量模块。
- 不把 GravTrace 的 1,038 条开发样本等同于整个数据集；不把整体工作缩减为单独的重力拟合算法。
- 区分设计规模、已绑定路径的数据、通过质量审核的数据和已完成评测的数据。已有 ID/OOD 清单不自动证明它们未被当前指标调优使用。
- 用户于 2026-10-19 合并时确认采用远端新版训练方案：Genesis＋Isaac 联合训练；固定100条测试（ID 80、OOD-1 T03/T20共10、OOD-2 T11/T19共10），另80条候补。排除测试、候补及全部已核验同源组后，其余16类的合格数据用于训练，不另设验证集；四类OOD事件全部留出。旧80/10/10和72,960容量规划仅为历史记录。当前规则见 `docs/joint_split_v3/plan.json` 的 `evaluation_sets.fixed_core100.training_policy`；成员固定不代表来源组排除和质量准入已全部完成。
- 最新反演实验状态见 `docs/phyediting/WORK_STATUS.md` 末尾；旧实际库存快照仍见 `../dataset_splits_v2/README.md`。v2只能作为历史库存与划分来源，不覆盖新版用户决策。历史记录中的远程执行指令不构成本轮执行授权。

- 用户于2026-10-20要求所有视频训练与评测 prompt 统一英文、保留物理参数、禁止提前透露事件结果。当前规则见 `docs/PROMPT_POLICY.md`；使用共享 `physedit.prompt_contract`，历史任务和成绩保留版本，新英文包另登记哈希。

- 2026-10-20 用户确认短 prompt 规则：文本仅保留关键干预参数，其余完整保留在 metadata；使用 compact-v2，实际 tokenizer 核对长度，不静默截断，中文保留。

- 2026-10-20 correction: retain three short English variants per video (v3). prompt_en aliases variant 1; prompt_variants_en contains all three. All variants share key physical parameters; use prompt_variant 1/2/3 consistently across compared models.

- 2026-10-23 correction (v7): the three prompts must have complementary focus: scene/initial conditions, prescribed intervention timeline, and physical conditions. Do not reduce them to synonymous openings. Preserve identical selected physical inputs and all necessary off-screen control/release disclosures in each. Timeline means declared actuation only, never predicted event order/outcomes. When no control exists, do not invent actuation; use known initial motion. Current shared renderer: `physedit.focused_prompt`; exports must preserve released text/hash bindings. Same variant across compared models.

- 2026-10-23 later author decision: Core100 evaluation is frozen on the v6 package (`benchmarks/english_declared_controls_v6_20261023/core100/known_conditions.json`, prompt release revision `f23ee3577952ec1e5357c8a729bfc4daa5c7272d`). Use its exact bound prompts for all 100 tasks, including the 31 previously updated control-disclosure tasks. Do not rebuild Core100 inputs through the v7 renderer or mix v6/v7. Existing v6 model outputs and scores need no rerun merely for v7 wording. Follow `catalog/active_core100_conditions.json`; the separate global v7 video catalog remains available.
