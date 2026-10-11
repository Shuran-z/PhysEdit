# 重力、动摩擦与初速度测量

三类参数使用SAM3.1提供的单视角观测，在一键生成评测中分别计算误差、覆盖率与失败原因。开发集结果见[项目性能](validation.md)。

| 参数 | 观测与已知条件 | 输出 |
| :---: | :---: | :---: |
| 重力 | 自由飞行或适用坡面片段、相机、几何、时钟 | 重力大小（m/s²） |
| 动摩擦 | 稳定纯滑动、已知重力、坡面与阻尼 | 有效动摩擦系数 |
| 初速度 | 自由飞行或滑动、相机、几何、参考时刻 | 速度大小与三维向量（m/s） |

## 重力

一键流程以目标轮廓的投影位移拟合重力，初速度等辅助参数在给定范围内估计。单独处理已有观测：

```bash
physedit measure gravity samples.jsonl -o predictions.jsonl
gravtrace score samples.jsonl predictions.jsonl -o summary.json
```

相机、真实尺度、初始姿态、角运动和阻尼由输入给定。目标重力仅用于拟合后的评分，方法与输入格式见[测量参考](../REFERENCE.md)。


## 动摩擦

```bash
physedit measure friction registered_friction_inputs.jsonl friction_result.json
```

每行包括`id`、`measurement`及评分目标`target_effective_friction`。测量输入为单视角`boxes_xyxy`、`times_s`、相机与图像尺寸、初始位置、轮廓点、下坡方向、坡角、已知重力及线性阻尼（1/s）。目标有效摩擦系数只用于评分。`world_corners`提供相对物体参考点、已按初始姿态转到世界方向的轮廓偏移，`initial_position`单独提供参考点位置。

纯滑动段采用`dv/dt = g(sin(theta) - mu*cos(theta)) - drag*v`，通过相机投影同时拟合窗口起点速度与有效动摩擦系数，支持水平面。`initial_time_s`可指定已知初始状态的时刻；首个观测晚于该时刻时保留真实时间差，缺省值为首观测时刻。`evidence`绑定时钟、物体身份、单支撑面、无外力和稳定姿态；窗口范围覆盖连续滑动片段。估计方法参见[WorldBench](https://arxiv.org/html/2601.21282v2)。

评分使用接触组合规则和滑动接触力所对应的有效摩擦系数。材料属性值通过`declared_material_friction`单独记录。静止片段可输出`static_friction_bound`，斜面下界为`tan(theta)`，状态为`unidentifiable`、`friction=null`。

`information_coverage`分别统计动摩擦点值、静摩擦下界和未解析样本；`summary.coverage_rate`只计算动摩擦点值，`point_or_bound_rate`计算点值或下界的信息覆盖。停车、反向、碰撞、滚动、转动和离开支撑面的片段保留各自的不适用原因。

## 初速度

### 读取已有速度估计

```bash
physedit measure velocity \
  items.jsonl predictions.jsonl velocity_result.json
```

该命令将已有拟合输出中的`speed/angle/azimuth`转换为世界坐标系速度向量并评分。评分目标是物体在给定初始时刻的线速度，报告模长误差、向量误差和绝对误差（m/s）。零目标使用绝对误差，并计入覆盖率。

### 从轨迹估计初速度

| 命令 | 使用条件 | 测量方式 |
| :---: | :---: | :---: |
| `kinematic-velocity` | 场景已知运动平面 | 在平面内拟合速度与轨迹曲率 |
| `coverage-velocity` | 已知初始状态与采样时间 | 使用平面分支，或尝试无平面约束三维拟合 |
| `can-pixel-velocity` | 已知罐体几何，轮廓充分采样 | 掩膜矩、相邻帧光流与轮廓一致性 |
| `book-pixel-velocity` | 已知书本可视几何，至少8个观察帧 | 可见轮廓矩、材料点光流与遮挡处理 |

```bash
physedit measure coverage-velocity inputs.jsonl velocity_result.json
```

选择表中的命令时，输入需满足对应的运动与几何条件。每行包括`id`、`sample`、`saved_gravity_prediction`、评分用`target_v0`和`plane_registration={"path":"/absolute/path/planes.json","sha256":"..."}`。输入记录样本及状态文件SHA、物体身份、初始状态帧和观察帧。参考速度在拟合完成后才用于评分。

运动平面由场景给定的驱动方向确定，多个方向须平行。来源位置用于核验2mm平面范围，拟合使用像素观测和初始几何。平面模型要求初始时间偏移为零。三维模型通过`source_initial_frame`记录初始时刻，观察首帧可晚于该时刻；缺帧按真实时间间隔处理，并报告`source_observation_gap_count`。

初速度拟合同时估计轨迹曲率，已有重力估计用于初始化。平面分支采用0.25s时间权重与MAD稳健尺度（下限0.5px），三维分支采用固定1px尺度。曲率作为辅助参数保存，原重力估计保持原值。

<details>
<summary>像素与几何输入格式</summary>

像素分支增加`pixel_registration={"path":"/absolute/path/pixels.json","sha256":"..."}`。输入行包含`id`、`sample_sha256`、`cache_path`、`cache_sha256`、`frames`；每帧包含`frame`、`bgr_sha256`、`mask_path`、`mask_file_sha256`。`rgb_<frame>`缓存保存BGR数组，像素SHA与压缩掩膜文件SHA分别校验。每条测量使用一个机位的原观察帧和秒数。

罐体资产为`can`或以`can_`、`beverage_can_`开头，几何需提供充分采样的圆形立体轮廓。拟合联合使用掩膜质心、二阶矩及相邻帧RGB光流。原掩膜轮廓的3px一致性检查决定是否采用光流结果，或继续尝试完整轮廓拟合；所有尝试分别输出。

书本资产为`book_thick_01_v2`或`book_textbook_01_v2`，至少24个立体可视几何点，尺寸与场景描述匹配；8角点碰撞代理和不足8帧的窗口单列不适用原因。每帧通过`window.edges_visible`标注可见边界。投影按画面范围和遮挡边界截断，半开`xyxy`的像素单元右、下界分别为`right-0.5`、`bottom-0.5`。

书本形状矩取原掩膜非零像素单元支撑的凸包，以减小封面掩膜缺口的影响。光流与一致性仍使用原掩膜；材料点检查下一帧表面可见性，并以预测可见范围中心校准。形状矩、光流和重力测量分别保存，便于比较各项观测。

模型根据输入的场景条件和几何确定。像素分支结果另存，拟合失败或不适用时保留原估计；汇总列出各分支的点值数量和失败数量。速度大小和三维向量误差分别报告。

</details>

## 结果与可视化

结果报告有效样本数、误差、覆盖率和逐例状态。全部输入ID计入分母，不可评分项记录为`null`并附原因。来源或输入SHA漂移返回输入失败，相机或有效接触系数待核验时返回`review_required`。原结果与新尝试分开保存。

检查测量结果时，可并列绘制原视频、观测框、拟合投影与轨迹残差，并标注视频SHA和帧号。测量命令输出数值JSON，图像需另行绘制。模拟器轨迹用于诊断与评分，像素观测用于拟合。
