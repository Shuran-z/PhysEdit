# PhysEdit快速上手

使用顺序：准备服务器环境和真实输入 → 登记模型与设备 → 查看计划 → 显式执行 → 检查逐例结果与汇总。每次运行一个模型、一个登记清单；12模型的配置见 [MODELS.md](MODELS.md)。

流水线包括条件图与提示构建、I2V/V2V 生成、完整媒体校验、SAM3.1单视角跟踪与边界测量、固定窗口未知速度反演、V/P 定量指标、Qwen 视觉判断和全部注册样本汇总。每条任务只使用一个视频，不融合三机位。[评分方法](GENERATION.md)与[目标跟踪](SAM31.md)规定实际输入、时钟和失败处理。本地/API及指标口径详见[评测指标](EVALUATION.md)。

## 1. 配置服务器环境

先将本仓库克隆到服务器，在仓库根目录运行下面的命令。需要事先已有：

- 可用的 GPU Python 环境及 PyTorch/CUDA、Diffusers、Transformers、Accelerate、OpenCV、NumPy、SciPy；各模型可能还有专有依赖。
- [模型依赖](SAM31.md#依赖与版本)的官方 SAM3 Git checkout 和 SAM3.1 multiplex checkpoint。
- 本机生成模型权重、必要的模型代码/LoRA、可执行的 FFmpeg；使用 PhysRVG 还需要 FFprobe。
- 当前已确认可使用且空闲的 GPU。以下设备 `0` 是配置示例，运行前按实际设备修改。

```bash
bash scripts/setup_phyediting_server.sh \
  --python /absolute/path/to/existing/gpu-env/bin/python \
  --sam-source /absolute/path/to/official-sam3-git \
  --checkpoint /absolute/path/to/sam3.1_multiplex.pt \
  --env-dir /absolute/path/to/new-phyediting-env
source /absolute/path/to/new-phyediting-env/activate_phyediting.sh
```

脚本创建继承既有 GPU 环境包的独立 venv，安装 `setuptools==70.3.0`、`timm==1.0.28` 和本仓库，再以 CPU 实际导入依赖、核对官方 SAM commit 与权重 SHA。包安装需要可用的包源；脚本不下载模型权重，也不安装 CUDA/PyTorch 或所有模型专有依赖。它保持旧环境和旧 SAM 安装，已有目标目录会拒绝覆盖。检查失败时保留新目录，先查看报错。

`PHYEDIT_PYTHON` 用于控制器和 SAM3.1；`generation_runtime.python` 用于生成模型，可以使用另一个兼容的环境。激活脚本导出 `PYTHONPATH` 和三个 `PHYEDIT_*` 路径变量，不替代模型专有环境配置。

填写虚拟环境内的 `bin/python` 路径，保留该调用路径，不把它替换为符号链接指向的基础环境Python。各模型已检查的依赖组合和真实运行状态见 [MODELS.md](MODELS.md)；控制器与生成模型使用各自的依赖环境。

## 2. 准备真实输入

输入包含媒体、场景条件和预登记观察窗口，数据集划分由输入清单提供。

| 输入 | 内容 |
| --- | --- |
| `items.jsonl` | 每行一个唯一 `id`；事件、请求重力、源fps/尺寸、视频路径、轨迹ID、相机ID、目标名、声明相机/几何/初始状态和窗口 |
| `data_root` | 源视频根目录；与每个 item 的 `video` 路径结合定位实际媒体 |
| `compact` | 每个 `trajectory` 对应的 `.json` 和 `.npz`，用于从源第23帧声明几何生成初始场景框 |

item字段为 `id`、`event`、`gravity`、`fps`、`image_size`、`video`、`trajectory`、`camera_id`、`object_name`、`camera`、`object`、`motion`、`window`，可带 `split`、`generation_prompt`、`input_failure`。相机/几何/运动字段格式见 [REFERENCE.md](../REFERENCE.md#样本格式)，构建实现见 [phyediting_gen.py](../../scripts/phyediting_gen.py)。窗口须由来源规范预登记，不能根据生成效果选择。

内置事件提示覆盖 T03/T05/T08/T16/T17/T18/T19/T20；其他事件必须在 item 中提供 `generation_prompt`。已有提示包含事件结果描述，应按该控制任务解释，不称无结果提示的因果预测。缺源、不适用或未支持的提示保留在分母并列出失败原因。

输入须绑定已有核验清单与参考测量记录。在 `applicability` 中提供 `benchmark_items`、`reference_predictions` 两个 JSONL 路径及对应 `benchmark_sha256`、`reference_predictions_sha256`；清单和参考结果使用已有核验文件。参考记录使用已有逐例格式：`{"id":"...","target":9.81,"prediction":{"status":"ok","scenario":"projectile","gravity":9.8,"frames":12}}`。清单的原相机、几何、运动、时钟、窗口和身份必须一致；仅 `split`、预登记提示和原失败说明可另附。检查不使用新生成结果，也不重新拟合或找窗。缺证据、参考失败、运动模型不支持、时钟不覆盖或原计划帧完全不可见，整例登记不适用并保留分母，不启动生成。

`split`读取输入清单的集合标记，缺失时为`unspecified`。ID、OOD-1和OOD-2评测使用按[联合划分协议](../joint_split_v3/PROTOCOL.md)审核后的清单。

## 3. 登记模型和路径

复制 [pipeline.ltx.example.json](../../examples/phyediting/pipeline.ltx.example.json) 为自己的 `pipeline.json`，将所有示例路径换成服务器实际绝对路径：

```json
{
  "items": "/absolute/path/items.jsonl",
  "data_root": "/absolute/path/reference_videos",
  "compact": "/absolute/path/compact",
  "model": "ltx_i2v",
  "model_dir": "/absolute/path/ltx_weights",
  "sam3": "/absolute/path/official-sam3-git",
  "checkpoint": "/absolute/path/sam3.1_multiplex.pt",
  "seed": 20261008,
  "applicability": {
    "benchmark_items": "/absolute/path/verified_benchmark_items.jsonl",
    "benchmark_sha256": "SHA256_OF_VERIFIED_BENCHMARK_ITEMS",
    "reference_predictions": "/absolute/path/frozen_reference_predictions.jsonl",
    "reference_predictions_sha256": "SHA256_OF_FROZEN_REFERENCE_PREDICTIONS"
  },
  "evaluation": {
    "metrics": ["gravtrace", "vp", "qwen"],
    "vp": {"mask_backend": "sam31", "reference_duration_seconds": 1.0, "reference_fps": 30, "trajectory_duration_seconds": 5, "trajectory_sampling_fps": 30},
    "qwen": {"backend": "api", "model": "Qwen/Qwen3.5-9B",
             "base_url": "http://127.0.0.1:8000/v1", "api_key_env": "QWEN_API_KEY",
             "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}}
  },
  "generation_runtime": {
    "python": "/absolute/path/new-phyediting-env/bin/python",
    "gpu_devices": "0",
    "ffmpeg": "/absolute/path/ffmpeg"
  }
}
```

`evaluation.metrics` 支持 `gravtrace`、`vp`、`qwen`；Qwen 输入为完整生成视频与条件图，必须配置本地权重或支持原生 video_url 的视频 API 服务。完整配置及只补评已有产物的命令见 [EVALUATION.md](EVALUATION.md)。未支持的评测项和未知配置字段会在启动前报错。`model` 选用 [12个登记键](MODELS.md)，帧数、fps和画布自动使用对应原生配置；显式填入 `frames` / `fps` 必须一致。需要的 `code_dir`、`lora_dir` 等放在 `generation_runtime`。模型路径始终是已有本地权重，不在运行时下载。

## 4. 查看计划与执行

```bash
# 仓库根目录；核对登记结构、参考证据SHA、逐例资格、时钟覆盖及源码校验。
"$PHYEDIT_PYTHON" -m physedit run phyediting \
  --spec pipeline.json --run-dir runs/new_generation

# 显式运行；spec中的gpu_devices同时用于生成和SAM3.1。
"$PHYEDIT_PYTHON" -m physedit run phyediting \
  --spec pipeline.json --run-dir runs/new_generation --execute

"$PHYEDIT_PYTHON" -m physedit status phyediting --run-dir runs/new_generation
```

默认命令检查计划；服务器路径、模型格式和GPU在执行阶段检查。真实执行在生成前检查前端版本/权重和模型运行路径，随后依次处理各阶段。它是本机单进程控制器，没有远程GPU分配、自动下载或自动重试；一次命令运行一个模型，逐模型验收后再组织多模型实验。

执行必须使用新的运行目录；失败及中断留下日志、claim和partial。补跑使用新目录，保留原日志和产物。任一登记案例失败时CLI返回非零状态，各阶段已完成的结果仍在逐例文件中。

## 5. 读取结果

| 路径（相对于运行目录） | 用途 |
| --- | --- |
| `registered.json`、`items.jsonl` | 输入清单、配置、全登记分母和版本绑定 |
| `input/`、`rows.jsonl` | 条件图/提示及全部原始登记案例 |
| `input/inversion_applicability.json` | 原核验清单/参考预测SHA、逐例资格与不适用原因 |
| `generation.log`、`registered_model_status.jsonl`（若产生） | 模型运行日志、逐例运行状态 |
| `observed_rows.jsonl` | 媒体核验后的全登记案例及失败原因 |
| `sam31/tracks_v4.jsonl`、`sam31/measurements_v4.jsonl` | 视频/前端/测量SHA绑定和完整窗口观测 |
| `predictions.jsonl` | 各样本的拟合状态；`at_bound` 为失败，不填有效误差 |
| `evaluation/vp_results.jsonl`、`evaluation/qwen_results.jsonl` | 各阶段全登记逐例状态、指标、证据及失败原因 |
| `summary.json` | 参数误差/覆盖率/失败率、登记组内响应与排序，以及独立V/P辅助项和Qwen统计 |
| `completed.json` / `failure.json`、`controller_failures.jsonl`（异常时） | 控制器执行状态及异常记录 |

只有 `status=ok` 且数值有效才计整例评分成功；Qwen的 `partial` 另按各类别的 `assessable` 报告覆盖率，不把未知类别计成无违规。覆盖率=成功数/全部注册例，失败率为其补数；成功例均值和最大值须与分母/失败原因一起报告。生成视频没有已知物理真值，这里的数值是相对请求重力的偏差。精确口径见 [GENERATION.md](GENERATION.md#结果口径)。

## 运行验证

安装后先检查计划、输入SHA和设备配置，再选择单条样本运行。读取逐例文件确认生成、跟踪、反演及所选评测阶段的状态；各模型的权重、参数和运行状态见[MODELS.md](MODELS.md)。

单独跟踪使用[SAM31.md](SAM31.md)，既有观测评分使用[GENERATION.md](GENERATION.md#命令接口)，已有视频补评使用[EVALUATION.md](EVALUATION.md#只补评既有生成产物)。多机调度见[PIPELINE.md](../PIPELINE.md)。
