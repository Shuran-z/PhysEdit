# 模型与权重

12个生成模型共用配置入口。选择模型后，程序读取相应帧数、帧率和采样设置：

```bash
physedit models
physedit models --json
```

## 权重地址

| 模型 | 输入方式 | 权重与资源 |
| :---: | :---: | :---: |
| LTX-Video 2B | I2V / V2V | [Hugging Face](https://huggingface.co/Lightricks/LTX-Video) |
| CogVideoX 1.5 | I2V | [Hugging Face](https://huggingface.co/zai-org/CogVideoX1.5-5B-I2V) |
| Wan 2.2 5B | I2V | [Diffusers权重](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers) |
| HunyuanVideo 1.5 | I2V | [480p步数蒸馏权重](https://huggingface.co/hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_i2v_step_distilled) |
| Cosmos-Predict2 | 单帧续写 | [Hugging Face](https://huggingface.co/nvidia/Cosmos-Predict2-2B-Video2World) |
| DynamiCrafter | I2V | [1024权重](https://huggingface.co/Doubiiu/DynamiCrafter_1024) |
| VideoGPA | I2V | [Wan基座](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) · [官方LoRA](https://github.com/Hongyang-Du/VideoGPA/releases/tag/v1.0.0-weights) |
| PhysRVG | 静态前缀 | [Hugging Face](https://huggingface.co/HappyP4nda/PhysRVG) |
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
| `cosmos` | 81 | 16 | 5.000 | 继承调用器 | 7 |
| `dynamicrafter_i2v` | 16 | 10 | 1.500 | 50 | 7.5 |
| `videogpa_ti2v5b` | 81 | 24 | 3.333 | 50 | 5 |
| `physrvg_ti2v5b` | 49 | 15 | 3.200 | 16 | 5（CFG关闭） |
| `cosmos3_nano` | 189 | 24 | 7.833 | 35 | 6 |
| `wan22_i2v_a14b` | 81 | 16 | 5.000 | 40 | 3.5 / 3.5 |
| `physalign_wan22_i2v_a14b` | 81 | 16 | 5.000 | 40 | 3.5 / 3.5 |
| `minimax_h3` | 124 | 24 | 5.125 | 50 | 继承权重 |

时长为首帧到末帧的`(N−1)/fps`，帧数包含条件帧。生成长度由各模型配置决定，评测使用统一的真实时间范围：完整轨迹5s，短窗口1s。短于完整窗口的视频按该指标的实际覆盖情况报告。

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

完整V2V使用LTX的`LTXConditionPipeline`与Diffusers 0.39.0。复制[视频编辑示例](../../examples/phyediting/pipeline.ltx-v2v.example.json)，填写输入视频清单：

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

`denoise_strength`控制编辑噪声，`conditioning_strength`控制视频条件约束。视频清单提供`item_id/video/video_sha256/fps/frames/start_frame`。输入按真实时间重采样，初始帧与条件图一致。I2V、完整V2V和静态前缀续写分别汇总。

## 配置环境

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

Qwen通过本地权重或视频API配置，操作见[评测指南](EVALUATION.md#qwen视频判断)。SAM3.1的依赖见[跟踪指南](SAM31.md)。
