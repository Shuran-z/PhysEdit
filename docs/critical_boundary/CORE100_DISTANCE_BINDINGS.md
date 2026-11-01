# Core100 临界距离接入结果

这是参考参数与临界证据的接入状态，不是生成模型成绩。

100条：已接数值参考 85（边界区间83、原校准值2）；已确认不适用 0；原族/事件/观察窗仍待对齐 15。

原21条统一不适用结论已撤回。有限扫描无翻转不能证明没有原临界值；原族未核清的保留待对齐。原校准点、原采样中心与已测边界区间分别记录，不冒充精确物理阈值。

| 场景 | 已接数值参考 | 已确认不适用 | 待对齐 |
|---|---:|---:|---:|
| T01 | 5 | 0 | 0 |
| T02 | 5 | 0 | 0 |
| T03 | 3 | 0 | 2 |
| T04 | 3 | 0 | 2 |
| T05 | 4 | 0 | 1 |
| T06 | 3 | 0 | 2 |
| T07 | 5 | 0 | 0 |
| T08 | 5 | 0 | 0 |
| T09 | 4 | 0 | 1 |
| T10 | 3 | 0 | 2 |
| T11 | 2 | 0 | 3 |
| T12 | 5 | 0 | 0 |
| T13 | 5 | 0 | 0 |
| T14 | 4 | 0 | 1 |
| T15 | 5 | 0 | 0 |
| T16 | 5 | 0 | 0 |
| T17 | 5 | 0 | 0 |
| T18 | 5 | 0 | 0 |
| T19 | 5 | 0 | 0 |
| T20 | 4 | 0 | 1 |

## 接入命令

```text
python -m physedit.core100_bindings status --verify-evidence
python -m physedit.core100_bindings export --out core100_distance_reference.jsonl
```

评分代码 `annotation_site/critical_results.py` 已读取此表。匹配同时检查参考视频哈希和观察时长，不能仅按案例ID套用。
数值接入不自动批准视频质量，也不生成模型事件标签。完整EventExact仍使用原事件协议的全部标签与时序要求。
此参考表只供评分器使用；不得把参考事件答案或临界值发给视频生成器、VLM事件裁判。
有限扫描无翻转只作为诊断；原族、事件或窗口未核清时保持待对齐，不直接判不适用。
原始区间、条件补算和物理诊断分别保留；区间跨越Near/Mid/Far阈值时保留未定，不取中点强行分组。

## 未完成项

- T03_C02：已找回原C族采样中心0.035；当前是global_C_05、r032发布样本。保留中心，但不能把它自动当作此固定上下文的求解阈值。
- T03_C03：原r014的global_C_05与原C族有关；已有新有限网格不翻转，但尚未绑定该发布版本的原搜索值，不能判不适用。
- T04_C01：原support_release速度族有0.1/0.15/0.2三分支；此前用末端full_chain不翻转判断整族不适用，原支撑释放判据尚需对齐。
- T04_C02：原support_release速度族有0.1/0.15/0.2三分支；此前用末端full_chain不翻转判断整族不适用，原支撑释放判据尚需对齐。
- T05_C01：原global_16改变phone_tray_friction，之前误统一按gap_ratio扫描；这不能判定原摩擦轴不适用。
- T06_C02：当前是Genesis gap族；旧台账中已恢复的impact_force/J族边界不能移植到gap。有限gap扫描不翻转不等于原值不存在。
- T06_C03：当前是Genesis gap族；旧台账中已恢复的impact_force/J族边界不能移植到gap。有限gap扫描不翻转不等于原值不存在。
- T09_C01：此前使用末帧仍接触桌面，原要求是散塌后曾接触桌面；已重读现有8点曾接触标签，均0，但仍不能据此认定不适用。
- T10_C01：原support_x族身份已确定；现有旧边界主要对应地球条件，不能套到月球/火星。仍需同重力、同事件原搜索记录。
- T10_C02：原support_x族身份已确定；现有旧边界主要对应地球条件，不能套到月球/火星。仍需同重力、同事件原搜索记录。
- T11_C01：原G_global_06是速度、间距、边缘、质量联合点；之前只按速度坐标扫描，不能代表A/B/C/D四个原族。
- T11_C02：原G_global_06是速度、间距、边缘、质量联合点；之前只按速度坐标扫描，不能代表A/B/C/D四个原族。
- T11_C03：原G_global_06是速度、间距、边缘、质量联合点；之前只按速度坐标扫描，不能代表A/B/C/D四个原族。
- T14_C03：原G_global_07是间隙、姿态、进入速度联合覆盖；不能用一次固定姿态的A轴CPU扫描证明原A/B/C族都不适用。
- T20_C01：已有同来源局部接触区间，但标签是book-can末态接触；当前族为box_cup_gap、扫描目标为完整传播。二者不能混用，也不能据完整传播不变否定原局部边界。

