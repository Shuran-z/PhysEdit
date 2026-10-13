# 生成模型与采样参数

12个模型接入统一入口；I2V 与完整 V2V 编辑分别登记、分别汇报。本轮验证覆盖真实 CPU 媒体、模型调用参数、故障保留和冻结源码一致性，没有运行批量生成，也没有完成12模型的GPU验收。

## 权重与参数

`phyediting_sampling_v2` 明确区分官方模型配置、API默认值、官方示例和本地适配。下表是当前一键入口实际使用的参数；步数、CFG、flow shift 和 LoRA 强度不能当作同一个“去噪强度”。更换蒸馏版或其他权重必须另行登记，不能仅沿用模型名称。`python -m physedit models --json` 输出可核对的全部参数、条件模式与时间范围。

| 模型键／对应权重 | 帧数／fps；首末帧跨度 | 步数／CFG；其他参数 | 来源与适用范围 |
|---|---|---|---|
| `ltx_i2v`／LTX-Video-2B 非蒸馏版 | 161/25；6.4s | 50/3；显式 `frame_rate=25` | [Diffusers 0.39 LTX API](https://github.com/huggingface/diffusers/blob/v0.39.0/src/diffusers/pipelines/ltx/pipeline_ltx_condition.py) 默认值；不适用于13B蒸馏版 |
| `cogvideox_i2v`／CogVideoX1.5-5B-I2V | 81/16；5s | 50/6 | [官方仓库](https://github.com/zai-org/CogVideo)、[权重卡](https://huggingface.co/THUDM/CogVideoX1.5-5B-I2V)；仓库1.5规格为16fps，权重卡示例导出8fps存在差异，采用仓库规格并记录实际时钟 |
| `wan_ti2v5b`／Wan2.2-TI2V-5B | 121/24；5s | 50/5；shift=5 | [官方5B配置](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/wan_ti2v_5B.py)；通过图像条件接口调用，排除T2V |
| `hunyuan15_i2v`／480p I2V step-distilled | 121/24；5s | 12/1；shift=7 | [官方变体推荐](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5#inference-configurations)；仅CFG-distilled版为50/1、shift=5，不能混用 |
| `cosmos`／Cosmos-Predict2-2B-Video2World 16fps | 81/16；5s | CFG=7；步数继承本机producer | [官方Video2World](https://github.com/nvidia-cosmos/cosmos-predict2/blob/main/examples/video2world.py)；本机helper未提供步数覆盖，须另核验其版本；单帧前缀续写，不是完整V2V编辑 |
| `dynamicrafter_i2v`／DynamiCrafter-1024 | 16/10；1.5s | 50/7.5；eta=1、rescale=.7、trailing | [官方1024脚本](https://github.com/Doubiiu/DynamiCrafter/blob/main/scripts/run.sh) 的FS=10表示模型FPS；[保存代码](https://github.com/Doubiiu/DynamiCrafter/blob/main/scripts/evaluation/inference.py)使用8fps，适配器保留原文件并以10fps写出相同16帧，禁止补帧 |
| `videogpa_ti2v5b`／VideoGPA Wan2.2-TI2V-5B LoRA | 81/24；3.333s | 50/5；shift=5、LoRA=.2 | [官方推理脚本](https://github.com/Hongyang-Du/VideoGPA/blob/main/generate/Wan2.2-TI2V-5B.py) 的默认参数 |
| `physrvg_ti2v5b`／PhysRVG Wan2.2-TI2V-5B LoRA | 49/15；3.2s | 16/5；`do_cfg=false` | 本地I2V适配值；[官方README](https://github.com/ant-research/PhysRVG)的49/15、8步示例是V2V强化学习训练，不是I2V推理推荐；五个静态条件帧不算完整视频编辑 |
| `cosmos3_nano`／Cosmos3-Nano | 189/24；7.833s | 35/6；flow_shift=10 | [官方I2V示例](https://huggingface.co/nvidia/Cosmos3-Nano) |
| `wan22_i2v_a14b`／Wan2.2-I2V-A14B | 81/16；5s | 40/(3.5,3.5)；shift=5 | [官方A14B配置](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/wan_i2v_A14B.py)及shared_config；高低噪声CFG分别登记 |
| `physalign_wan22_i2v_a14b`／社区PhysAlign转换适配器 | 81/16；5s | 40/(3.5,3.5)；shift=5 | 使用Wan基座配置；[PhysAlign项目](https://physalign.github.io/PhysAlign/)不自动认证本机社区转换权重，转换来源及LoRA合并需单独核验 |
| `minimax_h3`／MiniMax-H3 FL2VA | 124/24；5.125s | 本地runner 50步；CFG继承权重pipeline | [官方权重卡](https://huggingface.co/MiniMaxAI/MiniMax-H3)支持24fps，公开卡未规定该50步为统一推荐，不私造CFG数值 |

帧数包含条件帧，物理比较时长为 `(N-1)/fps`，不是容器时长 `N/fps`。采样数量无需全部相同，但评分时间范围必须相同。轨迹默认比较固定5s，并另报1s；短于5s的模型保留为该指标覆盖不足，不能变速或填充到5s。新参数只用于新运行目录，旧媒体、原失败与原记录不改写，也不与新时钟混合汇总。

画布仍是本benchmark的按宽高比设置，可用 `canvas` 显式登记；它不是所有权重的官方原生分辨率。Wan 5B官方介绍为720p，DynamiCrafter固定576×1024，其余变体的尺寸约束以对应API为准。画布、权重路径、模型环境和实际解码时钟均记录在运行产物中。不得把共同480p设置宣称为全部模型的官方最优质量设置。

## 真正的视频编辑

当前完整 V2V 编辑入口为 `model=ltx_i2v`、`conditioning_mode=v2v`，实际加载 `LTXConditionPipeline`，使用原非蒸馏LTX权重。生成环境需要提供该类及 `video`、`frame_index`、`strength`、`denoise_strength`、`frame_rate` 参数；缺少接口直接拒绝，不退回I2V或T2V。已核对 Diffusers 0.39.0 官方源码接口；SAM3.1环境不随之升级。可用 `scripts/setup_ltx_v2v_env.sh --python CUDA_BASE_PYTHON --env-dir NEW_ENV_DIR` 建立独立生成环境；脚本只安装生成适配器版本并核对CPU接口，不加载权重或启动GPU。site_a现有0.39.0环境的完整编辑接口已实际CPU导入验证，0.33.1缺少去噪参数并会在加载权重前拒绝。

额外配置：

```json
{"conditioning_mode":"v2v","v2v":{"manifest":"/absolute/path/video_inputs.jsonl","manifest_sha256":"SHA256_OF_MANIFEST","denoise_strength":0.6,"conditioning_strength":0.7}}
```

每行明确关联原item：

```json
{"item_id":"original_item_id","video":"/absolute/path/input.avi","video_sha256":"SHA256_OF_VIDEO","fps":25,"frames":161,"start_frame":0}
```

上述强度仅为配置示例，不是已调优推荐。`denoise_strength` 控制编辑噪声，`conditioning_strength` 控制视频条件约束，两者独立并必须显式登记在(0,1)。只读取声明的来源区间，按真实秒数重采样后把全部目标时刻的帧传入视频接口；不把一张图片重复成完整视频、不拉伸时间、不外推。源文件必须与目标参考不同，初始解码像素必须与冻结条件图一致，保证原初始框与几何仍适用；压缩导致无法一致的输入需准备有真实来源的无损初始帧，不能放宽检查掩盖不适用。缺源、源SHA漂移、时长不足、初始状态不符均保留原分母和原因。

I2V和V2V接收的信息不同，必须分组报告，不能把视频输入的结果与单图输入直接合并成同一比较。Cosmos的单帧前缀续写与PhysRVG的静态前缀保持独立标记；没有宣称12模型全部具备完整V2V。

## 环境与执行

模型始终从已有本地权重加载。`generation_runtime` 可登记 `python`、`gpu_devices`、`pythonpath`、`ffmpeg`；外部runner还需要 `code_dir`，VideoGPA/PhysRVG需要 `lora_dir`，PhysAlign另需 `physalign_hook_dir`。DynamiCrafter的 `model_dir` 是checkpoint文件。保留venv可执行路径，不解析成基础Python。

默认只输出计划；显式 `--execute` 才启动。已有输出、partial或claim不自动覆盖/重试。统一入口完整解码校验媒体、时钟和输入SHA，再执行冻结单视角SAM3.1与原反演。详见 [QUICKSTART.md](QUICKSTART.md)、[EVALUATION.md](EVALUATION.md)。此前LTX、CogVideoX、Wan、Hunyuan单条视频已产出；这些是旧时钟/旧参数的尝试，新采样版本和完整V2V尚未GPU实测，不冒充新版本验收。
