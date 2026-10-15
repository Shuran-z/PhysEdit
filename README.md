# PhysEdit

物理视频生成与评测工具，提供图像生成视频、视频编辑与未来帧预测、SAM3.1单视角跟踪、重力、动摩擦与初速度测量，以及视觉指标和Qwen视频判断。

| 测量指标 | 样本数 | 平均相对误差 | 最大相对误差 | 点估计覆盖率 |
| :---: | :---: | :---: | :---: | :---: |
| 重力 | 1038 | 2.700% | 15.148% | 100% |
| 动摩擦系数 | 880 | 0.235% | 1.974% | 75% |
| 初速度大小 | 1038 | 1.785% | 14.353% | 100% |

表中为单视角开发集结果。初速度相对误差统计1036个非零目标，2个零目标使用绝对误差。摩擦误差统计660个滑动样本，其余220个静止样本给出静摩擦下界。测量条件与基线比较见[性能评测](docs/phyediting/validation.md)。

```bash
python -m pip install -e .
physedit plan pipeline.json
physedit run pipeline.json --execute
```

配置文件集中填写路径和评测选项。一键流程执行生成与跟踪，并按配置评测重力、动摩擦、初速度、V/P与Qwen。结果默认写入`runs/pipeline`，详见[快速上手](docs/phyediting/QUICKSTART.md)。

| 使用指南 | 参数测量 | 数据与部署 |
| :---: | :---: | :---: |
| [快速上手](docs/phyediting/QUICKSTART.md) | [SAM3.1跟踪](docs/phyediting/SAM31.md) | [划分协议](docs/joint_split_v3/PROTOCOL.md) |
| [模型与权重](docs/phyediting/MODELS.md) | [物理参数测量](docs/phyediting/MOTION_PARAMETERS.md) | [多机调度](docs/PIPELINE.md) |
| [生成与评分](docs/phyediting/GENERATION.md) | [V/P与Qwen](docs/phyediting/EVALUATION.md) | [性能数据](docs/phyediting/latest_results.json) |

MIT · [LICENSE](LICENSE)
