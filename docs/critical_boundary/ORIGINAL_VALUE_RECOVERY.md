# 原临界值恢复与距离导出

2026-10-19用户确定本任务顺序：先找回20个场景原来算好的临界参考，匹配发布视频参数并计算距离；确实缺失才补算。画面、事件标注、反演适用性及重复性验证另列，不阻止原值与距离导出。

## 直接执行

```powershell
python -X utf8 -m scripts.export_original_boundary_distances
```

输出目录：`review/scene_family_completion_20261018/original_value_distance_ledger/`。

- `sample_distances.csv`及同名JSONL：原标定中心或原搜索区间、实际发布样本参数、对应视频路径、距离、源文件及哈希。
- `recorded_rendering_star_distances.csv`及JSONL：直接读原渲染三分支记录中的star参数并计算距离。记录原字段用途；不因文件名中有star，就升级为数值求解证明。T08按原重复编号分别对应，避免把不同重复的star混为一个值。
- `ALL20_ORIGINAL_VALUES.md`及`all20_summary.json`：逐场景记录已恢复数值和仍待查找项。

若原记录为单值：带符号距离为`theta - original_critical_value`，绝对距离取其绝对值。若原记录只给`[a,b]`：距离下界为`max(a-theta,theta-b,0)`，上界为`max(abs(theta-a),abs(theta-b))`；不凭空输出精确点。

## 搜索原记录

```powershell
python -X utf8 -m scripts.find_original_critical_numbers --host p25
python -X utf8 -m scripts.find_original_critical_numbers --host p26
python -X utf8 -m scripts.find_original_critical_numbers --host p29
```

只读现有manifest、report和contract，不调用求解器、不判视频。输出数字、完整JSON字段路径、原文件路径和SHA256。扫描是有范围和时长上限的；未命中不能直接解释为从未计算，不据此自动补算。既有缓存的原报告也继续作为来源。

## 对应原则

1. 场景、引擎、发布revision、原参数族及固定条件对应后使用原记录。T14继续使用旧笔穿通道版；T14S独立。
2. 保留原始中心值、区间和渲染star各自的来源，不相互覆盖。原版本差异是一个可见字段，不与画面审核混在一起。
3. 两侧视频全部保留。修复后的实际参数与请求参数分列；不能悄悄拿请求参数冒充实际物理参数。
4. T19旧版只保留历史距离，按用户决定停用；不冒充正在重渲染的新版本。
5. 原记录确实缺失的族才进入补算清单；额外数值复验单独存放。距离导出不依赖VLM、SAM、人工标注或物理反演是否成功。

这份表不是模型评分表，也不以正式NearAcc参考准入数量衡量“原值找回”的进度。
