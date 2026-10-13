# 初速度与摩擦测量

速度与摩擦通过独立入口测量，沿用SAM3.1单视角观测。最新误差和覆盖率见[项目性能](validation.md)；默认生成评测使用GravTrace重力方法。

## 速度及参考时刻

```bash
python scripts/phyediting_motion_parameters.py velocity \
  runs/benchmark_gravity_v1/items.jsonl frozen_predictions.jsonl velocity_result.json
```

该命令将已有重力输出中的`speed/angle/azimuth`转换为世界坐标系速度向量。评分目标为同一物体在声明初始状态时刻的线速度，分别计算模长相对误差、向量相对误差和绝对误差（m/s）。零目标按绝对误差报告，仍计入覆盖率分母。

## 运动模型与测量入口

| 命令 | 使用条件 | 测量方式 |
|---|---|---|
| `kinematic-velocity` | 来源明确声明运动平面 | 在平面内拟合速度与轨迹曲率 |
| `coverage-velocity` | 登记初始状态及真实观察时钟 | 使用平面分支，或尝试无平面约束三维拟合 |
| `can-pixel-velocity` | 已登记罐体和充分采样的圆形立体几何 | 掩膜矩、相邻帧光流与轮廓一致性 |
| `book-pixel-velocity` | 已登记可视书本几何，至少8个原观察帧 | 可见轮廓矩、材料点光流与遮挡处理 |

```bash
python scripts/phyediting_motion_parameters.py kinematic-velocity registered_inputs.jsonl result.json
python scripts/phyediting_motion_parameters.py coverage-velocity registered_inputs.jsonl result.json
python scripts/phyediting_motion_parameters.py can-pixel-velocity registered_pixel_inputs.jsonl result.json
python scripts/phyediting_motion_parameters.py book-pixel-velocity registered_pixel_inputs.jsonl result.json
```

每行包括`id`、`sample`、`saved_gravity_prediction`、评分用`target_v0`和`plane_registration={"path":"/absolute/path/planes.json","sha256":"..."}`。来源登记绑定样本SHA、header/state文件及SHA、物体身份、初始状态帧和观察帧。参考速度在拟合完成后才用于评分。

平面方向来自声明的驱动方向，仅使用方向信息；多个声明方向须平行。来源位置用于核验2mm平面范围，拟合使用像素观测和初始几何。平面入口要求保存的时间偏移为零。三维入口通过`source_initial_frame`保留声明初始时刻，观察首帧可晚于该时刻；缺帧按真实时间间隔处理，并报告`source_observation_gap_count`。

速度轨迹单独拟合曲率，保存的重力用于初始化。平面分支采用0.25s时间权重与MAD稳健尺度（下限0.5px），三维分支采用固定1px尺度。曲率作为速度测量的辅助参数输出，辅助曲率与重力测量结果分别保存。

### 像素与几何登记

像素分支增加`pixel_registration={"path":"/absolute/path/pixels.json","sha256":"..."}`。登记行包含`id`、`sample_sha256`、`cache_path`、`cache_sha256`、`frames`；每帧包含`frame`、`bgr_sha256`、`mask_path`、`mask_file_sha256`。`rgb_<frame>`缓存保存BGR数组，像素SHA与压缩掩膜文件SHA分别校验。每条测量使用一个机位的原观察帧和秒数。

罐体资产为`can`或以`can_`、`beverage_can_`开头，几何需提供充分采样的圆形立体轮廓。拟合联合使用掩膜质心、二阶矩及相邻帧RGB光流。原掩膜轮廓的3px一致性检查决定是否采用光流结果，或继续尝试完整轮廓拟合；所有尝试分别输出。

书本资产为`book_thick_01_v2`或`book_textbook_01_v2`，至少24个立体可视几何点，尺寸与来源声明匹配；8角点碰撞代理和不足8帧的窗口单列不适用原因。每帧通过`window.edges_visible`标注可见边界。投影按画面范围和遮挡边界截断，半开`xyxy`的像素单元右、下界分别为`right-0.5`、`bottom-0.5`。

书本形状矩取原掩膜非零像素单元支撑的凸包，以减小封面掩膜缺口的影响。光流与一致性仍使用原掩膜；材料点检查下一帧表面可见性，并以预测可见范围中心校准。形状矩、光流和重力测量分别保存，便于比较各项观测。

模型由预先登记的来源和几何确定。像素分支结果另存，拟合失败或不适用时保留原估计；汇总列出各分支的点值数量和失败数量。速度大小和三维向量误差分别报告。

## 动摩擦

```bash
python scripts/phyediting_motion_parameters.py friction registered_friction_inputs.jsonl friction_result.json
```

每行包括`id`、`measurement`及评分目标`target_effective_friction`。测量输入为单视角`boxes_xyxy`、`times_s`、相机与图像尺寸、初始位置、轮廓点、下坡方向、坡角、已知重力及线性阻尼（1/s）。目标有效摩擦系数只用于评分。

纯滑动段采用`dv/dt = g(sin(theta) - mu*cos(theta)) - drag*v`，通过相机投影同时拟合窗口起点速度与有效动摩擦系数，支持水平面。`evidence`绑定时钟、物体身份、单支撑面、无外力和稳定姿态；窗口范围覆盖连续滑动片段。估计方法参见[WorldBench](https://arxiv.org/html/2601.21282v2)。

接触副有效系数结合几何属性、接触组合规则及滑动接触力证据登记。材质声明值通过`declared_material_friction`另报诊断。静止片段可输出`static_friction_bound`，斜面下界为`tan(theta)`，状态为`unidentifiable`、`friction=null`。

`information_coverage`分别统计动摩擦点值、静摩擦下界和未解析样本；`summary.coverage_rate`只计算动摩擦点值，`point_or_bound_rate`计算点值或下界的信息覆盖。停车、反向、碰撞、滚动、转动和离开支撑面的片段保留各自的不适用原因。

## 结果与可视化

每份结果使用完整登记分母，报告有效数量、误差、覆盖率和状态原因；不可评分项以`null`记录，并附状态原因。来源或输入SHA漂移返回输入失败，相机或有效接触系数待核验时返回`review_required`。原结果与新尝试分开保存。

可视化并列原视频、观测框、拟合投影和轨迹残差，绑定视频SHA与帧号。模拟器轨迹用于模型诊断和评分，像素观测用于拟合。开发集性能、生成视频参数偏差和独立测试结果分别汇总。
