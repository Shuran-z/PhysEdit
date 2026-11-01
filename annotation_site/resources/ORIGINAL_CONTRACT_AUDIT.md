# 原配置与临界协议逐条核对

{"fixed_cases": 100, "generated_videos_bound": 3600, "exact_source_id_matches": 100, "cases_with_source_backed_score_definition": 90, "cases_with_critical_target_pending": 10, "main_observation_fields": 175, "auxiliary_fields": 433, "excluded_fields": 50, "excluded_threshold_fields": 60, "assistant_added_threshold_fields": 15, "native_truncation_input_videos": 300, "NearAcc_eligible": 0, "PairAcc_eligible": 0, "reference_admission_granted": false}

100条均按生成清单中的source_video_id精确对应；不是按VLM结果定义事件。

补查50条：原状态50条已找齐，T03/T04/T08/T11/T16/T17/T19/T20共40条恢复原始结果提取定义；T16/T17/T19/T20的20条重算结果与原生产QA逐条一致。T08 V4生产worker明确调用analyze_t08_v3_metrics.py，8cm确为原规则；T04使用独立V4审计器。T08的v6参考视频与同目录状态LFS哈希已全部核对，旧候选配置不代表实际发布规格。逐条参考结果和剩余10条缺项见remaining50_recovery.csv。

T12新增1cm及T13新增1cm/5cm仍禁止进入正式评分。T11 R011正式放行记录与可参数化原提取脚本已核对，恢复末帧z < -0.10m；不借用R009的-0.20m；T13 F5的1cm起始检测不是跌落定义。T15区分原z=-0.15m跌落判据与失去支撑。

有原始定义和原状态结果不等于参考准入。缺协议、参考、边界、配对与共同观察窗分别见original_contract_audit.csv；NearAcc/PairAcc尚未准入。辅助项单列且不进入正式评分。
