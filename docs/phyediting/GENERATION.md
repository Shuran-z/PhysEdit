# PhyEditing 生成视频评估

生成与测量分别记账：先固定条件图、提示、seed、视频长度和帧率，再从生成帧0跟踪目标，使用已冻结的 SAM3.1 / V4 观测及原 anchor 拟合器。生成模型改变镜头、几何或运动事件时，声明相机和自由飞行模型可能不成立；数值拟合成功不能认证物理真实性。

## 固定输入

- 条件帧为原视频第23帧；生成物理时间为 `23 / source_fps + generated_frame / output_fps`。
- 窗口、物体几何/姿态、相机/K、声明角运动与阻尼在评分前固定。未知线速度范围为0–8m/s、仰角±89°；不提供参考线速度或其方向，目标重力只用于结果比较。
- 保存原视频、权重、源码、掩膜及解码像素的 hash。Wan 的反色配置必须关闭；修正媒体需重新绑定全部对应掩膜，不能混用旧像素和旧mask。
- 参考视频若经不均匀采样，必须用实际源帧时间，不能把容器帧率当作物理时间。

## 命令接口

```bash
python scripts/phyediting_gen.py build items.jsonl input --host-root /path/to/input --source-root /path/to/reference
python scripts/phyediting_gen.py rows input/template.jsonl rows.jsonl --model MODEL --frames 81 --fps 16 --out-root /path/to/output
python scripts/phyediting_gen.py jobs items.jsonl rows.jsonl track_jobs.jsonl
python scripts/phyediting_gen.py score items.jsonl rows.jsonl tracks.jsonl predictions.jsonl
```

`jobs`导出声明的初始框。`score`读取已完成的观测，并不自动运行 SAM3.1；需由上游提供同一冻结提示、前端处理及 V4 边界生成的 `tracks.jsonl`（`id`、`fps`、`tracks[object_name].frames/xyxy`）。V4 当前帧测量接口见 [observations.py](../../gravtrace/observations.py)。默认评分为 `--v0 agnostic --offset-mode anchor`。

评分从登记的 `num_frames`、帧率与原窗口生成完整帧清单。缺失框或空mask导致整例 `missing_observation`，输出原计划帧和缺帧清单；不会缩窗、裁尾或仅拟合剩余帧。缺失整条跟踪也保留原manifest案例。完整窗口沿用原拟合器，并关闭自动接触裁尾。探索性的 `--scan`、`--camera-motion`、`--v0 declared` 不属于此冻结协议。

非空残留也必须核验：原拟合器对任一边长小于6px或面积小于36px的框赋零权重。固定评分入口沿用这一定义，登记帧内出现这类框时返回整例 `invalid_observation`，附 `unusable_generated_frames`，不把1像素mask冒充完整观测。该检查不修改拟合器，也不裁掉问题帧。来源有效范围应在评分前按正确相机、声明几何和可见性登记；重新登记范围的验证须与原窗结果分别报告，保留原案例分母与逐帧不适用原因。生成视频的参考范围不能自动证明生成目标或镜头仍满足这些假设。

## 结果口径

每个模型保留全部登记案例，分别报告缺观测、帧数不足和触及参数边界等失败；均值/最大值只统计成功拟合，并同时给出原分母失败率、覆盖率、实际观测帧及事件/重力/相机/物理组统计。参考对照的误差针对已知物理真值；生成视频的数值是**相对于请求重力的偏差**，不是已知生成真值误差。只有测量适用性与参考控制同时成立，才能进一步解释模型差异。

原 `physedit` 多机器调度及 public-211 流程见 [PIPELINE.md](../PIPELINE.md)，与这里的 PhyEditing 固定评分合同分别维护。
## 冻结 SAM3.1 前端

实际使用的单视角 SAM3.1 + RGB 处理 + V4 测量代码和便携入口现已公开，运行方法见 [SAM31.md](SAM31.md)。`tracks_v4.jsonl` 可直接传给上述固定窗口 `score`，反演方法不变。
