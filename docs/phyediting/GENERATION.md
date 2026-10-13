# PhyEditing 固定评分方法

分别记录生成与测量结果：先固定条件图、提示、seed、视频长度和帧率，再从生成帧0跟踪目标，使用已冻结的 SAM3.1 / V4 观测及原 anchor 拟合器。生成模型改变镜头、几何或运动事件时，声明相机和自由飞行模型可能不成立；数值拟合成功不能认证物理真实性。

使用顺序与安装从 [快速上手](QUICKSTART.md)开始；此文档集中说明已冻结的输入、时钟、评分和失败口径。

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

`jobs`导出声明的初始框。`score`读取已完成的观测，并不自动运行 SAM3.1；需由上游提供同一冻结提示、前端处理及 V4 边界生成的 `tracks.jsonl`（`id`、`fps`、`tracks[object_name].frames/xyxy`及视频/版本/测量文件绑定）。V4 当前帧测量接口见 [observations.py](../../gravtrace/observations.py)。默认评分为 `--v0 agnostic --offset-mode anchor`。

评分从登记的 `num_frames`、帧率与原窗口生成完整帧清单。缺失框或空mask导致整例 `missing_observation`，输出原计划帧和缺帧清单；不会缩窗、裁尾或仅拟合剩余帧。缺失整条跟踪也保留原manifest案例。完整窗口沿用原拟合器，并关闭自动接触裁尾。探索性的 `--scan`、`--camera-motion`、`--v0 declared` 不属于此冻结协议。

非空残留也必须核验：原拟合器对任一边长小于6px或面积小于36px的框赋零权重。固定评分入口沿用这一定义，登记帧内出现这类框时返回整例 `invalid_observation`，附 `unusable_generated_frames`，不把1像素mask冒充完整观测。该检查不修改拟合器，也不裁掉问题帧。来源有效范围应在评分前按正确相机、声明几何和可见性登记；重新登记范围的验证须与原窗结果分别报告，保留原案例分母与逐帧不适用原因。生成视频的参考范围不能自动证明生成目标或镜头仍满足这些假设。

## 结果口径

每个模型保留全部登记案例，分别报告缺观测、帧数不足和触及参数边界等失败；均值/最大值只统计成功拟合，并同时给出全部注册样本的失败率、覆盖率、实际观测帧及事件/重力/相机/物理组统计。参考对照的误差针对已知物理真值；生成视频的数值是**相对于请求重力的偏差**，不是已知生成真值误差。只有测量适用性与参考控制同时成立，才能进一步解释模型差异。

当前入口支持 GravTrace、V/P 和本地/API Qwen；配置、统计口径和验证范围见 [EVALUATION.md](EVALUATION.md)。旧 public211 调度见 [PIPELINE.md](../PIPELINE.md)。

## 冻结 SAM3.1 前端

实际使用的单视角 SAM3.1 + RGB 处理 + V4 测量代码和便携入口现已公开，运行方法见 [SAM31.md](SAM31.md)。`tracks_v4.jsonl` 可直接传给上述固定窗口 `score`，反演方法不变。

## 一键入口与运行规范

安装、输入准备、完整登记示例、运行命令和结果文件见 [QUICKSTART.md](QUICKSTART.md)；12模型模式、原生时钟和专有依赖见 [MODELS.md](MODELS.md)。一键入口默认仅打印计划，显式 `--execute` 才串联真实生成、单视角SAM3.1、固定反演和汇总。当前每次运行一个模型，使用新的输出目录；不调用旧fleet、不自动下载或重试。

真实GPU验证目前只有一条LTX I2V运行验证，完整链路完成但V4为 `at_bound`，没有有效误差；其他模型和正式ID/OOD尚未实测。软件验证与物理有效性分别记录，当前没有完成完整 benchmark 的多指标评测。

### 自定义runner

已有外部调用可显式提供 `generation_command` **argv列表**覆盖登记入口，占位符仅为 `{manifest}`、`{run_dir}`、`{model_dir}`；不经过shell。此时 `{manifest}` 是合格生成子清单，全部注册样本仍在 `rows.jsonl` / `generation_rows.jsonl`，输出继续经过同一媒体、前端、评分方法，不能将外部runner的完成标记直接当评测成功。

### 完整输入与媒体绑定

输入构建默认保留全登记清单，不再默认抽取每重力8例。原内置提示只覆盖8类事件；其他事件须在item中提供预登记的 `generation_prompt`，否则保留为 `unsupported_registered_prompt_or_gravity`，不假造提示或删出分母。窗口不适用、缺源和缺初始提示均留下具体原因。参考媒体的容器时钟必须与登记fps一致；不均匀采样或不同物理时钟需要另有明确的时间定义，此入口不擅自改时钟。

完成检查逐帧解码整个视频，核对尺寸、总帧数、fps及每帧时间戳；无法可靠读取时间戳时拒绝。Diffusers runner以 `.partial.mp4` 写入，校验后才原子发布最终文件，另保存源码输入/登记/运行设置/媒体完成绑定；只有绑定和媒体再次验证都通过才能 `skip-existing`。坏文件、缺少完成记录的旧文件、已有 claim 的中断尝试不会触发自动重生成。

`tracks_v4.jsonl` 绑定实际视频SHA、fps、冻结前端manifest及测量文件SHA。评分在调用原fitter前拒绝旧前端、不同媒体/时钟或测量来源；整例缺帧仍失败。反演拟合器、生产相机、V4测量代码、数值范围及观察窗均不改。

### 独立汇总

新汇总使用显式输入路径，不再隐式读取旧runs：

```bash
python scripts/phyediting_gen_summary.py --items ITEMS.jsonl --rows ROWS.jsonl \
  --predictions RESULTS.jsonl --out SUMMARY.json
```

成功仅为 `status=ok` 且数值有效；`at_bound`、缺源、不适用、生成/跟踪/拟合失败及缺预测分别计入状态与原因。覆盖率为成功例/全部注册例，失败率为其补数；均值/最大/中位请求重力偏差只统计成功例。按原 `split`、事件、重力、相机分组，并以 `sample_id` 保留同一item的不同seed。没有split时标记unspecified，不推断ID/OOD归属；已有划分仍须用户确认并消费真实修正。

软件回归使用真实CPU媒体及人工模型观测/fit stub；CPU通过不等于模型GPU验收或科学认证。另已完成的LTX单条真实服务器运行验证及其失败状态见 [快速上手](QUICKSTART.md#已完成的验证)，不能作为独立ID/OOD成绩。
