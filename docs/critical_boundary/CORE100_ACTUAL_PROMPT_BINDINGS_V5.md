# Core100实际提交文本绑定与评测入口

名单：`core100-critical-pairs-v5-20261103`；协议：`core100_critical_protocol_v7_20261103`。

100条参考、物理参数、主事件、观察窗口、临界区间、归一化及配对均保留。仍为20场景各5条、Near14条、跨界配对13组；15条替换输入仍需独立生成和标注。

本版修复生成输入的文本绑定。对照作者已选择的实际提交文本及生成元数据，发现第四版57个案例沿用了恢复出的文本，而不是模型实际收到的冻结短prompt。本版逐字恢复实际提交文本的三种变体，不撰写新文本、不改物理参数。其中56条属于参考未更换的案例，另1条是本就需要新生成的T03_C02 cam02。另14条替换参考继续使用各自独立登记的prompt。

实际文本来源、三变体SHA256、作者输入政策SHA及原生成记录在`benchmarks/core100_critical_pairs_v5_20261103/evidence/ACTUAL_SUBMITTED_PROMPTS.json`。第四版保留，不把旧版分数改名为本版成绩。

对Cosmos3-Nano首轮变体1，按本版规定的种子、条件图、实际文本和原生观察窗核对，80条来自固定生成库、5条来自此前单独完成的新版T19产物，共85条具备视频复用候选。它们仍需全解码、哈希核验和按新版事件重新评分；不导入旧标签或旧分数。其余15条必须新生成。

## 执行

```powershell
python -m physedit.core100_critical status `
  --registry benchmarks/core100_critical_protocol_v7_20261103/registry_9d36771444d1.json `
  --expected-registry-sha256 9d36771444d1e93e87106af18a8e3ef757d9958eea8006160acc39108483b0f0

python -m physedit.core100_critical prepare `
  --out review/core100_v5_new_run --model cosmos3_nano --fps 24 --variant 1 --seeds 0 `
  --registry benchmarks/core100_critical_protocol_v7_20261103/registry_9d36771444d1.json `
  --expected-registry-sha256 9d36771444d1e93e87106af18a8e3ef757d9958eea8006160acc39108483b0f0

python -m physedit.core100_tasks `
  --pointer catalog/prepared_core100_critical_protocol_v5.json `
  --out review/core100_v5_regeneration_tasks_new
```

[15条任务清单](../../benchmarks/core100_regeneration_v5_20261103/README.md)同时提供独立生成输入、待绑定新视频的盲标任务和原文件哈希。三个种子时每模型45个新生成位置；首轮单个种子时为15个，不冒充多种子实验。

筛查失败保留在总分母，不确定事件送复核。机器预标注准确率、拒绝候选和最终人工确认分开报告。原生时间不足的模型不通过补帧、重定时或缩短参考窗口准入。

指标适用范围仍见[完整协议说明](CORE100_CAMERA_REVISION_V4.md#指标适用范围)：主事件、NearAcc、两类PairAcc及覆盖率有评分接口；完整EventExact、模型响应曲线BoundaryError和反演适用子集另行登记。输入绑定完成不等于新模型成绩或独立人工gold已经完成。
