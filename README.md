# PhysProbe

物理视频生成与评测工具（原名 PhysEdit；PhysEdit 现指其中的 benchmark 与生成工具包 `physedit`），提供图像生成视频、视频编辑与未来帧预测、SAM3.1单视角跟踪、重力、动摩擦与初速度测量，以及视觉指标和Qwen视频判断。

| 测量指标 | 样本数 | 平均相对误差 | 最大相对误差 | 点估计覆盖率 |
| :---: | :---: | :---: | :---: | :---: |
| 重力 | 1038 | 2.700% | 15.148% | 100% |
| 动摩擦系数 | 880 | 0.235% | 1.974% | 75% |
| 初速度大小 | 1038 | 1.785% | 14.353% | 100% |

表中为单视角开发集结果。初速度相对误差统计1036个非零目标，2个零目标使用绝对误差。摩擦误差统计660个滑动样本，其余220个静止样本给出静摩擦下界。测量条件与基线比较见[性能评测](docs/phyediting/validation.md)。

```bash
python -m pip install -e .
physedit prepare-gravity100 /path/to/tasks.jsonl --model-config model.json --out gravity100.json
physedit plan gravity100.json
physedit run gravity100.json --execute
```

当前100条使用第0帧条件图与逐条时间范围，结果写入`runs/gravity100`。其他参数任务可分别选用动摩擦、初速度、V/P与Qwen评测，详见[快速上手](docs/phyediting/QUICKSTART.md)。

| 使用指南 | 参数测量 | 数据与部署 |
| :---: | :---: | :---: |
| [快速上手](docs/phyediting/QUICKSTART.md) | [SAM3.1跟踪](docs/phyediting/SAM31.md) | [100条重力评测](docs/phyediting/GRAVITY100.md) |
| [模型与权重](docs/phyediting/MODELS.md) | [物理参数测量](docs/phyediting/MOTION_PARAMETERS.md) | [多机调度](docs/PIPELINE.md) |
| [生成与评分](docs/phyediting/GENERATION.md) | [V/P与Qwen](docs/phyediting/EVALUATION.md) | [性能数据](docs/phyediting/latest_results.json) |

[评测清单CSV](docs/phyediting/gravity100.csv) · [数据集划分与训练来源](docs/joint_split_v3/PROTOCOL.md)

## 仿真反演评测（Core100）

`physprobe/inversion/`：用作者原始 Genesis 场景建立仿真库，结合 SAM 3.1 联合跟踪，按物理时间对齐，并做逐视频配准与相机运动补偿，对参考视频和生成视频统一反演 g、μ、v，给出点估计或经过校准的不确定区间。已知答案测试中，点估计误差中位数为 g 2.2%、μ 1.6%、v 1.2%。方法、验证与运行步骤见 [physprobe/inversion/README.md](physprobe/inversion/README.md)。数据、仿真库和结果不进 git，通过 `PHYSPROBE_WORK` / `PHYSPROBE_ROOT` 指定位置。

| 包 | 内容 |
| :---: | :--- |
| `physedit` | PhysEdit benchmark、视频生成与评分流程 |
| `gravtrace` | GravTrace 单视角重力测量（解析拟合） |
| `physprobe` | 仿真反演评测（g、μ、v） |

MIT · [LICENSE](LICENSE)
