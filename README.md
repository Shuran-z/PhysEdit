# PhysEdit-GravTrace

PhyEditing 视频生成与重力评测流水线：**I2V/V2V 生成 → 单视角 SAM3.1 跟踪 → 冻结 V4 重力反演＋V/P＋Qwen → 全部注册样本汇总**。GravTrace 使用声明的相机和物体几何联合估计重力与未知初速度。

| 冻结方案（30 fps） | 平均误差 | 最大误差 | 失败率 |
|---|---:|---:|---:|
| GravTrace + SAM3.1 亚像素边界 | **2.700%** | **15.148%** | **0%** |
| 同信息、同观测帧的2D对照 | 5.294% | 36.364% | 0% |

以上为 **1038例、13918帧**开发集结果，覆盖率100%；[完整公平对比与逐例记录](docs/phyediting/validation.md#frozen-comparison)保留全部失败。一键入口已接入 GravTrace、V/P 和 Qwen完整视频评测（本地/视频API），输入须绑定原核验清单与冻结参考记录，拒绝不适用窗口。LTX 单条完整链路已实测，原反演 `at_bound`、Qwen 证据不足均保留。12模型参数与原生时钟已登记；LTX完整V2V接入视频条件接口，CPU调用与媒体验证不等于GPU验收。正式 ID/OOD 尚未评测。

```bash
python -m pip install -e '.[test]'
python -m physedit run phyediting --spec pipeline.json --run-dir runs/new_generation
# 默认只打印计划；配置与设备核对后，加 --execute 才生成、跟踪和评分。
```

- [快速上手：环境、输入、执行和结果](docs/phyediting/QUICKSTART.md) · [12模型配置与实测状态](docs/phyediting/MODELS.md)
- [固定评分方法与失败口径](docs/phyediting/GENERATION.md) · [冻结SAM3.1](docs/phyediting/SAM31.md) · [评测指标：真实时间 RGB PSNR/SSIM、V/P、Qwen](docs/phyediting/EVALUATION.md)
- [整体benchmark与划分](docs/joint_split_v3/PROTOCOL.md) · [开发集验证](docs/phyediting/validation.md) · [旧public211调度](docs/PIPELINE.md)

MIT — 见 [LICENSE](LICENSE)。
