# 联合划分执行入口

执行 `python -m scripts.phyediting_joint_split --out runs/joint_split_v3_candidate`。
它按 `plan.json` 将两引擎一起分配，保留全部输入记录；三视角、背景变体、临界族、已知重复和对应配置绑定。OOD事件保持整体留出，训练池按完整组近似80/10/10。原反演与已有结果不变。

输出五集合清单、`pending.jsonl`、`quarantine.jsonl`、全部记录的 `assignments.jsonl` 与含来源/输出SHA的 `audit.json`。**路由输入生成的是候选清单，不能直接训练。** 未核验的扫描组进入pending；跨事件池冲突整组进入quarantine，不删除记录。

## 实际候选执行

2026-10-11，原22,801条轨迹、68,403个三视角引用全部保留。原3,604个来源组件在固定版本媒体SHA恢复后，按两项跨旧组重复收据合并为3,601个；已知绑定跨集合冲突0。视频引用分配为train29,148、val4,143、ID4,149、OOD-1 5,952、OOD-2 5,496、pending19,515。数量不是已通过QA的媒体数。

Genesis固定版本目录已重建148,297项文件索引。原16,081条轨迹中，14,621条有精确引用及三相机MP4身份匹配；另1,460条未匹配（T15 880、T09 300、T06 280）。T12相机描述后缀已按实际render manifest修复。此前“全部匹配引用”的计数包含空列表，已纠正；引用恢复仍不是媒体解码、状态内容或视觉物理QA认证。

原来源清单将Genesis T15和Isaac T01–T10登记在另一个固定版本仓库，不能因为它们不在当前主仓库就认定媒体不存在。旧清单与当前发布的T06/T09扫描范围也有差异；禁止用新轴或其他版本替换未匹配记录。需先核验真实版本、配置对应关系和科学QA，再冻结。

T14五个完整组对应60/20/20；不拆组凑80/10/10。数值扫描区间、实际资产/QA与跨引擎配置映射尚未认证，Genesis T13未进入原清单，故当前`release_ready=false`。正式冻结须重新依据完整证据分组，候选分配不能预先当作最终版本。

## 证据与正式冻结

`--evidence evidence.jsonl` 接收每条record的真实来源与审核收据：

- `record_id`及`identity`的`sample_id/engine/revision/release`；
- `videos`包含cam01/02/03的`path/sha256`，`state`含`path/sha256`；
- `receipt`为可读JSON的`path/sha256`，内容须逐项绑定相同身份、资产、审核与标签；
- `checks`逐项认证解码同步、状态时间/单位/对象、运行参数、事件标签、视觉物理QA、重复与跨引擎映射。键名见脚本的`CHECKS`；工具校验收据，不替代实际科学QA；
- `sampling`含经核验的`kind`（global/critical）、`family_id`、非负整数`propagation_depth`；
- 扫描记录的`scan`含真实`parameter/unit/value/low/high/interval_id/family_id/controls_sha256`及`boundary_guards_reviewed=true`。共享端点或重叠区间整组绑定，不从p001编号推断数值；
- 已核验配置/临界族可指定`physical_configuration_group/critical_family_group`。额外对应关系用`--links links.jsonl`登记`record_ids/receipt_path/receipt_sha256`，冻结时验证实际收据内容。

加入`--freeze --out runs/joint_split_v3_release_v1`后，仅在证据、目标非零事件覆盖、可行组覆盖及待处理/冲突全部解决时写正式版本；否则拒绝冻结。冻结版本不覆盖，改动用新版本。训练只能经`load_training_split(directory, split)`加载，候选及内容SHA变化均拒绝。

`training_sampling_weights(directory)`仅对冻结train返回按事件、族和实际传播深度平衡的轨迹权重，不启动训练或编造标签。三视角可在已分配轨迹内选择，不能跨集合。

默认用1038例开发CSV记录指标开发组闭包；`--historical-exposure prior_attempts.json`可补充`prior_prediction_trajectory_ids`。暴露仅披露，不删除样本；未发现历史访问不等于独立盲测。生成模型事件留出与评测指标开发边界分别报告。
