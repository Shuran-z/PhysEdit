# 视频生成与参数测量

分别记录生成与测量结果：先固定条件图、提示、seed、视频长度和帧率，再从生成帧0跟踪目标，使用SAM3.1目标观测与图像边界测量及原 anchor 拟合器。参数测量使用声明相机、几何与运动模型；镜头变化、目标漂移和接触事件由视觉指标及Qwen另行评估。

使用顺序与安装从 [快速上手](QUICKSTART.md)开始；此文档集中说明评测输入、时钟、评分和失败口径。

## 固定输入

- 条件帧为原视频第23帧；生成物理时间为 `23 / source_fps + generated_frame / output_fps`。
- 窗口、物体几何/姿态、相机/K、声明角运动与阻尼在评分前固定。未知线速度范围为0–8m/s、仰角±89°；不提供参考线速度或其方向，目标重力只用于结果比较。
- 保存原视频、权重、源码、掩膜及解码像素的 hash。Wan 的反色配置必须关闭；修正媒体需重新绑定全部对应掩膜，不能混用旧像素和旧mask。
- 参考视频若经不均匀采样，必须用实际源帧时间，不能把容器帧率当作物理时间。

## 命令接口

```bash
python scripts/phyediting_gen.py build items.jsonl input --data-root /path/to/reference --host-root /path/to/input --source-root /path/to/reference --applicability /path/to/applicability.json --generation-frames 161 --generation-fps 25
python scripts/phyediting_gen.py rows input/template.jsonl rows.jsonl --model ltx_i2v --frames 161 --fps 25 --out-root /path/to/output
python scripts/phyediting_gen.py jobs items.jsonl rows.jsonl track_jobs.jsonl --compact /path/to/compact
python scripts/phyediting_gen.py score items.jsonl rows.jsonl tracks.jsonl predictions.jsonl
```

`jobs`导出声明的初始框。`score`读取已完成的观测，并不自动运行 SAM3.1；需由上游提供相同的初始提示、前端处理及 图像边界测量生成的 `tracks.jsonl`（`id`、`fps`、`tracks[object_name].frames/xyxy`及视频/版本/测量文件绑定）。单帧边界测量接口见 [observations.py](../../gravtrace/observations.py)。默认评分为 `--v0 agnostic --offset-mode anchor`。

评分从登记的 `num_frames`、帧率与原窗口生成完整帧清单。缺失框或空mask导致整例 `missing_observation`，输出原计划帧和缺帧清单；不会缩窗、裁尾或仅拟合剩余帧。缺失整条跟踪也保留原manifest案例。完整窗口沿用原拟合器，并关闭自动接触裁尾。探索性的 `--scan`、`--camera-motion`、`--v0 declared` 不属于此评分协议。

任一边长小于6px或面积小于36px的框为不可用观测，在拟合中赋零权重。登记窗口出现这类框时，固定评分返回`invalid_observation`并列出`unusable_generated_frames`。有效窗口由来源相机、几何和可见性预先确定；生成后的出画、遮挡和身份变化按实际观测记录。

## 结果口径

每个模型保留全部登记案例，分别报告缺观测、帧数不足和触及参数边界等失败；均值/最大值只统计成功拟合，并同时给出全部注册样本的失败率、覆盖率、实际观测帧及事件/重力/相机/物理组统计。参考视频按已知物理真值评分，生成视频报告**请求重力相对偏差**。测量适用性和参考控制分别记录。

当前入口支持 GravTrace、V/P 和本地/API Qwen；配置、统计口径和验证范围见 [EVALUATION.md](EVALUATION.md)。多机调度见 [PIPELINE.md](../PIPELINE.md)。

## SAM3.1目标跟踪

实际使用的单视角 SAM3.1 + RGB 处理 + 图像边界测量代码和便携入口现已公开，运行方法见 [SAM31.md](SAM31.md)。`tracks_v4.jsonl` 可直接传给上述固定窗口 `score`，反演方法不变。

## 一键入口与运行规范

安装、输入准备、完整登记示例、运行命令和结果文件见 [QUICKSTART.md](QUICKSTART.md)；12模型模式、原生时钟和专有依赖见 [MODELS.md](MODELS.md)。一键入口默认仅打印计划，显式 `--execute` 才串联真实生成、单视角SAM3.1、固定反演和汇总。每次运行一个模型，使用新的输出目录，权重和依赖由运行环境提供。

### 自定义runner

已有外部调用可显式提供 `generation_command` **argv列表**覆盖登记入口，占位符仅为 `{manifest}`、`{run_dir}`、`{model_dir}`；不经过shell。此时 `{manifest}` 是合格生成子清单，全部注册样本仍在 `rows.jsonl` / `generation_rows.jsonl`，输出继续经过同一媒体、前端、评分方法，不能将外部runner的完成标记直接当评测成功。

### 完整输入与媒体绑定

输入构建默认保留全登记清单，不再默认抽取每重力8例。原内置提示只覆盖8类事件；其他事件须在item中提供预登记的 `generation_prompt`，否则保留为 `unsupported_registered_prompt_or_gravity`，不假造提示或删出分母。窗口不适用、缺源和缺初始提示均留下具体原因。参考媒体的容器时钟必须与登记fps一致；不均匀采样或不同物理时钟需要另有明确的时间定义，此入口不擅自改时钟。

完成检查逐帧解码整个视频，核对尺寸、总帧数、fps及每帧时间戳；无法可靠读取时间戳时拒绝。Diffusers runner以 `.partial.mp4` 写入，校验后才原子发布最终文件，另保存源码输入/登记/运行设置/媒体完成绑定；只有绑定和媒体再次验证都通过才能 `skip-existing`。坏文件、缺少完成记录的旧文件、已有 claim 的中断尝试不会触发自动重生成。

`tracks_v4.jsonl` 绑定实际视频SHA、fps、前端manifest及测量文件SHA。评分前检查前端、媒体、时钟和测量来源的一致性，缺帧记录为整例失败。拟合器、相机、边界测量和观察窗均通过源码与输入SHA绑定。

### 独立汇总

汇总命令使用显式输入路径：

```bash
python scripts/phyediting_gen_summary.py --items ITEMS.jsonl --rows ROWS.jsonl \
  --predictions RESULTS.jsonl --out SUMMARY.json
```

成功仅为 `status=ok` 且数值有效；`at_bound`、缺源、不适用、生成/跟踪/拟合失败及缺预测分别计入状态与原因。覆盖率为成功例/全部注册例，失败率为其补数；均值/最大/中位请求重力偏差只统计成功例。按原 `split`、事件、重力、相机分组，并以 `sample_id` 保留同一item的不同seed。没有split时标记unspecified，不推断ID/OOD归属；集合标记由审核后的输入清单提供。

软件回归检查输入、媒体、调用接口和异常处理；模型运行状态见[MODELS.md](MODELS.md)，测量性能见[validation.md](validation.md)。
