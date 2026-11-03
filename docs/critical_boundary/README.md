# Critical-boundary evaluation

This directory contains the protocol and user-facing workflow for the critical-boundary benchmark module. The raw videos, model outputs, intermediate annotations, and machine-specific audit files live under the local `review/` directory and are intentionally excluded from Git.

## Start here

- [第四版：100条临界参考接入完成](CORE100_CAMERA_REVISION_V4.md)：作者批准T03_C02改用cam02；100条数值及视觉参考齐全、待完成0条，Near14条。新名单和协议独立封存，未改线上旧任务；新机位需独立生成和标注。

- [第三版：六条替换参考与独立评测入口](CORE100_SIX_REPLACEMENTS_V3.md)：保留该版100条数值、99条视觉参考的原记录；最后一条的cam02更新见第四版。使用第三版指针时仍读取该版结果，不套用第四版状态。

- [新版Core100全100条临界流水线](CORE100_V2_CRITICAL_PIPELINE.md)：数值对应、参考准入、近桶和两种配对、筛查、复核与评分；以 `python -m physedit.core100_critical status` 查看当前接入数量。

- [新版Core100：8条换入，仍为20场景各5条](CORE100_CRITICAL_PAIRS_V2.md)：新名单、参数真值及生成接口；保留旧版任务和成绩，换入8条需重新生成和标注。

- [独立临界补充集：8条、4组真实发布异侧对照](../../benchmarks/critical_supplement_v1_20261101/README.md)：保留 Core100，独立导出和评分；[原6条未定位原因核查](CORE100_PENDING6_CAUSES.md)。

- [Core100逐条距离接入与20场景完成数](CORE100_DISTANCE_BINDINGS.md)：区分边界区间、原校准值与原族待对齐；有限扫描无翻转不直接判不适用。运行 `python -m physedit.core100_bindings status --verify-evidence` 核对实际清单。
- [原21条“不适用”逐项复核及纠正](CORE100_ORIGINAL_REFERENCE_REAUDIT.md)：原结论已撤回，列出漏接的原值、窗口截断、参数轴与事件不一致。

- [Core100 T19：5条参考替换、参数与临界距离、运行命令](CORE100_T19_REPLACEMENT.md)。其余95条冻结v6输入保持一致；旧T19模型结果不转入新版评分。

- [全量72,000条临界数值参考覆盖核查](WHOLE_DATASET_BOUNDARY_AUDIT_20261030.md)：固定当前发布清单，逐视频核对原值/区间与身份；区别于补充计算队列完成率。

- [2026-10-30 回收、队列恢复与当前缺项](RECOVERY_20261030.md)：本轮实际接入结果与未完成项；20场景动态明细见本地 `review/scene_family_completion_20261018/ALL20_PROGRESS.md`。

- [固定100条逐项评测准备清单与缺项](CORE100_READINESS_20261027.md)：按文件内生成时间解释，数值扫描完成与正式准入分别列出。

- [Core100 本轮实际修复、物理结果与运行队列](CORE100_RESOLUTION_EXECUTION_20261027.md)

- [Author-approved Core100 T12/T13 contact targets, 2026-10-27](CORE100_CONTACT_PROTOCOL_20261027.md): 100 target definitions do not certify 100 boundary references or final scores.

- [Protocol and metric definitions](CRITICAL_BOUNDARY_PROTOCOL.md)
- [Setup and command workflow](../../BOUNDARY_EVALUATION.md)
- [Two-stage quality screening and event judging](TWO_STAGE_PIPELINE.md)
- [Failure handling and denominator rules](FAILURE_HANDLING.md)
- [Window-aware event judging](WINDOW_AWARE_JUDGE.md)
- [Dual-judge procedure](DUAL_JUDGE.md)
- [T15 protocol](T15_EVALUATION_PROTOCOL.md)
- [H3/T15 handoff](H3_T15_HANDOFF.md)
- [Triage rules](TRIAGE_V2.md)
- [Historical search-recovery status](SEARCH_RECOVERY_STATUS.md)
- [Group-meeting slide notes](GROUP_MEETING_SLIDE_NOTES.md)

## Reproducible reference records

- [T04 Genesis release distance example](results/T04_RELEASE_DISTANCE_BINDING.json): three published samples bound to a pinned repository snapshot and a locally measured transition interval. The record explicitly marks live Hugging Face HEAD verification, repeatability, and visual admission as pending.

Generated artifacts are not automatically publication-ready data. Check the source revision, fixed context, event truth, parameter normalization, repeatability, and visual observability before promoting a record to the formal NearAcc denominator.
