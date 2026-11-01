# 仓库整合记录 · 2026-10-31

## 合并内容

- 原本地 `main`：`34a816ed`；刷新后的远端 `origin/main`：`8e6d6295`。二者没有共同祖先。
- 整理前的 343 个改动文件已保存到独立备份，包含工作区 ZIP、二进制差异、逐文件 SHA256 清单及通过校验的 Git bundle。备份在父目录 `repository_backups/`，本地指针为 `.local-research/LATEST_INTEGRATION_BACKUP.txt`。
- 本地改动先分为三组提交：标注站/提示合同/冻结参考，恢复脚本/测试，协议/数据说明。
- 合并提交 `489fcb34` 同时保留本地和远端父提交。远端 `physprobe/`、V/P 指标文档、模型权重说明和结果表已接入；本地临界恢复、网站与提示合同继续保留。
- 未删除视频、数据库、人工标签或 `review/` 中的原始证据。远端 `.DS_Store` 只从源码索引移除，磁盘文件和原提交保留。

## 冲突选择

33 个文件发生 add/add 冲突。其中 25 个远端文件与本地整理前版本相同，沿用本地较新修改；其余逐项处理如下。

| 文件 | 处理 |
|---|---|
| `README.md` | 保留远端结果表和方法说明，补入当前源码、标注站与参考入口；说明旧结果不转移到五条替代 T19 |
| `docs/joint_split_v3/PROTOCOL.md` | 保留当前协议及有效文档链接；固定100测试、其余合格来源训练，不新增验证划分 |
| `docs/phyediting/MODELS.md` | 接入远端 GravityAdapter 权重说明，链接指向当前使用指南 |
| `pyproject.toml` | 同时保留本地提示分词器/裁判依赖与远端 PhysProbe 包、部署和服务端文件 |
| `scripts/combine_recovered_boundary_distances.py` | 保留归一化恢复、新 T19 与 T20 来源接入，不恢复整类 T19 停用的旧处理 |
| `scripts/register_t18_table_contact_distances.py` | 保留修正资产工作目录后的结果准入和 p26 回收支持 |
| `scripts/t07_original_boundary_worker.py` | 保留全网格、压缩状态读取及资源队列修复 |
| `scripts/t18_table_contact_boundary_worker.py` | 保留资产路径、执行环境、资源队列及完成回执修复 |

详细目录入口见 [REPOSITORY_GUIDE.md](REPOSITORY_GUIDE.md)。恢复/发布脚本保留原名，避免破坏服务器登记的调用和源代码证据路径。

## 文件与安装检查

- `.gitattributes` 对冻结参考、目录指针、评分资源和分词器启用字节保留；106 份资源的 Git 索引内容与磁盘原字节一致。
- 从 Git 树导出全新副本，当前 Core100 参考加载与距离注册表加载通过；没有借用该副本外的原始状态来通过加载检查。原始证据的额外 SHA 核验仍需要其注册路径文件。
- wheel 构建成功；包内包含 PhysProbe 源码和服务端文件、本地评测模块、GravTrace 和提示分词器。
- Python 源码编译检查、`physedit --help`、`gravtrace --help` 通过。
- 变更源码和内嵌运行包的高精度凭据模式扫描未发现命中；此项不替代完整安全审计。

## 回归检查

核心合并回归：86 passed、1 skipped、16 subtests passed。覆盖冻结参考与哈希、距离绑定、划分协议、结果回收、T07/T18 修复、事件输出、质量筛查和人工工作流。前端任务导航另有 3 项回归通过。

合并前副本单独运行生成时钟、生成流水线、Gravity100 三组测试：98 passed、2 skipped、9 failed。失败包括旧测试输入没有升级到英文提示合同，以及测试替身缺少新增的 tokenizer 接口；不能通过回退当前提示规则来掩盖这些失败。完整记录在本地 `.local-research/repository_integration_20261031/`。

完整合并后回归结果随后按实际执行回执更新。本记录不宣称生成模型的新实验、服务器热部署或数据集新发布已经完成。
