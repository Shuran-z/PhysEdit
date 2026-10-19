# SAM3.1目标跟踪

SAM3.1从单视角视频中跟踪指定物体，输出逐帧掩膜和图像边界。参数测量使用这些像素观测；每条任务对应一个视频中的一个目标。

## 模型与环境

准备[官方SAM源码](https://github.com/facebookresearch/sam3)与[SAM3.1权重](https://huggingface.co/facebook/sam3.1)，安装方式见[快速上手](QUICKSTART.md#安装)。

环境激活脚本提供`PHYEDIT_SAM3_SOURCE`和`PHYEDIT_SAM31_CHECKPOINT`。单独运行跟踪命令时使用同一环境。

## 准备与运行

每行输入提供视频、目标、观察帧和初始场景框：

```json
{
  "id": "case01",
  "video": "/path/to/case01.mp4",
  "video_sha256": "SHA256_OF_VIDEO",
  "fps": 30,
  "prompt_frame": 0,
  "frames": [24, 25, 26, 27],
  "target_name": "book_right",
  "scene_boxes": {"book_right": [100, 80, 180, 160]}
}
```

```bash
physedit track prepare jobs.jsonl runs/tracking
physedit track run runs/tracking \
  --sam3 "$PHYEDIT_SAM3_SOURCE" \
  --checkpoint "$PHYEDIT_SAM31_CHECKPOINT"
```

`prepare`检查输入，`run`执行目标跟踪。提示点根据初始场景框建立，输出保留原帧号、时钟和对象身份。缺失观测以`null`及原因记录。

## 输出

| 文件 | 内容 |
| :---: | :---: |
| `tracks_v4.jsonl` | 目标边界与逐帧跟踪状态 |
| `measurements_v4.jsonl` | 边界测量与像素记录 |
| `prepared.json` | 输入任务与文件信息 |
| `completed.json`、`failure.json` | 完成状态与异常原因 |

文件关联视频SHA、模型版本和实际观测范围。生成流水线自动准备跟踪任务，再执行所选参数评测；摩擦窗口超出已有轨迹时，按预先指定的帧表补充跟踪，操作见[快速上手](QUICKSTART.md)。测量误差见[性能评测](validation.md)。

<details>
<summary>依赖版本与边界测量</summary>

依赖清单为[`manifest.json`](../../scripts/sam31_frozen/manifest.json)，包含官方源码commit、checkpoint revision及跟踪、相机和拟合文件SHA。

- 官方源码：`0570b3a5be9c4e694f23d85232fb55f4a6f1f7fc`
- checkpoint revision：`daa63191845a41281374e725f4c9e51c7a824460`
- checkpoint SHA256：`0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`

运行前检查上述文件及10份跟踪源码。图像边界使用`gravtrace.observations.refine_box`；四条边界的像素位置未通过检查时采用整数像素框。输入帧表与视频实际帧率共同确定观察时钟。

</details>
