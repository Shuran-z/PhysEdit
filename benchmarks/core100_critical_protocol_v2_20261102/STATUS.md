# Core100新版临界接入状态

本表由当前哈希登记生成；数值区间不等于模型成绩或参考画面准入。

99条有数值登记，其中包含原设置、上下文或事件凭据尚未核准的候选；另1条尚缺匹配版本的区间，不能视为100条已经完成。正式RGB距离评分准入88条，剩余12条待闭合；正式Near参考13条。

| 场景 | 案例 | 原族数值区间 | RGB距离准入 | 正式Near |
|---|---:|---:|---:|---:|
|T01|5|5|5|0|
|T02|5|5|5|0|
|T03|5|5|3|0|
|T04|5|5|4|0|
|T05|5|5|5|0|
|T06|5|5|3|1|
|T07|5|5|5|0|
|T08|5|5|5|0|
|T09|5|5|5|1|
|T10|5|4|4|2|
|T11|5|5|1|0|
|T12|5|5|5|0|
|T13|5|5|5|2|
|T14|5|5|5|0|
|T15|5|5|5|0|
|T16|5|5|5|1|
|T17|5|5|5|2|
|T18|5|5|3|0|
|T19|5|5|5|4|
|T20|5|5|5|0|

## 逐条状态

| 案例 | 原参数族 | 源参数 | 观察窗(s) | 区间 | RGB距离 | 说明 |
|---|---|---|---:|---|---|---|
|T01_C01|chain_surface_friction_coefficient|0.2|5.0|full_chain: [[0.36, 0.43]]|已接入|已接入固定参考的局部区间。|
|T01_C02|chain_surface_friction_coefficient|0.2|5.0|full_chain: [[0.36, 0.43]]|已接入|已接入固定参考的局部区间。|
|T01_C03|chain_surface_friction_coefficient|0.2|5.0|full_chain: [[0.36, 0.43]]|已接入|已接入固定参考的局部区间。|
|T01_C04|chain_surface_friction_coefficient|0.29|5.0|full_chain: [[0.36, 0.43]]|已接入|已接入固定参考的局部区间。|
|T01_C05|chain_surface_friction_coefficient|0.43|5.0|full_chain: [[0.36, 0.43]]|已接入|已接入固定参考的局部区间。|
|T02_C01|probe_initial_speed_mps|0.1770508|6.833333|C2_signal_displaced_0p05m: [[0.1516736, 0.1770508]]|已接入|已接入固定参考的局部区间。|
|T02_C02|probe_initial_speed_mps|0.1786225|6.833333|C2_signal_displaced_0p05m: [[0.1612948, 0.1786225]]|已接入|已接入固定参考的局部区间。|
|T02_C03|probe_initial_speed_mps|0.3217655|5.0|C2_signal_displaced_0p05m: [[0.227844, 0.2904583]]|已接入|已接入固定参考的局部区间。|
|T02_C04|probe_initial_speed_mps|0.040001|5.0|C2_signal_displaced_0p05m: [[0.227844, 0.2904583]]|已接入|已接入固定参考的局部区间。|
|T02_C05|probe_initial_speed_mps|0.2904583|5.0|C2_signal_displaced_0p05m: [[0.227844, 0.2904583]]|已接入|已接入固定参考的局部区间。|
|T03_C01|lower_phone_com_edge_distance_m|0.1|5.0|phone_second_fall_original: [[0.08433333333333333, 0.1]]|已接入|已接入固定参考的局部区间。|
|T03_C02|lower_phone_com_edge_distance_m|0.1|5.0|phone_second_fall_original: [[0.1, 0.4]]|未准入|原二次跌落为正类，终端落地点超出当前画面；原C族边界、种子与实际版本的对应仍未闭合。上游事件标签保留，不据此准入完整二次跌落距离。|
|T03_C03|lower_phone_com_edge_distance_m|0.1|5.0|phone_second_fall_original: [[0.1, 0.4]]|未准入|原二次跌落为正类，终端落地点超出当前画面；原C族边界、种子与实际版本的对应仍未闭合。上游事件标签保留，不据此准入完整二次跌落距离。|
|T03_C04|book_initial_speed_mps|0.47000000000000003|5.0|book_contacts_upper_can: [[0.47000000000000003, 0.73]]|已接入|已接入固定参考的局部区间。|
|T03_C05|book_initial_speed_mps|0.73|5.0|book_contacts_upper_can: [[0.47000000000000003, 0.73]]|已接入|已接入固定参考的局部区间。|
|T04_C01|bottom_book_friction_coefficient|0.08|5.0|original_full_chain: [[0.08, 0.105]]|已接入|已接入固定参考的局部区间。|
|T04_C02|commanded_support_extraction_speed_mps|0.15|5.0|original_full_chain: [[0.037500000000000006, 0.05], [0.05, 0.1], [0.1, 0.125], [0.125, 0.15]]|未准入|三条已存轨迹的书／斜面几何重叠均低于0.41毫米，不能把原生0.151米读数直接称为可见穿模。但原配置／种子对应仍未认证，源复跑最大位置差约0.119米；原族候选保留，尚未准入正式距离。|
|T04_C03|bottom_book_friction_coefficient|0.105|5.0|original_full_chain: [[0.08, 0.105]]|已接入|已接入固定参考的局部区间。|
|T04_C04|commanded_support_extraction_speed_mps|0.1|5.0|original_full_chain: [[0.08, 0.1], [0.22, 0.32]]|已接入|已接入固定参考的局部区间。|
|T04_C05|commanded_support_extraction_speed_mps|0.2|5.0|original_full_chain: [[0.08, 0.1], [0.22, 0.32]]|已接入|已接入固定参考的局部区间。|
|T05_C01|gap_ratio|1.134|6.833333|gate_passage: [[1.134, 1.16]]|已接入|已接入固定参考的局部区间。|
|T05_C02|phone_tray_friction_coefficient|0.049|6.833333|gate_passage: [[0.033593750000000006, 0.03375]]|已接入|已接入固定参考的局部区间。|
|T05_C03|gap_ratio|1.16|6.833333|gate_passage: [[1.134, 1.16]]|已接入|已接入固定参考的局部区间。|
|T05_C04|gap_ratio|1.11|6.833333|gate_passage: [[1.140078125, 1.14046875]]|已接入|已接入固定参考的局部区间。|
|T05_C05|gap_ratio|1.16|6.833333|gate_passage: [[1.140078125, 1.14046875]]|已接入|已接入固定参考的局部区间。|
|T06_C01|gap|0.0571429|4.1|complete_required_contact_chain: [[0.02, 0.0223214]]|已接入|已接入固定参考的局部区间。|
|T06_C02|gap|0.0571429|4.1|complete_required_contact_chain: [[0.12328125, 0.12375]]|未准入|No opposite outcomes in the recovered original finite grid; not marked inapplicable.|
|T06_C03|gap|0.0571429|4.1|complete_required_contact_chain: [[0.12281249999999999, 0.12328125]]|未准入|No opposite outcomes in the recovered original finite grid; not marked inapplicable.|
|T06_C04|impact_force|1.4285714|4.1|complete_required_contact_chain: [[1.7056361783203124, 1.7060547051757813]]|已接入|已接入固定参考的局部区间。|
|T06_C05|impact_force|1.6428571|4.1|complete_required_contact_chain: [[1.5357143, 1.6428571]]|已接入|已接入固定参考的局部区间。|
|T07_C01|phone_surface_friction_coefficient|0.25|5.0|motion_ge_1cm: [[0.26, 0.28]]|已接入|已接入固定参考的局部区间。|
|T07_C02|phone_surface_friction_coefficient|0.25|5.0|motion_ge_1cm: [[0.26, 0.28]]|已接入|已接入固定参考的局部区间。|
|T07_C03|phone_surface_friction_coefficient|0.25|5.0|motion_ge_1cm: [[0.26, 0.28]]|已接入|已接入固定参考的局部区间。|
|T07_C04|phone_surface_friction_coefficient|0.2|5.0|motion_ge_1cm: [[0.24, 0.28]]|已接入|已接入固定参考的局部区间。|
|T07_C05|phone_surface_friction_coefficient|0.28|5.0|motion_ge_1cm: [[0.24, 0.28]]|已接入|已接入固定参考的局部区间。|
|T08_C01|lower_impactor_initial_speed_mps|0.8686186043463|5.0|t08_target_mug_below_table_8cm: [[0.8033769657523071, 0.8038531820924093]]|已接入|已接入固定参考的局部区间。|
|T08_C02|lower_impactor_initial_speed_mps|1.3144938983181307|5.0|t08_target_mug_below_table_8cm: [[1.2063940711538106, 1.2067544039110252]]|已接入|已接入固定参考的局部区间。|
|T08_C03|lower_impactor_initial_speed_mps|2.1375|5.0|t08_target_mug_below_table_8cm: [[1.9500000000000002, 1.9502929687500001]]|已接入|已接入固定参考的局部区间。|
|T08_C04|lower_impactor_initial_speed_mps|1.47|5.0|t08_upper_payload_book_below_table_8cm: [[1.764, 1.8]]; t08_target_mug_below_table_8cm: [[1.836, 2.058]]|已接入|已接入固定参考的局部区间。|
|T08_C05|lower_impactor_initial_speed_mps|2.058|5.0|t08_upper_payload_book_below_table_8cm: [[1.764, 1.8]]; t08_target_mug_below_table_8cm: [[1.836, 2.058]]|已接入|已接入固定参考的局部区间。|
|T09_C01|pull_force|15.5714286|4.1|upper_nonpulled_book_on_table_at_end: [[4.45, 4.5]]|已接入|No opposite outcomes in the recovered original finite grid; not marked inapplicable.|
|T09_C02|pull_force|15.5714286|4.1|upper_nonpulled_book_on_table_at_end: [[10.0, 10.2142857]]|已接入|已接入固定参考的局部区间。|
|T09_C03|pull_force|15.5714286|4.1|upper_nonpulled_book_on_table_at_end: [[14.7142857, 15.1428571]]|已接入|已接入固定参考的局部区间。|
|T09_C04|layer_friction|0.2|4.1|upper_nonpulled_book_on_table_at_end: [[0.2, 0.2178571]]|已接入|已接入固定参考的局部区间。|
|T09_C05|layer_friction|0.5571429|4.1|upper_nonpulled_book_on_table_at_end: [[0.2, 0.2178571]]|已接入|已接入固定参考的局部区间。|
|T10_C01|support_x|0.204|4.273333|support_pen_displacement_reaches_source_threshold: [[0.204, 0.2105]]|已接入|已接入固定参考的局部区间。|
|T10_C02|support_x|0.2105|4.273333|support_pen_displacement_reaches_source_threshold: [[0.204, 0.2105]]|已接入|已接入固定参考的局部区间。|
|T10_C03|support_x|0.08|4.1|support_pen_displacement_reaches_source_threshold: [[0.204, 0.2105]]|已接入|已接入固定参考的局部区间。|
|T10_C04|support_x|0.217|4.1|support_pen_displacement_reaches_source_threshold: [[0.204, 0.2105]]|已接入|已接入固定参考的局部区间。|
|T10_C05|support_x|0.2171429|4.1|support_pen_displacement_reaches_source_threshold: []|未准入|冻结文本与执行状态均为位置0.2171429米、初速3米/秒、倾角38度；同名cam01配置已换成另一版。物理参数已恢复，原机位完整轨迹对应仍待核验。冻结输入、标签保留。|
|T11_C01|driver_initial_speed_command_mps|2.3|5.0|t11_driver_eraser_final_center_below_minus_10cm: [[2.3, 2.5]]|已接入|已接入固定参考的局部区间。|
|T11_C02|driver_initial_speed_command_mps|2.5|5.0|t11_driver_eraser_final_center_below_minus_10cm: [[2.3, 2.5]]|未准入|新参考的橡皮在末帧154已出画；先前下落不直接证明原末态Z阈值。原状态真值和视频质量验收保留。|
|T11_C03|joint_global_configuration|{'driver_initial_speed_mps': 3.05, 'relay_case_gap_m': 0.024, 'case_edge_margin_m': 0.055, 'relay_block_mass_kg': 0.13, 'case_friction_coefficient': 0.08}|5.0|t11_driver_eraser_final_center_below_minus_10cm: [[0.388892197576643, 0.389468606164474]]; t11_relay_pencil_case_final_center_below_minus_10cm: [[0.3185703498612672, 0.3191467584490981]]; t11_eyeglasses_case_final_center_below_minus_10cm: [[0.2205808899300058, 0.22115729851783675]]|未准入|210帧完整核验完成；三目标在原五秒末帧154均不可见。原协议要求末态世界z判据，不能以较早可见的下落替代。原状态已恢复，当前RGB末态可观察性未通过。|
|T11_C04|driver_initial_speed_command_mps|2.9|5.0|t11_driver_eraser_final_center_below_minus_10cm: [[2.3844726562500003, 2.3853515625000004]]; t11_relay_pencil_case_final_center_below_minus_10cm: [[2.025, 2.02587890625]]|未准入|210帧完整核验完成；三目标在原五秒末帧154均不可见。原协议要求末态世界z判据，不能以较早可见的下落替代。原状态已恢复，当前RGB末态可观察性未通过。|
|T11_C05|driver_initial_speed_command_mps|3.1|5.0|t11_driver_eraser_final_center_below_minus_10cm: [[2.3844726562500003, 2.3853515625000004]]; t11_relay_pencil_case_final_center_below_minus_10cm: [[2.025, 2.02587890625]]|未准入|210帧完整核验完成；三目标在原五秒末帧154均不可见。原协议要求末态世界z判据，不能以较早可见的下落替代。原状态已恢复，当前RGB末态可观察性未通过。|
|T12_C01|stapler_initial_speed_mps|1.0|5.0|stapler_contacts_tissue_box: [[0.697265625, 0.6982421875]]|已接入|已接入固定参考的局部区间。|
|T12_C02|stapler_initial_speed_mps|1.6|5.0|stapler_contacts_tissue_box: [[1.05625, 1.0570312499999999]]|已接入|已接入固定参考的局部区间。|
|T12_C03|stapler_initial_speed_mps|1.9|5.0|stapler_contacts_tissue_box: [[1.7172363281249998, 1.7181640624999999]]|已接入|已接入固定参考的局部区间。|
|T12_C04|stapler_initial_speed_mps|1.6|5.0|stapler_contacts_tissue_box: [[1.717919921875, 1.71865234375]]|已接入|已接入固定参考的局部区间。|
|T12_C05|stapler_initial_speed_mps|2.05|5.0|stapler_contacts_tissue_box: [[1.7181762695312497, 1.7186767578124997]]|已接入|已接入固定参考的局部区间。|
|T13_C01|falling_book_edge_distance_m|0.125|5.0|falling_book_to_drink_contact: [[0.1125, 0.112890625]]; registered_two_contact_conjunction_and_order: [[0.1125, 0.112890625]]|已接入|已接入固定参考的局部区间。|
|T13_C02|falling_book_edge_distance_m|0.125|5.0|falling_book_to_drink_contact: [[0.1125, 0.112890625]]; registered_two_contact_conjunction_and_order: [[0.1125, 0.112890625]]|已接入|已接入固定参考的局部区间。|
|T13_C03|falling_book_edge_distance_m|0.125|5.0|falling_book_to_drink_contact: [[0.10820312500000001, 0.10859375]]; registered_two_contact_conjunction_and_order: [[0.10820312500000001, 0.10859375]]|已接入|已接入固定参考的局部区间。|
|T13_C04|falling_book_edge_distance_m|0.126|5.0|falling_book_to_drink_contact: [[0.10893750000000002, 0.10934375000000002]]; registered_two_contact_conjunction_and_order: [[0.10893750000000002, 0.10934375000000002]]|已接入|已接入固定参考的局部区间。|
|T13_C05|falling_book_edge_distance_m|0.127|5.0|falling_book_to_drink_contact: [[0.1084375, 0.10885937500000001]]; registered_two_contact_conjunction_and_order: [[0.1084375, 0.10885937500000001]]|已接入|已接入固定参考的局部区间。|
|T14_C01|channel_throat_width_m|0.0325|5.0|passed_channel: [[0.035250000000000004, 0.035500000000000004]]; terminal_contact_after_full_exit: [[0.035250000000000004, 0.035500000000000004]]|已接入|已接入固定参考的局部区间。|
|T14_C02|channel_throat_width_m|0.0325|5.0|passed_channel: [[0.0365, 0.03655078125]]; terminal_contact_after_full_exit: [[0.0365, 0.03655078125]]|已接入|已接入固定参考的局部区间。|
|T14_C03|channel_throat_width_m|0.0325|5.0|passed_channel: [[0.0305078125, 0.030566406249999997], [0.039941406250000006, 0.04], [0.04046875, 0.04052734375]]; terminal_contact_after_full_exit: [[0.0305078125, 0.030566406249999997], [0.039941406250000006, 0.04]]|已接入|已接入固定参考的局部区间。|
|T14_C04|channel_throat_width_m|0.018|5.0|passed_channel: [[0.018, 0.019]]|已接入|已接入固定参考的局部区间。|
|T14_C05|channel_throat_width_m|0.019|5.0|passed_channel: [[0.018, 0.019]]|已接入|已接入固定参考的局部区间。|
|T15_C01|driver_book_initial_speed_mps|1.4|5.0|laptop_reaches_original_fall_criterion: [[0.49500000000000005, 1.4]]|已接入|已接入固定参考的局部区间。|
|T15_C02|driver_book_initial_speed_mps|1.9500000000000002|5.0|laptop_reaches_original_fall_criterion: [[0.675, 1.9500000000000002]]|已接入|已接入固定参考的局部区间。|
|T15_C03|driver_book_initial_speed_mps|3.12|5.0|laptop_reaches_original_fall_criterion: [[1.08, 3.12]]|已接入|已接入固定参考的局部区间。|
|T15_C04|laptop_edge_margin_m|0.085|5.0|laptop_contacts_phone: [[0.050000000000000044, 0.08499999999999996]]|已接入|已接入固定参考的局部区间。|
|T15_C05|laptop_edge_margin_m|0.02|5.0|laptop_contacts_phone: [[0.050000000000000044, 0.08499999999999996]]|已接入|已接入固定参考的局部区间。|
|T16_C01|support_angle_deg|72.75862068965517|5.0|folder_downstream_contact: [[80.5172413793, 81.3793103448]]|已接入|已接入固定参考的局部区间。|
|T16_C02|support_angle_deg|72.75862068965517|5.0|folder_downstream_contact: [[76.9375, 77.0]]|已接入|已接入固定参考的局部区间。|
|T16_C03|support_angle_deg|72.75862068965517|5.0|folder_downstream_contact: [[83.9655172414, 84.8275862069]]|已接入|已接入固定参考的局部区间。|
|T16_C04|support_angle_deg|83.9655172413793|5.0|folder_downstream_contact: [[84.77370689655172, 85.60546875]]|已接入|已接入固定参考的局部区间。|
|T16_C05|support_angle_deg|84.82758620689656|5.0|folder_downstream_contact: [[83.9655172414, 84.8275862069]]|已接入|已接入固定参考的局部区间。|
|T17_C01|can_initial_speed_mps|1.610344827586207|5.0|can_tissue_box_contact: [[0.5482758621, 0.6810344828], [1.2120689655, 1.3448275862]]|已接入|已接入固定参考的局部区间。|
|T17_C02|can_initial_speed_mps|1.610344827586207|5.0|can_tissue_box_contact: [[0.6810344828, 0.8137931034], [2.1413793103, 2.274137931]]|已接入|已接入固定参考的局部区间。|
|T17_C03|can_initial_speed_mps|1.610344827586207|5.0|can_tissue_box_contact: [[1.0793103448, 1.2120689655], [3.7344827586, 3.8672413793]]|已接入|已接入固定参考的局部区间。|
|T17_C04|can_initial_speed_mps|0.9465517241379311|6.4|can_tissue_box_contact: [[1.024858566810345, 1.0253771551724138]]|已接入|已接入固定参考的局部区间。|
|T17_C05|can_initial_speed_mps|1.0793103448275863|6.4|can_tissue_box_contact: [[1.024858566810345, 1.0253771551724138]]|已接入|已接入固定参考的局部区间。|
|T18_C01|contact_friction|0.526896551724138|5.0|upper_nonpulled_book_on_table_at_end: [[0.10405172413793104, 0.1044396551724138]]|未准入|原GPU源点已复现，当前原参数轴端点仍无翻转；保留已有其他设置的诊断，不判不适用，也不宣称原GPU边界完成。|
|T18_C02|contact_friction|0.526896551724138|5.0|upper_nonpulled_book_on_table_at_end: [[0.11607758620689654, 0.1164655172413793], [0.39112068965517244, 0.3915086206896552]]|未准入|原GPU源点已复现，当前原参数轴端点仍无翻转；保留已有其他设置的诊断，不判不适用，也不宣称原GPU边界完成。|
|T18_C03|contact_friction|0.526896551724138|5.0|upper_nonpulled_book_on_table_at_end: [[0.04, 0.08]]|已接入|已接入固定参考的局部区间。|
|T18_C04|overlap_length|0.05827586206896551|5.0|upper_nonpulled_book_on_table_at_end: [[0.1947952586206897, 0.19523706896551726]]|已接入|已接入固定参考的局部区间。|
|T18_C05|overlap_length|0.06534482758620688|5.0|upper_nonpulled_book_on_table_at_end: [[0.06534482758620688, 0.15]]|已接入|已接入固定参考的局部区间。|
|T19_C01|impact_eccentricity_m|-0.0940625|6.966667|striker_target_contact: [[-0.0940625, -0.09296874999999999]]|已接入|已接入固定参考的局部区间。|
|T19_C02|impact_eccentricity_m|-0.09296874999999999|6.966667|striker_target_contact: [[-0.0940625, -0.09296874999999999]]|已接入|已接入固定参考的局部区间。|
|T19_C03|impact_eccentricity_m|-0.0940625|6.966667|striker_target_contact: [[-0.0940625, -0.09296874999999999]]|已接入|已接入固定参考的局部区间。|
|T19_C04|impact_eccentricity_m|-0.09296874999999999|6.966667|striker_target_contact: [[-0.0940625, -0.09296874999999999]]|已接入|已接入固定参考的局部区间。|
|T19_C05|impact_eccentricity_m|0.14|6.966667|striker_target_contact: [[0.0875, 0.105]]|已接入|已接入固定参考的局部区间。|
|T20_C01|box_cup_gap|0.03290909090909091|5.0|complete_propagation_original: [[0.45, 0.7]]|已接入|已接入固定参考的局部区间。|
|T20_C02|book_drive_speed|3.0454545454545454|5.0|complete_propagation_original: [[0.8181818181818181, 1.1363636363636362]]|已接入|已接入固定参考的局部区间。|
|T20_C03|book_drive_speed|3.0454545454545454|5.0|complete_propagation_original: [[1.4545454545454546, 1.7727272727272727]]|已接入|已接入固定参考的局部区间。|
|T20_C04|book_drive_speed|3.3636363636363638|5.0|complete_propagation_original: [[1.4545454545454546, 1.7727272727272727]]|已接入|已接入固定参考的局部区间。|
|T20_C05|book_drive_speed|3.6818181818181817|5.0|complete_propagation_original: [[0.5, 2.25]]|已接入|已接入固定参考的局部区间。|
