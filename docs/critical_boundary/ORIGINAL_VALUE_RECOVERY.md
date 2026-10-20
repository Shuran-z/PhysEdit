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

## 2026-10-19继续执行：发布参数与补算结果

T12目标由用户明确为**纸巾盒最大三维位移达到0.01米**，取整条轨迹相对首帧的最大位移，不使用最终位移代替。固定其余物理条件，分别按速度、摩擦、目标质量建条件扫描；不强行把联合网格改称原来的三个临界族。

本轮新增可重复执行的入口：

```powershell
python -m scripts.recover_t03_parameter_headers
python -m scripts.recover_t03_original_event_reports
python -m scripts.bind_t03_current_parameters
python -m scripts.bind_t11_current_star_parameters
python -m scripts.recover_t11_published_final_states
python -m scripts.supplement_t11_published_boundaries
python -m scripts.supplement_t12_published_boundaries
python -m scripts.register_t15_all_context_distances
python -m scripts.combine_recovered_boundary_distances
```

最后一个入口实际合并已恢复距离与补算区间，输出`combined_distance_inputs.jsonl`、`combined_distance_inputs.csv`及`combined_all20_summary.json`。按场景、引擎、revision、参数族、事件与局部区间保留来源，不合并不同事件边界，不丢弃两侧样本。各来源可能覆盖同一条视频，分类数量不能直接相加。渲染star距离另列，不冒充已经求解的转变值；T19旧版继续标记停用。

T15已将原60组及40组扩展扫描对应到全部60个临界族上下文的540条视频，配置哈希和实际物体参数逐条对应。79个局部区间中71个按原后端完成细化，8个保留原较粗区间；540条视频均保留距离，未因反演或画面准入排除。

T03的880条当前发布参数头、880份原仿真事件报告已读回，参数无冲突。局部转变区间来自同版本原报告，不要求先下载全部逐帧状态。T11按当前有限推力配方解释历史速度坐标；不得把标称速度当成实际初速度。T12已从现有发布轨迹提取76个局部区间，覆盖216条视频；更细求解在原p26部署等待空闲GPU，不抢占其他进程。

T06/T09另有280/580条原注释文件在发布配置声明的旧路径下存续，已恢复其参数和实际物体配置、施力及求解配置对应。两份源文件有非JSON尾部，保留源文件与哈希，单独记录首个完整210帧文档及尾部异常。T06按原必需相邻接触链提取92个局部事件区间，为112条视频登记距离；与T08一样，保留原扫描不同种子，不声称固定种子下的精确阈值。T08为213条视频登记120个原扫描转变区间。

用户明确T09继续采用原“局部／整体坍塌”判据，不改成1厘米运动阈值。原数值判定脚本尚未找回。末态层间接触诊断不能代替该判据，单独保存在诊断文件中，不接入正式临界距离目录。文件存在、参数读回、原值求解完成是不同状态；没有求出的参数族继续记未完成。

T11当前发布的880条末态已全部按发布注释和配置SHA256对应，零读取失败。按原分析器“最终质心低于桌面0.20米”分别记录三个物体跌落；结合四个原控制配方，得到121个局部事件区间，为287条不同视频登记距离。质量筛查结果不参与这一步筛选。修复样本的非控制物理差异继续留在条件组中，不混成一个阈值。

20个场景尚未全部完成。T19新版仍在重渲染；旧版不会因已恢复历史距离而重新启用。T14仍采用用户指定旧版笔穿通道，T14S单独保存。
