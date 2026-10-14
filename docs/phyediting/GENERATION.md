# 视频生成与参数评分

流水线从条件帧生成视频，跟踪目标，再测量请求参数的响应。模型、环境、提示和评测范围集中在配置文件中。

## 运行

```bash
physedit plan pipeline.json
physedit run pipeline.json --execute
```

输入与配置见[快速上手](QUICKSTART.md)。运行依次完成输入准备、视频生成、媒体检查、SAM3.1跟踪、固定窗口参数评分和可选V/P、Qwen评测。

## 观察时间与场景条件

条件图取参考视频第23帧。生成帧对应的物理时间为：

```text
t = 23 / source_fps + generated_frame / output_fps
```

观察窗口、物体几何与位姿、相机、角运动、质量和阻尼在评分前确定。初始线速度为待估参数，范围0–8m/s、仰角±89°；重力目标用于结果评分。非均匀源采样使用实际物理时间。

每个模型使用自己的生成帧数和帧率，参数比较采用相同的物理时间定义。帧数与时长见[模型说明](MODELS.md#采样参数)。

## 输入与观测检查

媒体检查完整视频的尺寸、帧数、帧率和时间戳。目标轨迹使用完整登记窗口，逐帧关联视频、对象和掩膜。所有输入样本保留在逐例结果中。

| 状态 | 含义 |
| :---: | :---: |
| `ok` | 有效参数估计 |
| `missing_observation` | 窗口内缺少目标观测 |
| `invalid_observation` | 目标框过小或不可用 |
| `at_bound` | 拟合达到参数边界 |
| `input_failure` | 缺源、输入格式或校验失败 |

目标框任一边长小于6px或面积小于36px时为不可用观测。固定评分保持预定窗口，记录出画、遮挡、身份变化和缺帧原因。

## 误差与覆盖率

参考视频报告相对真值误差，生成视频报告相对请求重力的偏差：

```text
relative_error = 100 × |estimated_g / target_g − 1|
coverage       = 有效估计数 / 全部输入样本数
failure_rate   = 1 − coverage
```

均值、中位数和最大值统计有效估计；失败、缺源和不适用按原ID及原因另列。结果按模型、seed、集合、事件、相机和参数分组。V/P及Qwen的各项分母见[评测指南](EVALUATION.md)。

## 读取与补评结果

`summary.json`给出综合统计，`predictions.jsonl`保存逐例估计，`evaluation/`保存V/P和Qwen输出。补评已有视频：

```bash
physedit evaluate pipeline.json --run runs/pipeline --out runs/evaluation --execute
```

速度与摩擦使用[独立测量入口](MOTION_PARAMETERS.md)。

<details>
<summary>底层命令与外部生成器</summary>

已有跟踪结果可单独评分：

```bash
python scripts/phyediting_gen.py score items.jsonl rows.jsonl tracks.jsonl predictions.jsonl
python scripts/phyediting_gen_summary.py --items items.jsonl --rows rows.jsonl \
  --predictions predictions.jsonl --out summary.json
```

默认评分使用`--v0 agnostic --offset-mode anchor`，关闭自动接触裁窗。场景、模型和观测文件由SHA关联。

外部生成器通过`generation_command`配置argv列表，支持`{manifest}`、`{run_dir}`和`{model_dir}`占位符。其输出经过相同媒体检查、目标跟踪和参数评分。

生成媒体先写入`.partial.mp4`，完成检查后发布。已有结果、运行日志和中断产物保存在各自运行目录。

</details>
