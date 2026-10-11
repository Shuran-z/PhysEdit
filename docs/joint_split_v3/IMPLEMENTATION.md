# 评测清单与联合划分执行入口

## 固定100条清单

从[固定版本目录](https://huggingface.co/datasets/phy2/phydataset/tree/64ae065222f6893b7c06ed446aa20d3b8e3cdc86/benchmarks/fixed_core100_v1_20261014)取得`FREEZE.json`、`PROTOCOL.md`、`core100.jsonl`与`reserve80.jsonl`，放在同一个本地目录。检查版本并生成三组清单：

```bash
python -m physedit.evaluation_split --source-dir /path/to/core100_source --out runs/core100
```

不提供`--out`时只检查并显示统计。输入文件逐一匹配包内[版本索引](../../physedit/core100.json)和数据集冻结记录；成员数、事件数、匿名ID与来源声明分别检查。

| 输出 | 内容 |
| :---: | :---: |
| `test_id.jsonl` | 80条ID测试 |
| `test_ood_1.jsonl` | T03/T20共10条 |
| `test_ood_2.jsonl` | T11/T19共10条 |
| `assignments.jsonl` | 全部100条及当前集合、来源与测量条件 |
| `reserve80.jsonl` | 80条候补，集合统一为`reserve` |
| `summary.json` | 版本、SHA256、分组统计与审核状态 |

输出统一使用当前集合标签，保留来源身份、视频SHA256、来源状态和测量条件。发布输入文件保持原字节。输出记录`membership_frozen=true`、`formal_test_ready=false`，全量训练来源组的排除与科学审核分别完成后再确认正式测试资格。模型只接收任务允许的输入及匿名媒体名，完整清单留给研究者与评分器使用。

## 训练集

按`summary.json`中的`training_policy`选择训练数据：Genesis与Isaac联合使用；T03/T20、T11/T19全部留出；其余16类排除100条测试、80条候补及所有已核验同源组后，统一归为`train`，不另分`val`。

同源组包括同轨迹其他机位、背景变体、重复、临界族、重渲染版本及已核验跨引擎对应版本。全量训练清单应按实际库存执行这些排除，并核验训练与测试的组交集为空。当前命令输出固定评测清单和训练选择规则；训练清单数量在全量库存完成分配后统计。

每条样本的缺源、失败、不适用及缺少标签原因与原ID一起保留。重力、动摩擦和初速度分别判断适用性，再报告误差、失败率与覆盖率。模型输入仅包含任务允许的条件与匿名媒体名。
