# 联合划分执行入口

执行时提供自己的来源路由与开发样本清单：

```bash
python -m scripts.phyediting_joint_split --routing /absolute/path/routing.jsonl \
  --development /absolute/path/development.csv --out runs/joint_split_v3_candidate
```
它按 `plan.json` 将两引擎一起分配，保留全部输入记录；三视角、背景变体、临界族、已知重复和对应配置绑定。OOD事件保持整体留出，训练池按完整组近似80/10/10。原反演与已有结果不变。

输出五集合清单、`pending.jsonl`、`quarantine.jsonl`、全部记录的 `assignments.jsonl` 与含来源/输出SHA的 `audit.json`。路由输入生成候选清单，训练使用审核后的冻结版本。 未核验的扫描组进入pending；跨事件池冲突整组进入quarantine，不删除记录。

## 证据与正式冻结

`--evidence evidence.jsonl` 接收每条record的真实来源与审核收据：

- `record_id`及`identity`的`sample_id/engine/revision/release`；
- `videos`包含cam01/02/03的`path/sha256`，`state`含`path/sha256`；
- `receipt`为可读JSON的`path/sha256`，内容须逐项绑定相同身份、资产、审核与标签；
- `checks`逐项认证解码同步、状态时间/单位/对象、运行参数、事件标签、视觉物理QA、重复与跨引擎映射。键名见脚本的`CHECKS`；收据绑定实际审核结果；
- `sampling`含经核验的`kind`（global/critical）、`family_id`、非负整数`propagation_depth`；
- 扫描记录的`scan`含真实`parameter/unit/value/low/high/interval_id/family_id/controls_sha256`及`boundary_guards_reviewed=true`。共享端点或重叠区间整组绑定，不从p001编号推断数值；
- 已核验配置/临界族可指定`physical_configuration_group/critical_family_group`。额外对应关系用`--links links.jsonl`登记`record_ids/receipt_path/receipt_sha256`，冻结时验证实际收据内容。

加入`--freeze --out runs/joint_split_v3_release_v1`后，仅在证据、目标非零事件覆盖、可行组覆盖及待处理/冲突全部解决时写正式版本；条件不足时返回具体状态。冻结版本不覆盖，改动用新版本。训练只能经`load_training_split(directory, split)`加载，reader检查冻结状态和内容SHA。

`training_sampling_weights(directory)`仅对冻结train返回按事件、族和实际传播深度平衡的轨迹权重，输出权重供训练入口使用。三视角可在已分配轨迹内选择，不能跨集合。

默认用1038例开发CSV记录指标开发组闭包；`--historical-exposure prior_attempts.json`可补充`prior_prediction_trajectory_ids`。暴露记录保留在清单中，独立测试另行登记。生成模型事件留出与评测指标开发边界分别报告。
