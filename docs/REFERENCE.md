# 单视角物理参数测量

PhysEdit从单视角目标观测中测量重力、初速度和动摩擦系数。SAM3.1提供目标掩膜和图像边界，解析运动模型预测三维轨迹，再用相机参数投影到图像平面，与目标观测拟合。各参数的输入条件和开发集误差见[性能评测](phyediting/validation.md)。

GravTrace是项目中的重力测量模块，适用于自由落体、抛体和斜面运动。初速度与摩擦可随生成视频自动评测，也可使用[单独测量命令](phyediting/MOTION_PARAMETERS.md)。生成与评测的使用方法见[快速上手](phyediting/QUICKSTART.md)。

## 重力测量方法

1. 将每帧的目标掩膜转换为图像边界框。
2. 根据初始几何、位姿、角运动和运动模型，计算物体轮廓的三维轨迹，并通过相机投影预测图像边界。运动模型包括带线性阻尼的自由飞行，以及斜面上的滑动、滚动和离坡飞行。
3. 计算预测边界与观测边界相对锚帧的位移残差。固定的几何或掩膜偏移由相对位移消除，图像边界裁切及标注遮挡的边缘单独处理。
4. 使用soft-L1稳健损失进行有界最小二乘拟合。重力采用对数参数化，未知初速度和时间偏移等辅助参数在给定范围内同时拟合；离散坡面假设按拟合代价比较。

物体旋转根据初始角速度、惯量和角阻尼，通过刚体Euler方程计算。重力拟合使用预先确定的观察窗口；生成评测的窗口与帧数规则见[生成评分方法](phyediting/GENERATION.md)。

`fit`命令可检查首次接触：预测轨迹越过地面，或后续观测偏离此前拟合超过`max(3 px, 3 × median error)`时结束解析轨迹。固定窗口评测使用`window.contact_check=false`，输入指定连续适用片段。

默认`offset_mode=anchor`使用锚帧位移；`offset_mode=centred`可估计各边缘的常量偏移。结果包含重力、拟合状态、实际使用帧、辅助参数及`sensitivity_px`，后者记录重力从g/2变到2g时预测图像运动的变化量。

## 样本格式

输入采用JSONL，每行一个样本。长度单位为m，时间为s，速度为m/s；`truth`仅用于评分。

| 字段 | 内容 |
| :---: | :---: |
| `id`, `scenario` | 样本ID及`freefall`、`projectile`或`incline`运动类型 |
| `fps`, `image_size` | 帧率及像素尺寸`[width, height]` |
| `camera` | 4×4相机到世界变换`matrix_world`，相机沿−Z观察；`fx/fy`以图像宽/高归一化，`cx/cy`默认0.5 |
| `object` | 轮廓点`corners`、初始`position`和xyzw顺序的`quaternion`；可声明`angular_velocity`、`inertia`、`mass`、`angular_damping`和`linear_damping` |
| `features` | `box`使用图像边缘，`centre`仅使用中心 |
| `motion.gravity_dir` | 重力单位方向，默认`[0,0,-1]` |
| `motion.t0` | 初始状态到首个拟合帧的时间范围`[lo,hi]` |
| `motion.v0` | 已知初速度；自由落体默认静止 |
| `motion.speed`, `motion.angle_deg`, `motion.directions` | 抛体未知速度范围、仰角范围和可选方位角初值 |
| `motion.slopes`, `motion.speed` | 坡面假设及沿坡速度范围；坡面包含`dir/angle_deg/mu/rolling/length`，负速度表示上坡 |
| `motion.ground_z` | 可选落地平面高度 |
| `window` | `start_frame/max_frames`及可选`edges_visible`；后者逐帧声明左、上、右、下边缘可见性 |
| `masks` | 掩膜`dir/pattern/label`；`label=null`表示二值掩膜 |
| `boxes` | 可替代掩膜，提供`frames/xyxy`及可选秒数`times` |
| `truth.gravity` | 评分用重力，单位m/s² |

`corners`可为8角点或网格轮廓点，并包含真实尺度。初始几何、相机、位姿和时钟与目标视频绑定；运动模型的适用片段在测量前确定。

## 命令接口

```bash
python -m pip install -e '.[test]'
gravtrace fit samples.jsonl -o predictions.jsonl --workers 16
gravtrace score samples.jsonl predictions.jsonl -o summary.json
```

`fit`在进入拟合前移除`truth`。`score`按来源和运动类型报告误差、失败率和覆盖率；覆盖惩罚均值在全部样本上计算`min(relative_error,1)`，失败或缺失估计记为1。`--root OLD=NEW`用于映射部署环境中的掩膜路径。

## 生成视频评分

生成视频使用参考场景的已知条件与同一初始时刻。`scripts/generated_manifest.py GT.jsonl VIDEOS.jsonl OUT.jsonl`将参考样本与生成视频观测关联；视频行提供`id/gt_id/masks/fps/start_s`，随后使用上述`fit/score`命令。

一键流水线使用固定窗口评分，按配置记录重力、初速度与动摩擦对请求值的偏差、V/P定量指标及Qwen视觉判断。不同模型采用相同真实时间范围；执行与配置见[快速上手](phyediting/QUICKSTART.md)，指标定义见[生成视频评测](phyediting/EVALUATION.md)。

## 测量条件

重力测量需要相机参数、初始几何与位姿、角运动、阻尼、重力方向和观测时钟。未知初速度在拟合中估计，参考速度与目标重力用于拟合后的评分。自由飞行和单一支撑面的斜面模型分别对应连续无碰撞片段和稳定支撑片段。

遮挡、截断、身份漂移、接触和缺失观测按逐例状态报告。速度大小与三维向量误差分别统计；摩擦测量使用已知重力和坡面几何，静止样本给出静摩擦下界。各指标的误差分母和覆盖率见[性能评测](phyediting/validation.md)。

## 输入格式转换

`scripts/convert_v22.py`提供历史清单到当前样本格式的转换；媒体、几何和初始状态按各自来源绑定。

## 许可证

MIT，见[LICENSE](../LICENSE)。
