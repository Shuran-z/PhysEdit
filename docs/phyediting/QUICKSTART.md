# PhyEditing 一键流水线快速上手

使用顺序：准备服务器环境和真实输入 → 登记模型与设备 → 查看计划 → 显式执行 → 检查逐例结果与汇总。当前入口一次运行一个模型、一个登记清单；12模型的配置见 [MODELS.md](MODELS.md)。

当前链路包括条件图与提示构建、I2V/V2V 生成、完整媒体校验、单视角 SAM3.1＋V4、固定窗口未知速度反演、V/P 定量指标、Qwen 视觉判断和全部注册样本汇总。每条任务只使用一个视频，不融合三机位。[评分方法](GENERATION.md)与[冻结前端](SAM31.md)规定实际输入、时钟和失败处理。本地/API及指标口径详见[评测指标与接入状态](EVALUATION.md)。

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

填写虚拟环境内的 `bin/python` 路径，保留该调用路径，不把它替换为符号链接指向的基础环境Python。各模型已检查的依赖组合和真实运行状态见 [MODELS.md](MODELS.md)；仅成功导入控制器环境不足以证明生成环境兼容。

## 2. 准备真实输入

输入必须包含媒体、声明的场景条件和预登记窗口；`pipeline.json` 本身不会构造数据集或推断测试划分。

| 输入 | 内容 |
| --- | --- |
| `items.jsonl` | 每行一个唯一 `id`；事件、请求重力、源fps/尺寸、视频路径、轨迹ID、相机ID、目标名、声明相机/几何/初始状态和窗口 |
| `data_root` | 源视频根目录；与每个 item 的 `video` 路径结合定位实际媒体 |
| `compact` | 每个 `trajectory` 对应的 `.json` 和 `.npz`，用于从源第23帧声明几何生成初始场景框 |

