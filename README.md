# PhysEdit

物理视频生成与评测工具，提供图像生成视频、视频编辑与未来帧预测、SAM3.1单视角跟踪、重力、动摩擦与初速度测量，以及视觉指标和Qwen视频判断。

## PhysProbe：Core100 物理参数反演评测（正式评测）

生成视频的正式评测由 [`physprobe/`](physprobe/inversion/README.md) 完成：对 Core100 的每条视频（参考视频或以第 5 帧为条件生成的视频），把 SAM 3.1 跟踪到的物体运动和作者原始 Genesis 场景在不同参数下的仿真逐帧比较，分别测出重力 g、主接触面摩擦 μ 和初速度 v，并给出校准过的不确定带。

| 文档 | 内容 |
| :---: | :---: |
| [验收报告](docs/physprobe/ACCEPTANCE_CORE100.md) | 方法、已知答案测试（参考视频与合成视频）、合理性证据、12 个模型的结果 |
| [评测指标](docs/physprobe/METRICS.md) | 通用指标（轨迹 ADE/FDE、Physics-IQ 运动一致、视频 PSNR/SSIM、相机漂移）与本基准独有的指标（物理可解释率、反演误差、参数响应） |
| [运行手册](physprobe/inversion/README.md) | 仿真库、SAM 跟踪、评测、真值验证门、指标总表的命令 |

仓库结构：`physedit/` 生成流水线与临界边界评测，`physprobe/` 物理参数反演评测，`gravtrace/` 早期重力反演模块（被 `physedit` 的旧评测阶段使用），`scripts/` 研究与渲染脚本（含与其他方法的对比：2D/深度提升基线 `baselines.py`、单目/多视深度模型 `depth_probe.py`（DepthPro、Depth Anything V2、ZoeDepth、MoGe-2、UniDepthV2、VGGT）、相同观测帧对比 `phyediting_common_*`、未知初速对比 `phyediting_unknown_*`、`phyediting_bounded_*`、VGGT 公共帧 `phyediting_vggt_common_*`、SAM2 跟踪 `track_sam2.py`；结果见 [docs/archive/GRAVTRACE_REFERENCE_PREINTEGRATION.md](docs/archive/GRAVTRACE_REFERENCE_PREINTEGRATION.md)），`docs/` 文档。

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
