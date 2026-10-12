# 生成模型配置与支持范围

12个模型均接入 `python -m physedit run phyediting`。当前每次命令选一个 `model`；统一入口支持登记、生成、单视角SAM3.1和固定评分，不表示12个模型都已经在服务器实测成功。

| 验证层级 | 当前证据 |
| --- | --- |
| 代码接入与CPU验证 | 12模型的计划、模式限制、argv与媒体/故障处理已验证 |
| 真实GPU端到端 | 仅 LTX I2V 单条site_a运行验证完成；拟合 `at_bound`、0/1有效评分 |
| 正式模型比较与ID/OOD | 尚未完成；其余11模型未真实GPU验收 |

此入口当前仅提供 GravTrace 评分；Qwen 和 V/P 的状态见 [EVALUATION.md](EVALUATION.md)。先按 [QUICKSTART.md](QUICKSTART.md)准备环境、输入和运行登记，评分口径见 [GENERATION.md](GENERATION.md)。仅接受I2V/V2V；不提供纯T2V调用。

## 模型配置

统一入口登记12个模型，按模型自动使用原生帧数、帧率与画布。显式填写 `frames` / `fps` 时必须与模型登记相同，避免输入切换模型后沿用旧时钟：

| 一键模型键 | 帧数／fps | 条件模式／入口 | 额外 `generation_runtime` | 本流水线GPU实测 |
| --- | --- | --- | --- | --- |
| `ltx_i2v` | 81/16 | I2V／Diffusers | 无 | 单条链路完成；拟合 `at_bound` |
| `cogvideox_i2v` | 81/16 | I2V／Diffusers | 无 | 未实测 |
| `wan_ti2v5b` | 81/16 | I2V／Diffusers | 无 | 未实测 |
| `hunyuan15_i2v` | 121/24 | I2V／Diffusers | 无 | 未实测 |
| `cosmos` | 81/16 | Cosmos-Predict2 V2V／单条件帧视频 | `code_dir` | 未实测 |
| `dynamicrafter_i2v` | 16/8 | I2V／DynamiCrafter | `code_dir`；权重路径为checkpoint文件 | 未实测 |
| `videogpa_ti2v5b` | 49/15 | I2V／VideoGPA | `code_dir`, `lora_dir` | 未实测 |
| `physrvg_ti2v5b` | 49/15 | I2V／PhysRVG | `code_dir`, `lora_dir` | 未实测 |
| `cosmos3_nano` | 81/16 | I2V／Cosmos3 | 无 | 未实测 |
| `wan22_i2v_a14b` | 81/16 | I2V／Wan官方入口 | `code_dir` | 未实测 |
| `physalign_wan22_i2v_a14b` | 81/16 | I2V／Wan＋PhysAlign | `code_dir`, `lora_dir`, `physalign_hook_dir` | 未实测 |
| `minimax_h3` | 124/24 | I2V／MiniMax FL2VA | 无 | 未实测 |

本流水线仅允许 **I2V/V2V**，排除纯 T2V 模型和纯 T2V 调用。`wan_ti2v5b` 使用 `WanImageToVideoPipeline` 并传入登记的 `condition_image`；`videogpa_ti2v5b` 和 `physrvg_ti2v5b` 也传入图像。TI2V 名称不改变实际图像条件路径。计划输出会显示 `conditioning_mode`；登记的 `mode` 或 `conditioning_mode` 请求不同模式时，在启动前拒绝；外部 argv 的显式 T2V 登记也拒绝。外部代码实际是否消费条件图仍需单独验收，argv 登记不能自动证明其输入行为。

`model_dir` 始终指向本机已经存在的模型权重；其余路径指向已经部署的模型代码和适配器。不同模型可选 `generation_runtime.python`、`gpu_devices`、`pythonpath` 路径列表及 `ffmpeg`；不自动下载或安装。示例：

```json
{"model":"physrvg_ti2v5b","model_dir":"/absolute/path/wan_diffusers","generation_runtime":{"python":"/absolute/path/model_env/bin/python","code_dir":"/absolute/path/physrvg_code","lora_dir":"/absolute/path/lora_checkpoint","gpu_devices":"0"}}
```

启动模型前检查所需代码和权重路径，并先在 CPU 核对冻结 SAM3.1 源码版本与权重 SHA；不匹配时保留逐例失败，不花费生成 GPU 时间。四个 Diffusers 入口也使用登记的 `generation_runtime.python`、GPU 映射、`pythonpath` 和 `ffmpeg`，强制本地权重加载及 offline 环境。使用 ImageIO 的旧 runner 同样绑定登记的 FFmpeg。运行一键控制器的 Python 环境需已安装冻结 SAM3.1 的实际运行依赖；模型专属环境可分别指定。所有旧 runner 以 argv 调用，不经 shell；每条尝试有持久 claim，旧输出、部分输出或中断不自动重试。生成后按登记媒体完整解码、核对尺寸／帧数／时钟、输入 SHA，并封存完成凭据；独立控制器再次核验后才进入 SAM3.1。原始登记分母和所有失败原因保留在 `rows.jsonl`、`observed_rows.jsonl` 与 `registered_model_status.jsonl`。

`cosmos` 只把声明的条件帧写成单帧 V2V 输入，绝不把参考视频第24帧后的运动交给模型；模型仍需在目标环境验证其单帧条件接口。PhysRVG 采用五次复制同一条件帧的 `static_frame` 策略，不读参考前史。VideoGPA 保留独立 LoRA 输入与后处理。模型原生运行环境、权重格式和实际 GPU 输出仍需逐模型验收；代码接入与 CPU软件验证不等于12模型已经生成成功。

## 切换模型

修改 `pipeline.json` 的 `model`、`model_dir` 和相应 `generation_runtime`，使用新的 `run-dir`。帧数/fps不必手写；不同模型不能沿用其他模型的时钟。所有表中模型的 `conditioning_mode` 默认为 `i2v`，仅 `cosmos` 为 `v2v_one_condition_frame`。

`cosmos3_nano` 在本注册入口中为图像条件；MiniMax-H3 为FL2VA图像条件。MiniMax runner支持单GPU共享offload或多GPU环境，但相应显存/格式/吞吐尚未在本流水线验收；旧fleet的双GPU配置不是当前单条运行验证证据。DynamiCrafter的 `model_dir` 是checkpoint文件，其他模型按各runner所需的本地权重格式配置。

控制器/SAM3.1使用启动命令的 Python，生成模型可使用 `generation_runtime.python` 指定的环境。`generation_runtime.gpu_devices` 同时设置生成和 SAM3.1 的设备映射；省略时沿用启动进程的映射。运行示例见 [快速上手](QUICKSTART.md#4-查看计划与执行)。

无需重新生成也能检查模型登记：

```bash
python -m physedit models
python -m physedit run phyediting --spec pipeline.json --run-dir runs/new_model
```

第一个命令显示共享的模型配置；本地PhyEditing入口的原生时钟/模式以 [oneclick_registry.py](../../physedit/runners/oneclick_registry.py)为准。第二个命令仅打印计划；缺权重/专有依赖/不兼容输出须在真实逐模型验收中保留失败，不能称全支持已经实测。
