# PhysProbe 仿真反演评测：Core100 流程

对每条视频（参考视频或生成视频），在其他条件都已知的前提下，分别反演三个参数：重力 g、主接触面摩擦 μ、初速度 v（只对有指定速度的 62 条任务）。方法对 99 条 Genesis 任务完全统一（T06_C04 是 Isaac，按用户决定跳过）。问题与决策的完整记录在 `.local-research/evaluation/CORE100_INVERSION_ISSUES.md`（不进 git，下文的 D7、C12 等编号指那里的条目）。

代码在本目录（git）；文中的 `results3/`、`results_gen/`、`sam_gen/`、`libs3/` 等数据路径都在 `PHYSPROBE_WORK` 下（默认为 `.local-research/evaluation/core100_inversion_workspace/trial/batch2`，见 `paths.py`）。脚本在本目录下运行，例如 `python physprobe/inversion/evaluator.py ref`；服务器端脚本在 `server/`，部署脚本在 `deploy/`，上传和监控工具在 `tools/`。

## 1. 方法（统一规则）

1. **仿真库**（`library_plan.py`，D11）。每个（任务, 参数）一个库，与视频无关，同一任务的所有生成视频共用。
   - g：绝对对数网格 0.5–25 m/s²，相邻比 1.12，共 35 个。
   - μ：真值 × 1.15^k；v：真值 × 1.12^k。另补真值 × r^(±0.5) 两个半步（D16），真值不进库。
   - 用作者原始渲染脚本、原始 32 位设置做纯物理重放，只算到 max(horizon) + 31 帧（F16），保存所有物体的位姿。
   - 分叉区间的二分加密（`library_bisect.py`，1316 条）：相邻取值的轨迹差异超过运动幅度一半的地方补中点。
2. **可预测窗口**（D7、D10）。每个物体只在"仿真自己能复现"的帧段内参与比较。
   - 判据：真值重复之间、真值重复与记录之间的差异 < 1.5 px，并且二阶差分也 < 1.5 px。
   - 新的评测机器先过 14 条一致性检查，它的重复并入窗口的计算。
3. **观测**（C12）。SAM 3.1 精简版跟踪器 `server_code/sam_tracker.py`。
   - 同一模型、同一权重、同样的两角点提示；一条视频里所有非固定物体一次会话、联合跟踪。
   - 提示框用条件帧上可见部分的框。
   - 只跟踪到最后一个窗口结束 + 平移余量对应的那一帧。
4. **对齐**（D12）。按物理时间对齐：视频第 k 帧对应 t = 4·dt + (k − k_c)·dt_obs。
   - 生成视频：k_c = 0，dt_obs = 1 / 原生帧率（按播放速度计时，E2）；由参考视频改造的合成视频沿用参考视频的时钟。
   - 允许 ±20 仿真帧的连续时间平移（起动时刻未知）。
   - 像素：相机像素 → 视频像素的仿射映射。生成视频的映射由条件图到第 0 帧的 ECC 配准得到，配准失败时用该模型的中位映射（`gen_register.py`）。
5. **相机运动补偿**（生成视频，`cam_comp.py`，C14）。每帧用背景（挖掉物体框）做 ECC 仿射配准到第 0 帧，物体框变换回第 0 帧坐标。很多模型会自己加镜头运动；不补偿的话所有物体都会"无法解释"。
6. **损失与估计**（`evaluator.py`）。
   - 损失：可见部分框的 Huber 残差，按每个物体条件帧框的对角线和 σ = 1.5 px 归一化。所有取值都在同一组帧（真值窗口）上比较，取值自己窗口以外的帧按噪声水平计。
   - 插值：相邻库取值之间在参数空间插值（D14，分叉区间不插）。
   - 物体筛选（D15）：
     - 在整个库里都拟合不上的物体，判为"无法解释"；
     - 在联合最优点上和其他物体不一致的物体，判为"不一致"。
     
     这两类都不参与估计，并记入 `object_diagnostics`。
   - 观测覆盖（D31）：物体在其窗口对应的视频帧里，有 SAM 框的不到一半（被遮挡、消失、画面崩坏），判为观测不足，不参与估计。
   - 多数与载体规则（D22、D23）：被拒的物体数不少于被采用的，或者参数的载体物体被拒，结果判为"无法解释"。
   - 不确定带：损失在最小值 + δ 以内的所有库取值（D25，全局集合，不只取最小值附近的连续段），δ = 1 为理论值；236 组已知答案结果上覆盖率 93%，不需要经验放大。
   - 结果类型：点估计（带宽 ≤ ×1.25）、区间、上界或下界、不可辨识（含只排除了网格最后一个值的"单侧界"，D32）、无法解释、无观测。
