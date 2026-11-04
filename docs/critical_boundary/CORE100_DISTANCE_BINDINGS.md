# Core100 临界距离接入结果

这是参考参数与临界证据的接入状态，不是生成模型成绩。

100条：原参数族已接数值参考 94，未完成 6，已确认不适用 0。

另有 2 条目前仅有补充方向参考，不能计入原参数族完成数。包含这些方向的参考登记总数为 96（边界区间94、原校准值2）。

原21条统一不适用结论已撤回。有限扫描无翻转不能证明没有原临界值；原族未核清的保留待对齐。原校准点、原采样中心与已测边界区间分别记录，不冒充精确物理阈值。

| 场景 | 原参数族已接 | 原参数族未完成 | 仅补充方向 | 已确认不适用 |
|---|---:|---:|---:|---:|
| T01 | 5 | 0 | 0 | 0 |
| T02 | 5 | 0 | 0 | 0 |
| T03 | 5 | 0 | 0 | 0 |
| T04 | 4 | 1 | 0 | 0 |
| T05 | 4 | 1 | 0 | 0 |
| T06 | 5 | 0 | 0 | 0 |
| T07 | 5 | 0 | 0 | 0 |
| T08 | 5 | 0 | 0 | 0 |
| T09 | 5 | 0 | 0 | 0 |
| T10 | 3 | 2 | 0 | 0 |
| T11 | 3 | 2 | 2 | 0 |
| T12 | 5 | 0 | 0 | 0 |
| T13 | 5 | 0 | 0 | 0 |
| T14 | 5 | 0 | 0 | 0 |
| T15 | 5 | 0 | 0 | 0 |
| T16 | 5 | 0 | 0 | 0 |
| T17 | 5 | 0 | 0 | 0 |
| T18 | 5 | 0 | 0 | 0 |
| T19 | 5 | 0 | 0 | 0 |
| T20 | 5 | 0 | 0 | 0 |

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

