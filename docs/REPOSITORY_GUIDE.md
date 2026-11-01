# 仓库导航

本仓库包含视频生成、物理参数测量、临界边界评测和人工标注。数据集文件通过 [PhyDataset](https://huggingface.co/datasets/phy2/phydataset) 发布，源码、冻结参考和运行产物分别管理。

## 按任务查找

| 任务 | 文档 | 代码入口 |
|---|---|---|
| 仿真器反演与 V/P 指标 | [反演方法](INVERSION.md)、[评测步骤](EVALUATE.md)、[指标](METRICS.md) | `physprobe/inversion/` |
| 视频生成与模型配置 | [快速上手](phyediting/QUICKSTART.md)、[模型和权重](phyediting/MODELS.md) | `physedit/runners/`、`physedit/conditioned_models/` |
| 单视角解析测量与对照方法 | [参数测量](phyediting/MOTION_PARAMETERS.md)、[跟踪](phyediting/SAM31.md) | `gravtrace/`、`physedit/parameter_evaluation.py` |
| 临界边界、配对和事件链评分 | [执行指南](../BOUNDARY_EVALUATION.md)、[协议索引](critical_boundary/README.md) | `physedit/boundary.py`、`physedit/boundary_pipeline.py` |
| 当前 Core100 参考与距离 | [五条 T19 替换](critical_boundary/CORE100_T19_REPLACEMENT.md)、[距离绑定](critical_boundary/CORE100_DISTANCE_BINDINGS.md) | `catalog/active_core100_conditions.json`、`physedit/core100_release.py`、`physedit/core100_bindings.py` |
| 人工标注与评分桥 | [标注站](../annotation_site/README.md) | `annotation_site/` |
| 数据下载、清单和发布工具 | [同事下载指南](DOWNLOAD_FOR_COLLEAGUES_ZH.md)、[数据清单](dataset_inventory/README.md) | [scripts/README.md](../scripts/README.md) |
| 提示词与训练划分 | [提示规则](PROMPT_POLICY.md)、[划分协议](joint_split_v3/PROTOCOL.md) | `physedit/prompt_contract.py`、`docs/joint_split_v3/plan.json` |

## 目录职责

| 路径 | 内容 |
|---|---|
| `physedit/` | 生成、提示合同、质量筛查和评分编排 |
| `physprobe/` | 按原仿真器反演参数，以及 V/P 指标；需要单独准备仿真库和跟踪产物 |
| `gravtrace/` | 相机投影与运动拟合等解析测量代码 |
| `annotation_site/` | 标注网站源码、协议资源和评分桥；数据库、邀请和会话留在私有目录 |
| `catalog/` | 当前冻结参考的入口指针 |
| `benchmarks/` | 冻结参考包、清单与哈希；这些文件按原始字节保存 |
| `scripts/` | 数据恢复、边界求解、审计、打包和发布工具；保留现有名称以兼容已登记命令 |
| `tests/`、`annotation_site/tests/` | 回归测试，不代表模型实验已经完成 |
| `docs/` | 当前文档、协议和注明日期的结果 |
| `docs/internal/` | 保留的研究记录；当前入口和协议优先于其中的旧快照 |
| `review/`、`runs/`、`outputs/` | 本地证据、视频、运行结果和预览；默认不纳入源码提交 |
| `.local-research/` | 本地诊断、备份指针和机器相关材料 |

## 当前输入约定

- Core100 从 `catalog/active_core100_conditions.json` 加载。五条 T19 使用 `core100-t19-isaac-v1-20261031`，其余 95 条沿用冻结 v6；旧参考、生成视频及标签保留，不能转移到新参考。
- 全量视频使用各自物理参数对应的三种简短英文提示，统一清单在父目录 `prompts_72000_unified/`。已有模型输出保留实际提交的文本与哈希。
- 固定测试 100 条，另有 80 条候补。训练使用排除测试、候补、已核验同源组和四类 OOD 事件后的 16 类合格来源，不另设验证集。
- 数值距离、参考准入、生成质量和模型评分是不同状态。参考距离表不能当作生成模型成绩；反演不适用的样本仍保留事件评测分母。

## 本地验证

在仓库根目录执行：

```bash
python -m pip install -e ".[test]"
python -m physedit --help
python -m gravtrace --help
python -m physedit.core100_release status
python -m physedit.core100_bindings status
python -m pytest tests/test_core100_distance_bindings.py tests/test_core100_reference_release.py annotation_site/tests/test_workflow.py -q
```

`core100_bindings status --verify-evidence` 还需要注册表逐项列出的本地原始证据；源码中的冻结注册表本身不包含全部原状态。远程恢复和发布脚本可能访问服务器或修改发布状态，运行前须阅读脚本参数、目标版本和输出路径，不能批量执行目录内脚本。

## Git 同步

本地和远端的两套提交历史已在集成分支保留并合并；处理记录见 [REPOSITORY_INTEGRATION_20261031.md](REPOSITORY_INTEGRATION_20261031.md)。今后使用普通 fetch/pull/push，不需要再次允许无共同祖先的历史合并，也不需要强制推送。冻结参考和评分资源通过 `.gitattributes` 禁止换行转换，普通源码统一 LF。
