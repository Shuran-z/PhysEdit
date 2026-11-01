# 仓库导航与版本边界

更新：2026-10-28。当前目录是物理数据集 benchmark 的生成、测量和评测仓库。

## 从哪里开始

| 目的 | 入口 |
|---|---|
| 投稿进度、已完成证据和待办 | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 本地运行生成与参数测量 | [快速上手](phyediting/QUICKSTART.md)、[模型](phyediting/MODELS.md) |
| 临界点、距离分桶、配对及事件链 | [临界模块索引](critical_boundary/README.md)、[执行指南](../BOUNDARY_EVALUATION.md) |
| 固定100条逐项可评状态及缺项 | [Core100准备清单](critical_boundary/CORE100_READINESS_20261027.md)，查看文件内生成时间 |
| 垃圾视频筛查 | [scene-integrity-v2](critical_boundary/SCENE_INTEGRITY_V2.md) |
| 人工标注与网站评分桥 | [annotation_site/README.md](../annotation_site/README.md) |
| 训练/测试规则 | [joint_split_v3](joint_split_v3/README.md)、其中 `plan.json` 的 `evaluation_sets.fixed_core100.training_policy` |
| 本地论文片段 | [dataset_description.tex](dataset_description.tex)，不是完整主文 |
| 原始审计与本次盘点 | 本地 `review/repository_inventory_20261027/`；不随公共源码自动发布 |

## 目录职责

| 目录 | 内容与处理规则 |
|---|---|
| `physedit/` | 生成、提示合同、评分编排及临界模块源码 |
| `gravtrace/` | 本地解析物理测量实现；开发集数字单独报告 |
| `annotation_site/` | 网站源码、冻结协议资源、评分桥；目前大量文件尚未提交，不能当缓存忽略 |
| `scripts/` | 数据恢复、临界搜索、审计工具；历史日志中的命令不构成执行授权 |
| `tests/` | 测试源码；运行结果与实验分数分开记录 |
| `docs/` | 使用文档、协议、研究说明及论文片段；带日期的历史快照按其日期解释 |
| `review/` | 本地视频、原始回答、哈希与审计回执，保留原路径；已由Git忽略 |
| `outputs/` | 交接文档、预览及安装依赖；已由Git忽略，文件保留在磁盘 |
| `.local-research/` | 私有备份及机器相关资料；已由Git忽略 |
| `examples/` | 可复现的示例输入 |

父目录是数据集工程，不能把本仓库目录数或 `outputs/` 文件数当成数据集规模。`benchmarks/`、`catalog/` 的发布引用是 HF 数据仓库中的路径，本地未检出这些目录不等于线上没有发布。

## 当前版本边界

- 按本轮作者规则，Core100使用 `phy2/phydataset@f23ee3577952ec1e5357c8a729bfc4daa5c7272d` 的完整v6提示绑定；不通过v7重新生成输入。
- 当前 `annotation_site/resources/core100_final_input_policy.json` 为v3，要求全部100条精确v6文本、seed 0；旧“31条v6、69条旧文本”是历史规则。规则统一不代表全部存量输出符合输入、条件图和观察窗要求；人工记录保留，不自动转移到替代视频。
- 固定100条：ID80、OOD-1为T03/T20共10、OOD-2为T11/T19共10；另80条候补。训练使用排除测试、候补和已核验同源组后的16类合格来源，不另设验证集。
- 多个prompt/seed是同一物理任务的生成重复，不增加独立物理任务数。网站冻结抽样组合与“seed0三prompt”的早期方案不是同一批次。
- 旧开发集误差、97任务远端主表、3600网站任务、200条诊断和24条规则开发批次必须分别报告。

## Git整理与同步

2026-10-27核对：本地 `main@aca3bf12` 与远端 `main@8e6d6295` 无共同祖先；界面的113/54不能解释为普通分叉后的提交差异。远端包含本地缺少的 `physprobe/` 和新结果文档，本地包含尚未同步的网站及临界恢复工作。

2026-10-28本地复查：`HEAD=34a816ed`，缓存的 `origin/main=8e6d6295`，仍无共同祖先；相对缓存引用计数115/54，本次未刷新远端。当前Git可见137个改动文件：22个已跟踪修改、115个未跟踪文件，其中标注平台78个。原盘点中的4,470个 `outputs/` 产物已由忽略规则移出变更列表，文件保留原地；这不等于源码已提交或两套历史已经整合。本次盘点未创建提交或推送。

本轮只整理入口、忽略产物和纠正文档；没有合并两套历史。同步时应在独立集成分支逐模块对齐，保留两侧来源、冻结输入哈希、已有评分器和标注数据。禁止用一次全选提交或强制覆盖代替核对。

整理前的已跟踪差异、84份未跟踪作者文件及文件清单保存在 `.local-research/repository_cleanup_20261027/`。`outputs/` 保留原地。本轮期间其他任务可能继续写文件，盘点是带时间的快照。

截图中的CRLF提示说明Git按 `.gitattributes` 规范化换行，不是文件损坏。本轮没有对全仓库批量换行。