7. **真值验证门**（生成视频，`validation_gate.py`，D28）。参考视频或同格式合成视频在某组（任务, 参数）上没给出估计的，生成视频在这组上记为 `not_validated`。

## 2. 已知答案验证

参考视频用的是同一套流程，库里不含真值（`results3/ref_*.json`，统计用 `ref_stats.py`）。

| 参数 | 组数 | 点估计 | 点估计误差中位数 | 90 分位 | 真值在带内 |
|---|---|---|---|---|---|
| g | 97 | 35 | 1.4% | 6.2% | 85/96 |
| μ（不含 T19/T20，见 B20） | 87 | 19 | 0.7% | 4.3% | 76/85 |
| v | 62 | 34 | 1.1% | 4.4% | 57/62 |

**生成视频路径的端到端测试**（`make_synth.py`）。把参考视频改成 15 fps × 81 帧，并做 VideoGPA 式的几何变换（横向 ×1.026、偏移 −11 px），当作生成视频走完整流程（30 fps × 121 帧、10 fps × 16 帧两种格式见验收报告 3.2 节）：

| 参数 | 点估计 | 误差中位数 | 90 分位 | 真值在带内 |
|---|---|---|---|---|
| g | 35 | 1.2% | 4.1% | 79/93 |
| μ | 19 | 0.9% | 4.3% | 69/81 |
| v | 32 | 0.8% | 4.4% | 51/59 |

配准准确找回了人为加入的映射：横向缩放中位数 1.0264，偏移 −11.28 px。

**相机运动补偿的已知答案测试**（同一批合成视频，加逐帧平移 1.2k/0.4k px 和 0.2%/帧缩放，`make_pan_test.py`）：不补偿时 g 只有 1 个点估计、79/97 判为无法解释；补偿后 34 个点估计（误差中位数 1.3%）、带内 77/92，和不加镜头运动时几乎一样。

不是点估计的那些结果，多数是物理上确实无法精确确定的情况，例如：
- 窗口不到 0.3 秒（T14、T04_C03/C04 等）；
- 参数几乎不影响可见运动（滚动的罐子对摩擦不敏感）；
- 真值附近存在分叉（T15 的笔记本电脑、T05 手机是否碰到罐子）。

这时给出的是如实的区间或单侧界，而不是假的精确值。

## 3. 速度

| 环节 | 优化前 | 现在 |
|---|---|---|
| 仿真 | 不开 MPS 时同卡多进程只能轮流执行，并且线程超订 | 开 MPS：H100 单卡 24 条并发，吞吐是单条的 16 倍；线程限制为 1；截断后总量少约 24%（F15、F16） |
| SAM 3.1 | V4 前端约每物体 5 分钟（H100） | 精简版约每条视频 25–40 秒（206 帧，H100）。1 万条生成视频在 5 张 3090 + 4 张 A800/H100 上约 7 小时跑完（C12） |
| 逐视频评测 | — | 可见框按库仿真缓存。每条视频 3 个参数约 1 CPU 秒，1 万条在 9 核上约 20 分钟 |

建库只需要做一次。新的一批生成视频只需要跑 SAM 和评测。

## 4. 对新一批生成视频运行

```
cd physprobe/inversion   # 数据在 PHYSPROBE_WORK；服务器上设 PHYSPROBE_ROOT=<镜像根目录>
python make_gen_jobs.py NAME REMOTE_DIR --seeds 0,1,2 --annotations 1,2,3   # 配准 + SAM 任务（sam_gen/NAME/）
# 上传视频并跑 SAM：upload_and_run_gen.sh（hupanwen：server_code/run_sam_tracker_hupanwen.sh；xdliang3 主机：server_code/run_sam_tracker.sh）
python cam_comp.py sam_gen/NAME/items.json sam_gen/NAME/tracks_*.jsonl --out sam_gen/NAME/tracks_camcomp.jsonl   # 相机运动补偿
python eval_generated.py NAME sam_gen/NAME/tracks_camcomp.jsonl --workers 9 --clock realtime   # -> results_gen/NAME.jsonl（库与已知答案测试相同，不含真值重放，D30）
python validation_gate.py NAME NAME   # 真值验证门（D28）-> results_gen/NAME_gated.jsonl
python summarize_generated.py NAME_gated   # -> results_gen/NAME_gated_by_model.md
```

真值验证门:同一任务、同一参数的参考视频,以及同一视频格式的合成视频(真值已知),只要有一个没给出估计(无法解释、无观测或出错),这组(任务, 参数)在该格式下的生成视频结果就记为 `not_validated`,不计入模型的统计。这些地方是测量工具本身解释不了正确的物理,所以"无法解释"不能算作模型的错。

每条结果包含：key（seed / annotation / 模型 / 任务）、param、kind、est、band、truth、objects、object_diagnostics、map_source。如果某条视频的某个物体判为 not_explained 或 inconsistent，说明没有任何参数值能解释它的运动，可以作为"物理不合理"的独立信号单独统计。

