# 快速上手

准备环境和输入后，将路径写入配置，即可运行生成、跟踪、参数测量及所选评测阶段。每次运行一个模型，支持的权重与参数见[模型说明](MODELS.md)。

## 安装

在已有PyTorch/CUDA环境中安装项目：

```bash
python -m pip install -e .
physedit --help
```

SAM3.1需要[官方源码和权重](SAM31.md#模型与环境)，生成模型需要对应依赖与本地权重。可使用下面的环境脚本建立独立环境。

<details>
<summary>配置SAM3.1运行环境</summary>

```bash
bash scripts/setup_phyediting_server.sh \
  --python /path/to/cuda-env/bin/python \
  --sam-source /path/to/sam3 \
  --checkpoint /path/to/sam3.1_multiplex.pt \
  --env-dir /path/to/physedit-env
source /path/to/physedit-env/activate_phyediting.sh
```

基础环境提供PyTorch/CUDA、Diffusers、Transformers、Accelerate、OpenCV、NumPy和SciPy。脚本建立独立venv，安装SAM及像素指标依赖，并检查源码、权重和CPU导入。模型专有依赖在生成环境中配置。

控制器与SAM使用激活后的Python；`generation_runtime.python`可指定独立生成环境。填写venv中的`bin/python`路径。

</details>

## 准备输入

| 输入 | 内容 |
| :---: | :---: |
| `items.jsonl` | 样本、目标物体、场景条件与观察窗口 |
| `data_root` | 参考视频目录 |
| `compact` | 初始场景几何与状态文件 |
| `applicability` | 参考清单与已有参数测量结果 |

每个样本包含`id`、`event`、`gravity`、`fps`、`image_size`、`video`、`trajectory`、`camera_id`、`object_name`、`camera`、`object`、`motion`和`window`。场景字段见[输入格式](../REFERENCE.md#样本格式)。

提示可通过`generation_prompt`提供；内置事件模板覆盖T03、T05、T08、T16–T20。`split`读取输入的集合标记，缺失时为`unspecified`。完整样本及其缺源、失败和不适用原因随结果保存。

## 配置一次

复制示例配置，填写数据、权重和环境路径：

```bash
cp examples/phyediting/pipeline.ltx.example.json pipeline.json
```

| 配置位置 | 填写内容 |
| :---: | :---: |
| `model`、`model_dir` | 模型键与本地权重 |
| `sam3`、`checkpoint` | SAM源码与权重 |
| `generation_runtime` | 生成Python、GPU和FFmpeg |
| `applicability` | 参考文件路径与SHA256 |
| `evaluation` | 重力、V/P与Qwen选项 |

示例已开启重力、V/P和Qwen API评测。Qwen也可使用[本地权重配置](../../examples/phyediting/pipeline.qwen-local.example.json)。帧数、帧率和画布由模型配置提供，配置项说明见[评测指南](EVALUATION.md)。

<details>
<summary>参考清单与输入检查</summary>

`applicability`包含`benchmark_items`、`reference_predictions`及对应的`benchmark_sha256`、`reference_predictions_sha256`。参考结果格式如下：

```json
{"id":"case01","target":9.81,"prediction":{"status":"ok","scenario":"projectile","gravity":9.8,"frames":12}}
```

检查比较样本身份、场景条件、观察窗口和实际时钟。参考失败、缺少文件或运动模型不适用的样本保留状态与原因。

</details>

## 运行与查看结果

```bash
physedit plan pipeline.json
physedit run pipeline.json --execute
physedit status runs/pipeline
```

`plan`检查输入和配置。`run`加`--execute`后执行，输出目录默认为`runs/<配置文件名>`；例如`wan.json`对应`runs/wan`。也可指定新的目录：

```bash
physedit run pipeline.json --run-dir runs/experiment_02 --execute
```

运行使用新目录，已有结果和中断输出保留。结果按阶段保存：

| 结果文件 | 内容 |
| :---: | :---: |
| `summary.json` | 各项误差、覆盖率与分组统计 |
| `predictions.jsonl` | 逐样本参数测量结果 |
| `evaluation/` | V/P与Qwen逐样本结果 |
| `sam31/` | 目标轨迹、掩膜与观测记录 |
| `registered.json` | 输入、配置与版本信息 |
| `completed.json`、`failure.json` | 执行状态与异常原因 |

误差统计有效估计，覆盖率使用全部输入样本。生成视频的参数分数表示相对请求值的偏差；详细定义见[生成评分](GENERATION.md#误差与覆盖率)。

已有视频补评见[评测指南](EVALUATION.md#已有视频补评)，独立参数测量见[速度与摩擦](MOTION_PARAMETERS.md)。原`python -m physedit`命令仍可使用。
