# 原参数族搜索恢复与补算状态

更新：2026-10-18。**未完成20个场景全部族/上下文的临界值绑定。** 不把配置已找回、原合同中心点已找回、数值转变区间已验证混为一个完成状态。

完整20场景表、JSON与CSV：`review/scene_family_completion_20261018/ALL20_PROGRESS.md`、`all20_evidence_progress.json`、`all20_evidence_progress.csv`。

本轮恢复T06/T09/T10/T12的全部3,520份冻结发布配置，使用发布时的revision获取。连同既有来源，历史Genesis清单16,081条轨迹中15,047条有配置候选。这不是15,047条已取得可评分边界。T03后修复155条、T04的879条原配置路径仍未找回；T04已证实发布metadata中保存对象spec，后续从该来源继续。T13不在这份历史清单中，必须另接新版发布，不得解释成T13没有数据。

原字段纠正：T06是impact_force/gap；T09是pull_force/layer_friction；不能按文件名把前者当冲量、后者当抽取距离。T11 r011初速度为零并使用分段外力，旧速度族名称须与实际执行字段核对。

T15沿用V11原Genesis后端和配置完成152次补算，143次通过原QA，失败全部保留。本次只覆盖bg01_home_ase/g03_earth：

- A初速出现多次转变，保留[2.142,2.151]与[2.151,2.160] m/s；不能声称唯一阈值或搜索已穷尽。
- B支撑参数的跌落转变区间收窄到[0.103125,0.1075] m。
- C手机声明扫描坐标的命中窗口两边界为[-0.125,-0.1140625]和[0.165,0.175] m。
- 60个原族条件组已恢复，不能把上述一个条件的补算外推为60组均完成。

4条H3结果通过原state哈希、参数值、目标事件、固定物理上下文绑定到A族补算区间。case02虽来自原cfB样本，但其固定速度上下文与本次A扫描一致；该绑定只表达条件速度响应，未把原cfB重新归类为cfA。

实际运行入口：

```powershell
python -X utf8 scripts/collect_t15_resolve_context.py
python -X utf8 -m scripts.bind_t15_supplemental_search
python -X utf8 -m physedit.boundary score --run-dir review/h3_delivery_audit_20261016/recomputed_with_cv2/evaluation --annotations review/h3_delivery_audit_20261016/t15_h3_b06b492_20261016/evaluation/events.jsonl --screening review/h3_delivery_audit_20261016/recomputed_with_cv2/screen/screening.jsonl --boundary-bindings review/scene_family_completion_20261018/h3_supplemental_bindings.json --out <新的评分文件路径>
```

最新结果是`h3_supplemental_refined_score.json`。4/4绑定观测区间；balanced accuracy 25%、coupled PairAcc 0、EventExact 0、事件有效覆盖率50%、反演有效覆盖率0。NearAcc仍为null：当前接入的是不完备、多转变的观测区间，没有将其强行变成唯一临界点的正式分桶。上述分数来自已有开发标注，不是新增独立人工验证。

T14：880条三机位媒体SHA256已经匹配。进一步读取192份原标定配置，发现constraint_timeconst=.005，而880条正式配置均为.001。原区间和距离继续保存，但暂不认证为正式配置边界；须完成同配置验证/补算。具体证据为`t14_calibration_configs.json`、`t14_solver_profile_comparison.json`。

随后已实际补验T14 bg03/地球A族的两条正式配置：.018m为two_sided_wedge，.019m为passed_and_hit_eraser，原分析器成功输出，区间仍跨越passed_channel事件。p25/p26原renderer代码哈希一致，所用配置哈希与发布核验记录一致。`t14_formal_probe_distance_registry.json`已调用现有distance函数计算两条区间距离，仅作观测区间诊断；其余条件、重复验证和正式答案state绑定仍待完成。这是T15之外新增的2次后端复算，不包含在上面的152次T15统计中。

Genesis/Isaac分别登记。Isaac T16/T19的360条是原搜索来源匹配候选，后修复版本尚未全部核对，不能直接视为360条正式可评分距离。T20原Isaac有实际measured_bracket，不因旧清单没有该来源而忽略它。

