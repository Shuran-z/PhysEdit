# PhysEdit

PhysEdit用于物理视频生成与评测，提供I2V/V2V生成、SAM3.1单视角目标跟踪、重力与运动参数测量，以及V/P指标和Qwen视频评测。

| 测量指标 | 样本数 | 平均相对误差 | 最大相对误差 | 点估计覆盖率 |
|---|---:|---:|---:|---:|
| 重力 | 1038 | 2.700% | 15.148% | 100% |
| 初速度大小 | 1038 | 1.785% | 14.353% | 100% |
| 动摩擦系数 | 880 | 0.235% | 1.974% | 75% |

表中为单视角开发集结果；测量条件和基线比较见[性能评测](docs/phyediting/validation.md)。
初速度误差统计1036个非零目标，2个零目标使用绝对误差。摩擦误差统计T07的660个滑动样本，其余220个静止样本给出静摩擦下界。速度与摩擦使用独立测量命令。

```bash
python -m pip install -e '.[test]'
python -m physedit run phyediting --spec pipeline.json --run-dir runs/new_generation
```

默认只打印计划；配置与设备核对后，加`--execute`才实际运行。
[快速上手](docs/phyediting/QUICKSTART.md) · [12模型与参数](docs/phyediting/MODELS.md) · [生成与评分](docs/phyediting/GENERATION.md) · [V/P与Qwen](docs/phyediting/EVALUATION.md)
[SAM3.1跟踪](docs/phyediting/SAM31.md) · [速度与摩擦](docs/phyediting/MOTION_PARAMETERS.md) · [划分协议](docs/joint_split_v3/PROTOCOL.md) · [性能数据](docs/phyediting/latest_results.json) · [多机调度](docs/PIPELINE.md)
MIT — 见[LICENSE](LICENSE)。
