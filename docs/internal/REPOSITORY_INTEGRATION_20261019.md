# 2026-10-19 仓库合并记录

本次按 benchmark 的整体逻辑合并本地临界边界工作与远端生成、跟踪、物理参数测量流水线。

## 来源与恢复点

- 本地工作先保存为 `7156ea3`；备份分支为 `codex/pre-integration-20261019`。
- 远端基线为 `origin/main` 的 `b19baad`。
- 两侧没有共同祖先，使用保留双方历史的 merge；未使用强制覆盖或改写提交历史。
- 原本地部署配置保存在被忽略的 `.local-research/fleet_preintegration_20261019.py`。新版多机调度通过 `PHYSEDIT_FLEET_CONFIG` 显式加载私有配置。
- 原始视频、实验输出及本地环境保留在磁盘，不作为本次代码合并的新产物上传。

## 合并后的功能

- 统一 `physedit` 入口保留远端生成、跟踪、重力/摩擦/初速度测量及视觉评测，并保留本地 `boundary`、`boundary-evaluate`。
- 临界边界流程保留独立质量筛查、逐事件判读、人工复核、失败样本总分母，以及事件和反演分别计算覆盖率。
- H3 保留本地可选补边、输入图留档、逐样本画布记录及输出裁回；接入远端 MiniMax 工作流拆分兼容逻辑，模型目录需显式指定。
- GravTrace 核心代码与远端一致；已有开发集统计不代表本次重新运行模型得到的新结果。
- 修复 Windows 下媒体巡检目录解析及传输清单路径映射；本地命令不再因顶层导入 Unix 锁模块而失败。

## 当前划分决定

用户于本轮确认采用远端新版：固定100条测试（ID80、OOD-1 10、OOD-2 10），保留远端80条候补排除规则。Genesis 与 Isaac 联合训练；排除测试/候补的已验证同源组及 T03/T20/T11/T19 后，其余合格来源组用于训练，不另设验证集。

旧80/10/10方案仅供历史或可选分组工具使用，不能覆盖当前决定。当前策略在 `docs/joint_split_v3/plan.json` 的 `active_partition` 和 `evaluation_sets.fixed_core100.training_policy` 中登记。登记策略不等于最终训练清单已完成科学验收，也不自动满足临界边界配对要求。

历史文档保存于 `docs/archive/JOINT_SPLIT_20261009.md` 和 `docs/archive/GRAVTRACE_REFERENCE_PREINTEGRATION.md`。

## 验证

Windows、Python 3.12，本地执行 `pip install -e ".[test]"` 成功。

- 首轮全量：732 passed、25 failed、4 skipped；检查发现路径断言、路径归一化、默认文本编码和 Unix 专用测试问题。
- 修复后针对失败项复测：22 passed、3 skipped；原有科学阈值和固定清单摘要未改写。新增跳过的3项为2项 POSIX shebang 可执行文件测试、1项 Unix socket 权限测试，仍需 Unix 主机验证。
- 关联集成回归：192 passed、3 skipped，覆盖清单构造、统一入口、生成时钟、生成流水线、模型启动契约、参考可观察性准入及数据划分。
- `physedit --help`、`physedit boundary --help`、`physedit measure --help` 和 Python 编译检查通过。

完整日志保存在本地 `.local-research/merge_pytest_20261019.log`、`merge_retest_20261019.log`、`merge_integration_20261019.log`。本次没有运行 GPU 模型生成或重新计算实验指标；上述测试不代表 GPU 部署或裁判效果已经验收。
