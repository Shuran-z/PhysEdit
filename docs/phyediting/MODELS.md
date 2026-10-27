# 模型与权重

12个生成模型使用相同配置格式。以下命令列出模型及其采样设置：

```bash
physedit models
physedit models --json
```

## 权重地址

| 模型 | 输入方式 | 权重与资源 |
| :---: | :---: | :---: |
| LTX-Video 2B | I2V / V2V | [Hugging Face](https://huggingface.co/Lightricks/LTX-Video) |
| LTX-Video 2B — PhyDataset SFT-LoRA (ZH) | I2V / V2V | [基础模型](https://huggingface.co/Lightricks/LTX-Video) · [中文 LoRA 权重](https://github.com/Shuran-z/PhysEdit/releases/download/ltx-video-2b-phydataset-zh-lora-v1/phydataset-zh-sft-lora-step188.safetensors) |
| LTX-Video 2B — PhyDataset SFT-LoRA (EN) | I2V / V2V | [基础模型](https://huggingface.co/Lightricks/LTX-Video) · [英文 LoRA 权重](https://github.com/Shuran-z/PhysEdit/releases/download/ltx-video-2b-phydataset-en-lora-v1/phydataset-en-sft-lora-step188.safetensors) |
| CogVideoX 1.5 | I2V | [Hugging Face](https://huggingface.co/zai-org/CogVideoX1.5-5B-I2V) |
| CogVideoX1.5-5B-I2V — PhyDataset LoRA (EN) | I2V | [基础模型](https://huggingface.co/zai-org/CogVideoX1.5-5B-I2V) · [英文 LoRA 权重](https://github.com/Shuran-z/PhysEdit/releases/download/cogvideox1.5-5b-i2v-phydataset-en-lora-v1/phydataset-cogvideox15-i2v-en-lora-step150.safetensors) |
| Wan 2.2 5B | I2V | [Diffusers权重](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers) |
| Wan2.2-TI2V-5B — PhyDataset SFT-LoRA (ZH) | I2V | [基础模型](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) · [中文 LoRA 权重](https://github.com/Shuran-z/PhysEdit/releases/download/wan2.2-ti2v-5b-phydataset-zh-lora-v1/phydataset-wan22-ti2v5b-zh-lora-750updates.safetensors) |
| Wan2.2-TI2V-5B — PhyDataset SFT-LoRA (EN) | I2V | [基础模型](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) · [英文 LoRA 权重](https://github.com/Shuran-z/PhysEdit/releases/download/wan2.2-ti2v-5b-phydataset-en-lora-v1/phydataset-wan22-ti2v5b-en-lora-700plus50.safetensors) |
| HunyuanVideo 1.5 | I2V | [480p步数蒸馏权重](https://huggingface.co/hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_i2v_step_distilled) |
| Cosmos-Predict2 | I2V / V2V未来帧预测 | [Hugging Face](https://huggingface.co/nvidia/Cosmos-Predict2-2B-Video2World) |
| DynamiCrafter | I2V | [1024权重](https://huggingface.co/Doubiiu/DynamiCrafter_1024) |
| VideoGPA | I2V | [Wan基座](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) · [官方LoRA](https://github.com/Hongyang-Du/VideoGPA/releases/tag/v1.0.0-weights) |
| PhysRVG | I2V（静态前缀） | [Hugging Face](https://huggingface.co/HappyP4nda/PhysRVG) |
| Cosmos3-Nano | I2V | [Hugging Face](https://huggingface.co/nvidia/Cosmos3-Nano) |
| Wan 2.2 A14B | I2V | [Hugging Face](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B) |
| PhysAlign社区适配 | I2V | [Wan基座](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B) · [项目](https://physalign.github.io/PhysAlign/) |
| MiniMax-H3 | I2V | [FL2VA权重](https://huggingface.co/MiniMaxAI/MiniMax-H3) |

LTX使用2B非蒸馏权重；Hunyuan使用480p I2V步数蒸馏权重；Cosmos-Predict2使用16fps变体。VideoGPA使用Wan 5B基座与TI2V LoRA。PhysAlign接口使用社区转换适配器，配置中提供其LoRA目录与合并脚本。

## 采样参数

| 配置键 | 帧数 | fps | 时长(s) | 步数 | CFG |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `ltx_i2v` | 161 | 25 | 6.400 | 50 | 3 |
| `cogvideox_i2v` | 81 | 16 | 5.000 | 50 | 6 |
| `wan_ti2v5b` | 121 | 24 | 5.000 | 50 | 5 |
| `hunyuan15_i2v` | 121 | 24 | 5.000 | 12 | 1 |
| `cosmos` | 81 | 16 | 5.000 | 由运行配置提供 | 7 |
| `dynamicrafter_i2v` | 16 | 10 | 1.500 | 50 | 7.5 |
| `videogpa_ti2v5b` | 81 | 24 | 3.333 | 50 | 5 |
| `physrvg_ti2v5b` | 49 | 15 | 3.200 | 16 | 5（CFG关闭） |
| `cosmos3_nano` | 189 | 24 | 7.833 | 35 | 6 |
| `wan22_i2v_a14b` | 81 | 16 | 5.000 | 40 | 3.5 / 3.5 |
| `physalign_wan22_i2v_a14b` | 81 | 16 | 5.000 | 40 | 3.5 / 3.5 |
| `minimax_h3` | 124 | 24 | 5.125 | 50 | 模型默认值 |

时长为首帧到末帧的`(N−1)/fps`，帧数包含条件帧。生成长度由各模型配置决定，评测使用统一的真实时间范围：轨迹比较5s，短窗口1s。短于完整窗口的视频按该指标的实际覆盖情况报告。

<details>
<summary>其他参数与推荐来源</summary>

- **LTX**：`frame_rate=25`，50步/CFG 3来自[Diffusers接口默认值](https://github.com/huggingface/diffusers/blob/v0.39.0/src/diffusers/pipelines/ltx/pipeline_ltx_condition.py)。
- **CogVideoX**：81帧、16fps、50步/CFG 6对应[官方I2V规格](https://github.com/zai-org/CogVideo)。
- **Wan 5B**：`flow_shift=5`，采样设置见[官方配置](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/wan_ti2v_5B.py)。
- **Hunyuan**：步数蒸馏变体使用12步、CFG 1、shift 7，见[变体推荐](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5#inference-configurations)。
- **Cosmos-Predict2**：CFG 7；步数由外部Video2World调用器提供，随运行设置记录，见[官方示例](https://github.com/nvidia-cosmos/cosmos-predict2/blob/main/examples/video2world.py)。
- **DynamiCrafter**：FS 10、eta 1、rescale 0.7、trailing时刻表，见[1024推理脚本](https://github.com/Doubiiu/DynamiCrafter/blob/main/scripts/run.sh)。导出使用10fps，同步保留原8fps文件。
- **VideoGPA**：LoRA强度0.2、shift 5，见[官方推理脚本](https://github.com/Hongyang-Du/VideoGPA/blob/main/generate/Wan2.2-TI2V-5B.py)。
- **PhysRVG**：I2V适配采用16步、CFG开关关闭、五帧静态条件前缀；[原项目](https://github.com/ant-research/PhysRVG)另提供V2V/RL设置。
- **Cosmos3**：35步、CFG 6、flow shift 10，见[模型卡](https://huggingface.co/nvidia/Cosmos3-Nano)。
- **Wan A14B / PhysAlign**：高、低噪声专家分别使用CFG 3.5，shift 5，见[Wan配置](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/wan_i2v_A14B.py)。
- **MiniMax-H3**：调用器采用50步，CFG由FL2VA pipeline提供，见[模型卡](https://huggingface.co/MiniMaxAI/MiniMax-H3)。

画布按源视频宽高比配置，并受模型的尺寸约束限制。参数、画布、权重和依赖版本保存到运行目录。

</details>

## 视频编辑

视频编辑使用LTX的`LTXConditionPipeline`与Diffusers 0.39.0。复制[视频编辑示例](../../examples/phyediting/pipeline.ltx-v2v.example.json)，填写输入视频清单：

```json
{
  "conditioning_mode": "v2v",
  "v2v": {
    "manifest": "/path/to/video_inputs.jsonl",
    "manifest_sha256": "SHA256_OF_MANIFEST",
    "denoise_strength": 0.6,
    "conditioning_strength": 0.7
  }
}
```

`denoise_strength`控制编辑噪声，`conditioning_strength`控制视频条件约束。视频清单提供`item_id/video/video_sha256/fps/frames/start_frame`。输入按真实时间重采样，初始帧与条件图一致。结果按图像条件、视频编辑和静态前缀续写分别汇总。

## Cosmos未来帧预测

Cosmos-Predict2的Video2World支持1帧图像条件或5帧视频条件，见[官方接口](https://github.com/nvidia-cosmos/cosmos-predict2/blob/main/examples/video2world.py)和[历史帧读取实现](https://github.com/nvidia-cosmos/cosmos-predict2/blob/main/cosmos_predict2/pipelines/video2world.py)。视频条件用于延续运动，LTX的V2V用于编辑已有视频。

复制[Cosmos续写配置](../../examples/phyediting/pipeline.cosmos-future.example.json)，填写权重、Video2World调用器目录及[历史视频清单](../../examples/phyediting/future.example.jsonl)：

```json
"model": "cosmos",
"conditioning_mode": "v2v_future",
"future": {
  "manifest": "/path/to/history_inputs.jsonl",
  "manifest_sha256": "SHA256_OF_HISTORY_MANIFEST"
}
```

清单提供`item_id/video/video_sha256/fps/frames/end_frame`，`end_frame`与条件图对应同一时刻、同一画面。程序从该时刻向前按16fps选5个真实观测，记录原帧号与采样时间差，并制作仅含这5帧的无损条件视频。历史不足、源文件变动和条件画面不一致均逐例保留原因。

原生输出为81帧、16fps，包含5帧条件与76帧预测。原始视频保留；评测副本删去前4帧历史，以末个条件帧为时间零点，共77帧、4.75s。参数测量、V/P和Qwen使用这一副本；条件帧SSIM/PSNR与未来帧质量分别统计。默认5s轨迹项会记录窗口不足，跨模型运行前可统一选4s窗口，视频保持原生16fps。

单帧路径继续兼容原配置中的`v2v_one_condition_frame`。Cosmos3-Nano目前使用I2V路径。三种输入方式分别记录，不混作同一种实验条件。

## 配置环境

重力、动摩擦、初速度、V/P与Qwen由公共评测流程调度，12个生成模型使用相同配置项。各参数按所需观测与场景条件分别判断适用性。

生成权重通过`model_dir`指定。`generation_runtime`填写生成Python、GPU和FFmpeg；外部实现增加`code_dir`，LoRA模型增加`lora_dir`，PhysAlign增加`physalign_hook_dir`。DynamiCrafter的`model_dir`填写checkpoint文件。

```bash
physedit plan pipeline.json
physedit run pipeline.json --execute
```

## 跟踪与视频评测模型

| 用途 | 模型 | Hugging Face |
| :---: | :---: | :---: |
| 目标跟踪 | SAM3.1 | [权重](https://huggingface.co/facebook/sam3.1) |
| 视频判断 | Qwen3.5-9B | [权重](https://huggingface.co/Qwen/Qwen3.5-9B) |
| 视频判断 | Qwen3.5-27B | [权重](https://huggingface.co/Qwen/Qwen3.5-27B) |

Qwen通过本地权重或视频API配置，操作见[评测指南](../internal/phyediting/EVALUATION.md#qwen视频判断)。SAM3.1的依赖见[跟踪指南](../internal/phyediting/SAM31.md)。
