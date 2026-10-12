# PhysEdit-GravTrace

使用 **SAM3.1** 跟踪和声明的相机、物体几何，从单视角视频联合估计重力与未知初速度。当前验证数据为 **PhyEditing**。

| 冻结方案（30 fps） | 平均误差 | 最大误差 | 失败率 |
|---|---:|---:|---:|
| GravTrace + SAM3.1 亚像素边界 | **2.700%** | **15.148%** | **0%** |
| 同信息、同观测帧的2D对照 | 5.294% | 36.364% | 0% |

全部 **1038例、13918帧**保留，覆盖率100%，拟合器保持不变。2D及DepthPro、DA-V2 Metric、ZoeDepth、MoGe-2、UniDepthV2、VGGT均已完成公平对比；[完整结果与逐例记录](docs/phyediting/validation.md#frozen-comparison)包含全部失败及分组统计。这是开发集结果，不代表独立泛化或全局最优。

```bash
pip install -e .[test]
python -m gravtrace fit samples.jsonl -o predictions.jsonl --workers 8
python -m gravtrace score samples.jsonl predictions.jsonl -o summary.json
```

- [方法与输入格式](docs/REFERENCE.md) · [冻结SAM3.1前端与运行入口](docs/phyediting/SAM31.md)
- [验证协议与结果](docs/phyediting/validation.md)
- [视频生成流水线与固定评分协议](docs/phyediting/GENERATION.md)

MIT — 见 [LICENSE](LICENSE)。
