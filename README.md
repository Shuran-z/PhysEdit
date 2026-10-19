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

## 临界边界与事件链评测

`python -m physedit boundary` 提供临界两侧样本登记、生成清单与评分；`python -m physedit boundary-evaluate` 接入独立质量筛查、逐事件判读和人工复核。生成失败保留在总分母里，事件与物理反演分别报告覆盖率。反演不适用不会排除事件评测样本；自动判读仍是待验证的预标注。

[执行指南](BOUNDARY_EVALUATION.md) · [完整协议与文档索引](docs/critical_boundary/README.md) · [研究脚本索引](scripts/README.md)

100条固定测量任务与临界族评测有不同的参考要求；临界距离、事件真值、完整配对和视频可观察性按样本核验，不能由100条成员资格自动推导。

MIT · [LICENSE](LICENSE)