## 5. 主机与环境（F8–F19）

- **仿真**：nscc-xdliang3-h100-1（2× H100，28 核）、a800-7（2× A800，12 核）、a800（1× A800，6 核），都部署在 `/workspace/wz`。环境为 `batch2/genesis_env.sh`：LD_PRELOAD 路径重定向、GL 旁路、PYTHONNOUSERSITE、线程限制、MPS。另外用 nscc-wangzijun-4090 的 GPU 0 和 GPU 2（作者的机器，每卡不超过 6 条，不开 MPS）。
- **SAM**：nscc-hupanwen 的 GPU 3–7、h100-2（驱动 550，只能跑 SAM），以及上面几台 xdliang3 主机。
- **部署包**：`deploy_cache_a800/deploy_host.sh`（`DEPLOY_HOST=...`），或者 Storage01 上的 `zhangshuran_eval_20261024/wz_stack.tar`（h100-1、h100-2、a800-7 共享）。
- **h100 占卡池**（codex_v3/infra2）：借卡用 `gpu_acquire.sh physedit_eval N`，还卡用 `GPU_PACKAGE=physedit_eval gpu_release.sh K`。h100-2 的 GPU 0 已于 2026-10-24 归还。

## 6. 生成视频结果

正式结果和全部证据见验收报告 [docs/physprobe/ACCEPTANCE_CORE100.md](../../docs/physprobe/ACCEPTANCE_CORE100.md)。

- 结果:`results_gen/all_cc.jsonl`(10,295 条视频 × 适用参数,共 27,164 组,已做相机运动补偿,实时时钟,库与已知答案测试相同);过门后为 `all_cc_gated.jsonl`,按模型的汇总在 `all_cc_gated_by_model.md`。
- 后处理一次跑完:`tools/postprocess_generated.sh <镜像根目录> all_cc 24`。依次做真值验证门、汇总、σ 加倍的敏感性对比(有 `all_cc_sigma3.jsonl` 时)、运动幅度与起动检查、报告图表。
- 人工判读:`qa_overlay.py`(分层抽样叠加图;绿 = SAM,红 = 提示值下的仿真,蓝 = 最佳拟合),判读记录在 `.local-research/evaluation/qa_view/`。
- 生成视频指标(问题记录 E3):`response_metrics.py [NAME]` -> `results_gen/response_metrics.md`:可评测性(各类结果的比例,不能评测 = 无法解释 + 无观测,待与人工打分做相关性检验)、反演误差(给出数值的结果,|最优值 / 提示值 − 1|,g/μ/v)、参数响应(g、v;同一模型同一任务内提示值不同的视频对,按不确定带排先后,单侧界也算,Kendall τ,按任务组重采样给区间)。同时写逐视频状态表 `results_gen/per_video_status.csv`(key、匿名片段 id、视频路径、各参数的类别和数值),用来对齐人工打分。
- 指标总表(用户 2026-10-26,文档 `docs/physprobe/METRICS.md`):`common_metrics.py SET TRACKS --out NAME [--video-dir DIR] [--clock ...]` 算通用指标(轨迹 ADE/FDE、Physics-IQ 运动一致、首帧 PSNR/SSIM、运动像素占比),`benchmark_table.py COMMON RESPONSE_JSON CAMCOMP_STATS --out NAME` 把通用指标、相机漂移和本基准的参数指标合成按模型的总表(`results_gen/benchmark_<NAME>.md`)。生成视频按 key 放在 `gen_videos_v3/videos/`(镜像上)。
- 仿真库加密(D36):`library_refine_plan.py`(规划,只看仿真)→ `server/refine_queue.py`(运行)→ `collect_library.py PLAN libs3`(收集)。第一轮已并入 `libs3/`;第二轮(4.5 px 以下)A/B 变差,不采用。试验块放在单独目录,用 `PHYSPROBE_EXTRA_LIBS` 做 A/B(`ref_ab.py` 比较两次参考结果,`refined_clips.py` 列出已全部加密的参考片段)。

## 7. 局限与待办

- **T19/T20 的 μ**(B20):支撑面是背景桌子,固定为 Genesis 默认摩擦 1.0,低于 1.0 的值在当前仿真设置下无法表示。
- **T11**:提示词没写起动时间(仿真里 2.0 s 才推),生成视频的"无法解释"可能部分来自时间未知(D29)。
- **DynamiCrafter**:16 帧、10 fps,大多数视频第 0 帧已不是条件图(用模型中位映射),跟踪噪声偏大,结论要谨慎。
- **待用户决定**:E1(T02、T16 主接触面的另一种映射);人工打分的数据(相关性检验);T07_C05、T09_C05(参考视频静止)是否补进评测。