- T04_C01：已读取原状态并重判27个有效参数点，事件标签集合{'original_full_chain': [0]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。
- T05_C01：已读取原状态并重判41个有效参数点，事件标签集合{'gate_passage': [0]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。
- T10_C01：已读取原状态并重判50个有效参数点，事件标签集合{'support_pen_displacement_reaches_source_threshold': [1]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。
- T10_C02：已读取原状态并重判50个有效参数点，事件标签集合{'support_pen_displacement_reaches_source_threshold': [1]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。
- T11_C01：已读取原状态并重判15个有效参数点，事件标签集合{'t11_driver_eraser_final_center_below_minus_10cm': [1], 't11_relay_pencil_case_final_center_below_minus_10cm': [1], 't11_eyeglasses_case_final_center_below_minus_10cm': [1]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。
- T11_C02：已读取原状态并重判15个有效参数点，事件标签集合{'t11_driver_eraser_final_center_below_minus_10cm': [1], 't11_relay_pencil_case_final_center_below_minus_10cm': [1], 't11_eyeglasses_case_final_center_below_minus_10cm': [1]}。当前没有异侧端点，原参数族临界距离仍未完成；未判不适用。

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
| T03_C02 | lower_phone_com_edge_distance_m | 0.1 | 5 | 已接数值参考 | 区间跨分界 |
| T03_C03 | lower_phone_com_edge_distance_m | 0.1 | 5 | 已接数值参考 | 区间跨分界 |
| T03_C04 | book_initial_speed_mps | 0.47 | 5 | 已接数值参考 | far, mid, 区间跨分界 |
| T03_C05 | book_initial_speed_mps | 0.73 | 5 | 已接数值参考 | far |
| T04_C01 | commanded_support_extraction_speed_mps | 0.15 | 5 | 原族待对齐 | 待定 |
| T04_C02 | commanded_support_extraction_speed_mps | 0.15 | 5 | 已接数值参考 | far, 区间跨分界 |
| T04_C03 | commanded_support_extraction_speed_mps | 0.15 | 5 | 已接数值参考 | far |
| T04_C04 | commanded_support_extraction_speed_mps | 0.1 | 5 | 已接数值参考 | far, 区间跨分界 |
| T04_C05 | commanded_support_extraction_speed_mps | 0.2 | 5 | 已接数值参考 | far |
| T05_C01 | phone_tray_friction_coefficient | 0.049 | 5 | 原族待对齐 | 待定 |
| T05_C02 | phone_tray_friction_coefficient | 0.049 | 6.83333 | 已接数值参考 | far |
| T05_C03 | phone_tray_friction_coefficient | 0.049 | 6.83333 | 已接数值参考 | near |
| T05_C04 | gap_ratio | 1.11 | 6.83333 | 已接数值参考 | far |
| T05_C05 | gap_ratio | 1.16 | 6.83333 | 已接数值参考 | far |
| T06_C01 | gap | 0.0571429 | 4.1 | 已接数值参考 | far |
| T06_C02 | gap | 0.0571429 | 4.1 | 已接数值参考 | far |
| T06_C03 | gap | 0.0571429 | 4.1 | 已接数值参考 | far |
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
| T09_C01 | pull_force | 15.5714286 | 4.1 | 已接数值参考 | far |
| T09_C02 | pull_force | 15.5714286 | 4.1 | 已接数值参考 | far |
| T09_C03 | pull_force | 15.5714286 | 4.1 | 已接数值参考 | mid |
| T09_C04 | layer_friction | 0.2 | 4.1 | 已接数值参考 | near |
| T09_C05 | layer_friction | 0.5571429 | 4.1 | 已接数值参考 | far |
| T10_C01 | support_x | 0.08 | 4.1 | 原族待对齐 | 待定 |
| T10_C02 | support_x | 0.08 | 4.1 | 原族待对齐 | 待定 |
| T10_C03 | support_x | 0.08 | 4.1 | 已接数值参考 | far |
| T10_C04 | support_x | 0.217 | 4.1 | 已接数值参考 | 区间跨分界 |
| T10_C05 | support_x | 0.1909 | 4.1 | 已接数值参考 | mid |
| T11_C01 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 仅补充方向；原参数族未完成 | 多方向分别登记；原主轴记录保留，评分须显式指定方向 |
| T11_C02 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 仅补充方向；原参数族未完成 | 多方向分别登记；原主轴记录保留，评分须显式指定方向 |
| T11_C03 | joint_global_configuration | {"driver_initial_speed_mps": 3.05, "relay_case_gap_m": 0.024, "case_edge_margin_m": 0.055, "relay_block_mass_kg": 0.13, "case_friction_coefficient": 0.08} | 5 | 已接数值参考 | 多方向分别登记；原主轴记录保留，评分须显式指定方向 |
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
| T14_C03 | channel_throat_width_m | 0.0325 | 5 | 已接数值参考 | 多方向分别登记；原主轴记录保留，评分须显式指定方向 |
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
| T20_C01 | box_cup_gap | 0.0329090909 | 5 | 已接数值参考 | 多方向分别登记；原主轴记录保留，评分须显式指定方向 |
| T20_C02 | book_drive_speed | 3.04545455 | 5 | 已接数值参考 | far |
| T20_C03 | book_drive_speed | 3.04545455 | 5 | 已接数值参考 | far |
| T20_C04 | book_drive_speed | 3.36363636 | 5 | 已接数值参考 | far |
| T20_C05 | book_drive_speed | 3.68181818 | 5 | 已接数值参考 | far |

## 多方向条件边界

旧主轴的参数与证据保留；多方向结果不压成一个全局最近距离。调用 bind_answer 时必须指定 axis。

| 案例 | 方向 | 原参数值 | 事件 | 临界区间 |
|---|---|---:|---|---|
| T11_C01 | driver_precontact_push_force_N | 0.2633333333333333 | t11_driver_eraser_final_center_below_minus_10cm | [0.02431640625, 0.024462890624999997] |
| T11_C01 | driver_precontact_push_force_N | 0.2633333333333333 | t11_relay_pencil_case_final_center_below_minus_10cm | [0.02255859375, 0.0228515625] |
| T11_C01 | driver_precontact_push_force_N | 0.2633333333333333 | t11_eyeglasses_case_final_center_below_minus_10cm | [0.0205078125, 0.020654296875] |
| T11_C02 | driver_precontact_push_force_N | 0.2633333333333333 | t11_driver_eraser_final_center_below_minus_10cm | [0.03251953125, 0.032812499999999994] |
| T11_C02 | driver_precontact_push_force_N | 0.2633333333333333 | t11_relay_pencil_case_final_center_below_minus_10cm | [0.031201171874999996, 0.031347656249999994] |
| T11_C02 | driver_precontact_push_force_N | 0.2633333333333333 | t11_eyeglasses_case_final_center_below_minus_10cm | [0.029150390624999994, 0.029296874999999997] |
| T11_C02 | case_friction_coefficient | 0.08 | t11_driver_eraser_final_center_below_minus_10cm | [1.5750000000000002, 1.5765625] |
| T11_C02 | case_friction_coefficient | 0.08 | t11_relay_pencil_case_final_center_below_minus_10cm | [1.5953125, 1.596875] |
| T11_C02 | case_friction_coefficient | 0.08 | t11_driver_eraser_final_center_below_minus_10cm | [1.2, 2.0] |
| T11_C02 | case_friction_coefficient | 0.08 | t11_relay_pencil_case_final_center_below_minus_10cm | [1.2, 2.0] |
| T11_C03 | original_G_global_path | 0.7209977526762721 | t11_driver_eraser_final_center_below_minus_10cm | [0.388892197576643, 0.389468606164474] |
| T11_C03 | original_G_global_path | 0.7209977526762721 | t11_relay_pencil_case_final_center_below_minus_10cm | [0.3185703498612672, 0.3191467584490981] |
| T11_C03 | original_G_global_path | 0.7209977526762721 | t11_eyeglasses_case_final_center_below_minus_10cm | [0.2205808899300058, 0.22115729851783675] |
| T14_C03 | marker_initial_yaw_deg | 4.5 | passed_channel | [5.1796875, 5.1875] |
| T14_C03 | marker_initial_yaw_deg | 4.5 | terminal_contact_after_full_exit | [5.171875, 5.1796875] |
| T14_C03 | trigger_impulse_magnitude_Ns | 0.028414799999999997 | passed_channel | [0.023184263671874997, 0.023206289062499996] |
| T14_C03 | trigger_impulse_magnitude_Ns | 0.028414799999999997 | terminal_contact_after_full_exit | [0.023283377929687495, 0.023294390624999998] |
| T14_C03 | channel_throat_width_m | 0.0325 | passed_channel | [0.0305078125, 0.030566406249999997] |
| T14_C03 | channel_throat_width_m | 0.0325 | passed_channel | [0.039941406250000006, 0.04] |
| T14_C03 | channel_throat_width_m | 0.0325 | passed_channel | [0.04046875, 0.04052734375] |
| T14_C03 | channel_throat_width_m | 0.0325 | terminal_contact_after_full_exit | [0.0305078125, 0.030566406249999997] |
| T14_C03 | channel_throat_width_m | 0.0325 | terminal_contact_after_full_exit | [0.039941406250000006, 0.04] |
| T20_C01 | book_drive_speed_mps | 2.0 | complete_propagation_original | [0.89453125, 0.896484375] |

## 端点重复运行核查

原窄区间和距离保留。重复运行矛盾或尚未完成核查的区间，不作为可用评分边界；不修改原事件真值、不判不适用。
T11_C02原运行的数值种子为None，保留该设置不等于固定数值种子。逐次GPU身份、实际初始化种子和运行后端随证据保存。

| 案例 | 方向 | 事件 | 重复运行结果 | 端点标签 |
|---|---|---|---|---|
| T11_C02 | case_friction_coefficient | t11_driver_eraser_final_center_below_minus_10cm | discordant | [[1, 0, 0, 0], [0, 0, 0]] |
| T11_C02 | case_friction_coefficient | t11_relay_pencil_case_final_center_below_minus_10cm | discordant | [[1, 0, 1], [0, 0, 0]] |
| T11_C02 | case_friction_coefficient | t11_driver_eraser_final_center_below_minus_10cm | reproduced | [[1, 1], [0, 0]] |
| T11_C02 | case_friction_coefficient | t11_relay_pencil_case_final_center_below_minus_10cm | reproduced | [[1, 1], [0, 0]] |
