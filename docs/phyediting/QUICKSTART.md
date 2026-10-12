# PhyEditing 一键流水线快速上手

使用顺序：准备服务器环境和真实输入 → 登记模型与设备 → 查看计划 → 显式执行 → 检查逐例结果与汇总。当前入口一次运行一个模型、一个登记清单；12模型的配置见 [MODELS.md](MODELS.md)。

当前链路包括条件图与提示构建、I2V/V2V 生成、完整媒体校验、单视角 SAM3.1＋V4、固定窗口未知速度反演和全部注册样本汇总。每条任务只使用一个视频，不融合三机位。[评分方法](GENERATION.md)与[冻结前端](SAM31.md)规定实际输入、时钟和失败处理。Qwen/V/P 未接入，详见[评测指标与接入状态](EVALUATION.md)。

## 1. 配置服务器环境

先将本仓库克隆到服务器，在仓库根目录运行下面的命令。需要事先已有：

- 可用的 GPU Python 环境及 PyTorch/CUDA、Diffusers、Transformers、Accelerate、OpenCV、NumPy、SciPy；各模型可能还有专有依赖。
- [冻结版本](SAM31.md#依赖与版本)的官方 SAM3 Git checkout 和 SAM3.1 multiplex checkpoint。
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

## 2. 准备真实输入

输入必须包含媒体、声明的场景条件和预登记窗口；`pipeline.json` 本身不会构造数据集或推断测试划分。

| 输入 | 内容 |
| --- | --- |
| `items.jsonl` | 每行一个唯一 `id`；事件、请求重力、源fps/尺寸、视频路径、轨迹ID、相机ID、目标名、声明相机/几何/初始状态和窗口 |
| `data_root` | 源视频根目录；与每个 item 的 `video` 路径结合定位实际媒体 |
| `compact` | 每个 `trajectory` 对应的 `.json` 和 `.npz`，用于从源第23帧声明几何生成初始场景框 |

item字段为 `id`、`event`、`gravity`、`fps`、`image_size`、`video`、`trajectory`、`camera_id`、`object_name`、`camera`、`object`、`motion`、`window`，可带 `split`、`generation_prompt`、`input_failure`。相机/几何/运动字段格式见 [REFERENCE.md](../REFERENCE.md#sample-format)，构建实现见 [phyediting_gen.py](../../scripts/phyediting_gen.py)。窗口须由来源规范预登记，不能根据生成效果选择。

内置事件提示覆盖 T03/T05/T08/T16/T17/T18/T19/T20；其他事件必须在 item 中提供 `generation_prompt`。已有提示包含事件结果描述，应按该控制任务解释，不称无结果提示的因果预测。缺源、不适用或未支持的提示保留在分母并列出失败原因。

`split` 使用输入的真实登记值；缺失时为 `unspecified`。入口不会执行联合划分，也不会自动应用三条归属修正。正式 ID/OOD 评测须另行确认清单与修正后再登记输入。

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
  "evaluation": {"metrics": ["gravtrace"]},
  "generation_runtime": {
    "python": "/absolute/path/new-phyediting-env/bin/python",
    "gpu_devices": "0",
    "ffmpeg": "/absolute/path/ffmpeg"
  }
}
```

`evaluation.metrics` 当前仅支持 `gravtrace`，未支持的评测项和未知配置字段会在启动前报错。`model` 选用 [12个登记键](MODELS.md)，帧数、fps和画布自动使用对应原生配置；显式填入 `frames` / `fps` 必须一致。需要的 `code_dir`、`lora_dir` 等放在 `generation_runtime`。模型路径始终是已有本地权重，不在运行时下载。

## 4. 查看计划与执行

```bash
# 仓库根目录；只核对登记结构、items身份及冻结仓库源码。
"$PHYEDIT_PYTHON" -m physedit run phyediting \
  --spec pipeline.json --run-dir runs/new_generation

# 显式运行；spec中的gpu_devices同时用于生成和SAM3.1。
"$PHYEDIT_PYTHON" -m physedit run phyediting \
  --spec pipeline.json --run-dir runs/new_generation --execute

"$PHYEDIT_PYTHON" -m physedit status phyediting --run-dir runs/new_generation
```

默认计划不创建运行目录、不联网、不启动模型，也不证明服务器路径、模型格式或GPU可用。真实执行在生成前检查前端版本/权重和模型运行路径，随后依次处理各阶段。它是本机单进程控制器，没有远程GPU分配、自动下载或自动重试；一次命令运行一个模型，逐模型验收后再组织多模型实验。

执行必须使用新的运行目录；失败及中断留下日志、claim和partial。不要删除旧失败来复用同一目录。CLI在任何注册案例失败时返回非零状态，可能已有部分阶段完成；检查下面的逐例文件判定原因。

## 5. 读取结果

| 路径（相对于运行目录） | 用途 |
| --- | --- |
| `registered.json`、`items.jsonl` | 输入清单、配置、全登记分母和版本绑定 |
| `input/`、`rows.jsonl` | 条件图/提示及全部原始登记案例 |
| `generation.log`、`registered_model_status.jsonl`（若产生） | 模型运行日志、逐例运行状态 |
| `observed_rows.jsonl` | 媒体核验后的全登记案例及失败原因 |
| `sam31/tracks_v4.jsonl`、`sam31/measurements_v4.jsonl` | 视频/前端/测量SHA绑定和完整窗口观测 |
| `predictions.jsonl` | 原ID的冻结拟合状态；`at_bound` 为失败，不填有效误差 |
| `summary.json` | 成功数、失败数、覆盖率、失败率、请求重力偏差及分组统计 |
| `completed.json` / `failure.json`、`controller_failures.jsonl`（异常时） | 控制器完成/异常凭据；不等于全部样本科学通过 |

只有 `status=ok` 且数值有效才计评分成功。覆盖率=成功数/全部注册例，失败率为其补数；成功例均值和最大值须与分母/失败原因一起报告。生成视频没有已知物理真值，这里的数值是相对请求重力的偏差。精确口径见 [GENERATION.md](GENERATION.md#结果口径)。

## 已完成的验证

12个模型的登记、模式限制、启动argv及CPU媒体/故障测试已验证。site_a上实际完成一条 LTX I2V 的生成→SAM3.1→V4→汇总：81帧/16fps，10/10计划观测帧有观测；拟合触及重力下界，状态 `at_bound`，成功0/1、失败1/1，无有效误差。这证明本次链路能够执行，尚未得到合格的物理评分。

服务器安装脚本和 GitHub 克隆版预检另已通过。后续代码及文档修改没有重新运行 GPU 推理；其余11模型尚未真实GPU验收，正式 ID/OOD 反演成绩尚未测量。

仅需SAM3.1跟踪时使用 [SAM31.md](SAM31.md#单视角输入与运行)；已有观测的手工评分接口见 [GENERATION.md](GENERATION.md#命令接口)；旧 `public211` 多机流程见 [PIPELINE.md](../PIPELINE.md)。