相关边界恢复、绑定和评分32项unittest通过。所有新增操作保留原视频、两侧样本和评分总分母。本轮改动尚未推送GitHub。


## 2026-10-18 后续恢复与补算

- T02：45份原运行metadata已回收；880条发布配置的对象、求解器、时间设置与其固定物理上下文匹配。15个族×重力的原事件转变区间已接入距离登记。A判撞书接触，B判被阻挡探针接触书，C判信号物移动5cm；不得把B偷换成未验证的解析倾倒阈值。正式输出原metadata路径880/880现已不可访问，仍须绑定发布旁文件及真值。
- T03：先前缺少的155条r032/r034配置已从固定发布revision全部取回，历史474条配置现已齐全；这不等于474条都完成边界认证。
- T06/T09/T10：原发布配置、原种子、原后端完成六轴12端点复算，每条210帧；仅使用较低分辨率raster渲染。T10追加6个原网格中间点，全部完成。支撑笔相对首帧最大三维位移超过原声明0.04m的转变区间为support_x=[0.1779,0.217]m、v_roll=[1.7428571,2.3142857]m/s。10条区间距离已登记；尚不声称该测量等同文件夹支撑丢失。
- Isaac旧搜索：T16 72条、T19 288条交付/源配置/QA哈希精确对应，区间距离已登记。
- Isaac修复搜索：恢复四个冻结release的60组校准记录，16组标记REPEAT_VALIDATED、44组REPAIR_REQUIRED。生产记录中59条与交付配置/QA哈希及深度一致，分别为T17 30、T18 10、T19 19；已按修复后的独立参数轴登记距离。其余不能根据旧参数字段推断。
- T20：原28组252条源输入哈希核对通过，已登记区间距离。它们不在旧冻结清单里，单列来源台账，未冒充已对应当前发布视频。

当前旧库存22,801条轨迹中，1,311条已有事件区间距离登记；另有T20原来源252条。正式NearAcc登记仍为0：这是当前完成事件真值/版本身份/边界资格/归一化及near桶登记的数量，不是断言数据没有临界点或不能使用。H3四条仍只有观测区间绑定，NearAcc为null，不编造模型分数。

入口：`python -X utf8 -m scripts.audit_nearacc_readiness`从逐条证据计算资格，不再写死参考计数；`nearacc_readiness_ledger.jsonl`记录每条原因。新增6项计数测试加原32项边界恢复/绑定/评分测试，共38项通过。

T04固定发布metadata继续按文件回收，未完成；所有20场景的对应/补算任务也尚未全部完成。当前表见`review/scene_family_completion_20261018/ALL20_PROGRESS.md`。原视频、临界两侧样本均保留。本轮改动未推送GitHub。


## 2026-10-18 数值真值与评分答案接入（本轮中间快照）

本轮495条完成数值真值、版本来源和原设计范围归一化：Isaac T16/T19共360条，Genesis T02已审计135条；其中375条确定属于near桶，分布于42个同时具有近邻正负类的上下文族。不是最终测试集计数，也不是375条模型输出已完成评分。

现有正式视觉准入登记仍为0：参考事件可观察性尚未闭环，候选答案全部保留。导出candidate_reference_answers.jsonl和admitted_near_reference_answers.jsonl，并在运行入口阻止pending参考进入正式运行；这项准入发生在生成前，绝不用于从生成结果分母中剔除坏视频。

T04/T05已按原正式构建器匹配真实物理字段；T04抽取速度/摩擦/杯位置三族分别登记。T05有105条原配置携带接触稳定性修复，实际间隙变化，不与旧版阈值混用。对应记录为t04_t05_profile_bindings.json。

T06/T09的原后端12个中间点补算正在运行，输出独立目录t06_t09_interior_raster_20261018，保留原种子和物理参数。T02原始状态及T04缺失配置回收继续。20场景尚未全部闭环；后续计数以nearacc_readiness_summary.json和reference_answer_export_summary.json为准。40项回归测试通过。