## 100条逐项明细

| 案例 | 原参数轴 | 参数值 | 观察窗(s) | 距离接入状态 | 分组 |
|---|---|---:|---:|---|---|
| T01_C01 | chain_surface_friction_coefficient | 0.2 | 5 | 已接数值参考 | far |
| T01_C02 | chain_surface_friction_coefficient | 0.2 | 5 | 已接数值参考 | far |
| T01_C03 | chain_surface_friction_coefficient | 0.2 | 5 | 已接数值参考 | far |
| T01_C04 | chain_surface_friction_coefficient | 0.29 | 5 | 已接数值参考 | far |
| T01_C05 | chain_surface_friction_coefficient | 0.43 | 5 | 已接数值参考 | 区间跨分界 |
| T02_C01 | probe_initial_speed_mps | 0.1770508 | 6.83333 | 已接数值参考 | 原校准值距离，非精确边界 |
| T02_C02 | probe_initial_speed_mps | 0.1786225 | 6.83333 | 已接数值参考 | 原校准值距离，非精确边界 |
| T02_C03 | probe_initial_speed_mps | 0.3217655 | 5 | 已接数值参考 | 区间跨分界 |
| T02_C04 | probe_initial_speed_mps | 0.040001 | 5 | 已接数值参考 | far |
| T02_C05 | probe_initial_speed_mps | 0.2904583 | 5 | 已接数值参考 | 区间跨分界 |
| T03_C01 | lower_phone_com_edge_distance_m | 0.1 | 5 | 已接数值参考 | far |
| T03_C02 | lower_phone_com_edge_distance_m | 0.1 | 5 | 原族待对齐 | 待定 |
| T03_C03 | lower_phone_com_edge_distance_m | 0.1 | 5 | 原族待对齐 | 待定 |
| T03_C04 | book_initial_speed_mps | 0.47 | 5 | 已接数值参考 | far, mid, 区间跨分界 |
| T03_C05 | book_initial_speed_mps | 0.73 | 5 | 已接数值参考 | far |
| T04_C01 | commanded_support_extraction_speed_mps | 0.15 | 5 | 原族待对齐 | 待定 |
| T04_C02 | commanded_support_extraction_speed_mps | 0.15 | 5 | 原族待对齐 | 待定 |
| T04_C03 | commanded_support_extraction_speed_mps | 0.15 | 5 | 已接数值参考 | far |
| T04_C04 | commanded_support_extraction_speed_mps | 0.1 | 5 | 已接数值参考 | far, 区间跨分界 |
| T04_C05 | commanded_support_extraction_speed_mps | 0.2 | 5 | 已接数值参考 | far |
| T05_C01 | phone_tray_friction_coefficient | 0.049 | 5 | 原族待对齐 | 待定 |
| T05_C02 | phone_tray_friction_coefficient | 0.049 | 6.83333 | 已接数值参考 | far |
| T05_C03 | phone_tray_friction_coefficient | 0.049 | 6.83333 | 已接数值参考 | near |
| T05_C04 | gap_ratio | 1.11 | 6.83333 | 已接数值参考 | far |
| T05_C05 | gap_ratio | 1.16 | 6.83333 | 已接数值参考 | far |
| T06_C01 | gap | 0.0571429 | 4.1 | 已接数值参考 | far |
| T06_C02 | gap | 0.0571429 | 4.1 | 原族待对齐 | 待定 |
| T06_C03 | gap | 0.0571429 | 4.1 | 原族待对齐 | 待定 |
| T06_C04 | impact_force | 1.4285714 | 4.1 | 已接数值参考 | mid |
| T06_C05 | impact_force | 1.6428571 | 4.1 | 已接数值参考 | near |
| T07_C01 | phone_surface_friction_coefficient | 0.25 | 5 | 已接数值参考 | far |
| T07_C02 | phone_surface_friction_coefficient | 0.25 | 5 | 已接数值参考 | far |
| T07_C03 | phone_surface_friction_coefficient | 0.25 | 5 | 已接数值参考 | far |
| T07_C04 | phone_surface_friction_coefficient | 0.2 | 5 | 已接数值参考 | far |
| T07_C05 | phone_surface_friction_coefficient | 0.28 | 5 | 已接数值参考 | far |
| T08_C01 | lower_impactor_initial_speed_mps | 0.868618604 | 5 | 已接数值参考 | far |
| T08_C02 | lower_impactor_initial_speed_mps | 1.3144939 | 5 | 已接数值参考 | far |
| T08_C03 | lower_impactor_initial_speed_mps | 2.1375 | 5 | 已接数值参考 | far |
| T08_C04 | lower_impactor_initial_speed_mps | 1.47 | 5 | 已接数值参考 | far |
| T08_C05 | lower_impactor_initial_speed_mps | 2.058 | 5 | 已接数值参考 | far, 区间跨分界 |
| T09_C01 | pull_force | 15.5714286 | 4.1 | 原族待对齐 | 待定 |
| T09_C02 | pull_force | 15.5714286 | 4.1 | 已接数值参考 | far |
| T09_C03 | pull_force | 15.5714286 | 4.1 | 已接数值参考 | mid |
| T09_C04 | layer_friction | 0.2 | 4.1 | 已接数值参考 | near |
| T09_C05 | layer_friction | 0.5571429 | 4.1 | 已接数值参考 | far |
| T10_C01 | support_x | 0.08 | 4.1 | 原族待对齐 | 待定 |
| T10_C02 | support_x | 0.08 | 4.1 | 原族待对齐 | 待定 |
| T10_C03 | support_x | 0.08 | 4.1 | 已接数值参考 | far |
| T10_C04 | support_x | 0.217 | 4.1 | 已接数值参考 | 区间跨分界 |
| T10_C05 | support_x | 0.1909 | 4.1 | 已接数值参考 | mid |
| T11_C01 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 原族待对齐 | 待定 |
| T11_C02 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 原族待对齐 | 待定 |
| T11_C03 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 原族待对齐 | 待定 |
| T11_C04 | driver_initial_speed_command_mps | 2.9 | 5 | 已接数值参考 | far |
| T11_C05 | driver_initial_speed_command_mps | 3.1 | 5 | 已接数值参考 | far |
| T12_C01 | stapler_initial_speed_mps | 1 | 5 | 已接数值参考 | far |
| T12_C02 | stapler_initial_speed_mps | 1.6 | 5 | 已接数值参考 | far |
| T12_C03 | stapler_initial_speed_mps | 1.9 | 5 | 已接数值参考 | mid |
| T12_C04 | stapler_initial_speed_mps | 1.6 | 5 | 已接数值参考 | mid |
| T12_C05 | stapler_initial_speed_mps | 2.05 | 5 | 已接数值参考 | far |
| T13_C01 | falling_book_edge_distance_m | 0.125 | 5 | 已接数值参考 | near |
| T13_C02 | falling_book_edge_distance_m | 0.125 | 5 | 已接数值参考 | near |
| T13_C03 | falling_book_edge_distance_m | 0.125 | 5 | 已接数值参考 | mid |
| T13_C04 | falling_book_edge_distance_m | 0.126 | 5 | 已接数值参考 | mid |
| T13_C05 | falling_book_edge_distance_m | 0.127 | 5 | 已接数值参考 | mid |
| T14_C01 | channel_throat_width_m | 0.0325 | 5 | 已接数值参考 | mid |
| T14_C02 | channel_throat_width_m | 0.0325 | 5 | 已接数值参考 | mid |
| T14_C03 | channel_throat_width_m | 0.0325 | 5 | 原族待对齐 | 待定 |
| T14_C04 | channel_throat_width_m | 0.018 | 5 | 已接数值参考 | far |
| T14_C05 | channel_throat_width_m | 0.019 | 5 | 已接数值参考 | far |
| T15_C01 | driver_book_initial_speed_mps | 1.4 | 5 | 已接数值参考 | far |
| T15_C02 | driver_book_initial_speed_mps | 1.95 | 5 | 已接数值参考 | far |
| T15_C03 | driver_book_initial_speed_mps | 3.12 | 5 | 已接数值参考 | far |
| T15_C04 | laptop_edge_margin_m | 0.085 | 5 | 已接数值参考 | far, mid |
| T15_C05 | laptop_edge_margin_m | 0.02 | 5 | 已接数值参考 | far |
| T16_C01 | support_angle_deg | 72.7586207 | 5 | 已接数值参考 | far |
| T16_C02 | support_angle_deg | 72.7586207 | 5 | 已接数值参考 | far |
| T16_C03 | support_angle_deg | 72.7586207 | 5 | 已接数值参考 | far |
| T16_C04 | support_angle_deg | 83.9655172 | 5 | 已接数值参考 | near |
| T16_C05 | support_angle_deg | 84.8275862 | 5 | 已接数值参考 | near |
| T17_C01 | can_initial_speed_mps | 1.61034483 | 5 | 已接数值参考 | far, mid |
| T17_C02 | can_initial_speed_mps | 1.61034483 | 5 | 已接数值参考 | far, 区间跨分界 |
| T17_C03 | can_initial_speed_mps | 1.61034483 | 5 | 已接数值参考 | far, mid |
| T17_C04 | can_initial_speed_mps | 0.946551724 | 6.4 | 已接数值参考 | near |
| T17_C05 | can_initial_speed_mps | 1.07931034 | 6.4 | 已接数值参考 | near |
| T18_C01 | contact_friction | 0.526896552 | 5 | 已接数值参考 | far |
| T18_C02 | contact_friction | 0.526896552 | 5 | 已接数值参考 | far |
| T18_C03 | contact_friction | 0.526896552 | 5 | 已接数值参考 | far |
| T18_C04 | overlap_length | 0.0582758621 | 5 | 已接数值参考 | far |
| T18_C05 | overlap_length | 0.0653448276 | 5 | 已接数值参考 | far |
| T19_C01 | impact_eccentricity_m | -0.0940625 | 6.96667 | 已接数值参考 | near |
| T19_C02 | impact_eccentricity_m | -0.09296875 | 6.96667 | 已接数值参考 | near |
| T19_C03 | impact_eccentricity_m | -0.0940625 | 6.96667 | 已接数值参考 | near |
| T19_C04 | impact_eccentricity_m | -0.09296875 | 6.96667 | 已接数值参考 | near |
| T19_C05 | impact_eccentricity_m | 0.14 | 6.96667 | 已接数值参考 | 区间跨分界 |
| T20_C01 | box_cup_gap | 0.0329090909 | 5 | 原族待对齐 | 待定 |
| T20_C02 | book_drive_speed | 3.04545455 | 5 | 已接数值参考 | far |
| T20_C03 | book_drive_speed | 3.04545455 | 5 | 已接数值参考 | far |
| T20_C04 | book_drive_speed | 3.36363636 | 5 | 已接数值参考 | far |
| T20_C05 | book_drive_speed | 3.68181818 | 5 | 已接数值参考 | far |