item字段为 `id`、`event`、`gravity`、`fps`、`image_size`、`video`、`trajectory`、`camera_id`、`object_name`、`camera`、`object`、`motion`、`window`，可带 `split`、`generation_prompt`、`input_failure`。相机/几何/运动字段格式见 [REFERENCE.md](../REFERENCE.md#sample-format)，构建实现见 [phyediting_gen.py](../../scripts/phyediting_gen.py)。窗口须由来源规范预登记，不能根据生成效果选择。

内置事件提示覆盖 T03/T05/T08/T16/T17/T18/T19/T20；其他事件必须在 item 中提供 `generation_prompt`。已有提示包含事件结果描述，应按该控制任务解释，不称无结果提示的因果预测。缺源、不适用或未支持的提示保留在分母并列出失败原因。

输入须绑定已有核验清单与原冻结参考反演记录。在 `applicability` 中提供 `benchmark_items`、`reference_predictions` 两个 JSONL 路径及对应 `benchmark_sha256`、`reference_predictions_sha256`；不能为通过检查伪造记录。参考记录使用已有逐例格式：`{"id":"...","target":9.81,"prediction":{"status":"ok","scenario":"projectile","gravity":9.8,"frames":12}}`。清单的原相机、几何、运动、时钟、窗口和身份必须一致；仅 `split`、预登记提示和原失败说明可另附。检查不使用新生成结果，也不重新拟合或找窗。缺证据、参考失败、运动模型不支持、时钟不覆盖或原计划帧完全不可见，整例登记不适用并保留分母，不启动生成。

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
  "applicability": {
    "benchmark_items": "/absolute/path/verified_benchmark_items.jsonl",
    "benchmark_sha256": "SHA256_OF_VERIFIED_BENCHMARK_ITEMS",
    "reference_predictions": "/absolute/path/frozen_reference_predictions.jsonl",
    "reference_predictions_sha256": "SHA256_OF_FROZEN_REFERENCE_PREDICTIONS"
  },
  "evaluation": {
    "metrics": ["gravtrace", "vp", "qwen"],
    "vp": {"mask_backend": "sam31", "reference_duration_seconds": 1.0, "reference_fps": 30},
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
# 仓库根目录；核对登记结构、参考证据SHA、逐例资格、时钟覆盖及冻结源码。
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
| `input/inversion_applicability.json` | 原核验清单/参考预测SHA、逐例资格与不适用原因 |
| `generation.log`、`registered_model_status.jsonl`（若产生） | 模型运行日志、逐例运行状态 |
| `observed_rows.jsonl` | 媒体核验后的全登记案例及失败原因 |
| `sam31/tracks_v4.jsonl`、`sam31/measurements_v4.jsonl` | 视频/前端/测量SHA绑定和完整窗口观测 |
| `predictions.jsonl` | 原ID的冻结拟合状态；`at_bound` 为失败，不填有效误差 |
| `evaluation/vp_results.jsonl`、`evaluation/qwen_results.jsonl` | 各阶段全登记逐例状态、指标、证据及失败原因 |
| `summary.json` | 重力统计与 `evaluations.vp` / `evaluations.qwen` 的独立覆盖率和分组统计 |
| `completed.json` / `failure.json`、`controller_failures.jsonl`（异常时） | 控制器完成/异常凭据；不等于全部样本科学通过 |

只有 `status=ok` 且数值有效才计整例评分成功；Qwen的 `partial` 另按各类别的 `assessable` 报告覆盖率，不把未知类别计成无违规。覆盖率=成功数/全部注册例，失败率为其补数；成功例均值和最大值须与分母/失败原因一起报告。生成视频没有已知物理真值，这里的数值是相对请求重力的偏差。精确口径见 [GENERATION.md](GENERATION.md#结果口径)。

## 已完成的验证

12个模型的登记、模式限制、启动argv及CPU媒体/故障测试已验证。site_a上实际完成一条 LTX I2V 的生成→SAM3.1→V4→汇总：81帧/16fps，10/10计划观测帧有观测；拟合触及重力下界，状态 `at_bound`，成功0/1、失败1/1，无有效误差。这证明本次链路能够执行，尚未得到合格的物理评分。

随后已在与 GitHub 文件树一致的服务器版本执行同一条完整评测：公开脚本创建独立环境，真实 SAM3.1 全片段掩膜及18项 V/P 正常产出；Qwen2.5-VL-3B 实际推理返回证据不足，未计评分。反演仍为 `at_bound`，最终退出码1正确保留这两个未评分原因。修复 Qwen 加载兼容和已注册事件/机位的汇总分组遗漏；只用既有结果修正汇总，没有重跑生成或拟合。不能把链路完成称为全部评分成功。

原 T04 工程烟测失败已诊断为输入运动模型不适用：支撑/滑动早期窗口不能直接按自由飞行反演。原产物保留，新输入检查阻止无资格记录的输入启动生成；冻结拟合器与评分窗口不变。

随后使用已有核验资格的 T03 输入完成另一条 LTX 链路：冻结反演及18项 V/P 均产出有效数值。修复后的 Qwen 入口单独重评同一条已有视频，12帧采样覆盖全片时间范围，输出结构与汇总通过；没有重跑生成或反演。3B 模型的依据仍偏笼统，判断准确性尚未验证；详细范围见 [EVALUATION.md](EVALUATION.md#汇总与验证范围)。

另已逐条执行CogVideoX/T08、Wan/T17和Hunyuan/T19，均真实生成完整视频。Wan、Hunyuan曾因虚拟环境路径被解引用而加载失败，修复后在新目录各补跑一次，旧失败保留。各阶段实际有效性见 [MODELS.md](MODELS.md)；另8模型、外部视频API及正式ID/OOD尚未实测，不能称12模型全流程验收。

仅需SAM3.1跟踪时使用 [SAM31.md](SAM31.md#单视角输入与运行)；已有观测的手工评分接口见 [GENERATION.md](GENERATION.md#命令接口)；旧 `public211` 多机流程见 [PIPELINE.md](../PIPELINE.md)。

评测逐项保留可用证据：V/P按登记帧范围处理缺失，Qwen按类别保留合法回答；已确认的目标误跟踪可用 `evaluation.vp.mask_review_manifest` 作SHA绑定的否决复核。字段与范围见 [评测说明](EVALUATION.md)，不会改变冻结反演或自动重跑生成。
