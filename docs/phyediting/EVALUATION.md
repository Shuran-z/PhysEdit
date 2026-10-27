# 生成视频评测

> 注：本页描述的是旧版评测流程。生成视频的正式评测已改为 PhysProbe，见[验收报告](../physprobe/ACCEPTANCE_CORE100.md)和[评测指标](../physprobe/METRICS.md)。

一键生成后，PhysEdit通过SAM3.1跟踪目标，按配置测量重力、动摩擦和初速度，并执行V/P与Qwen评测。V衡量视觉质量与运动差异；P报告物理参数偏差、响应与排序；Qwen判断可见问题。

| 评测类别 | 主要指标 | 观察范围 |
| :---: | :---: | :---: |
| 像素一致性 | 全图SSIM、PSNR | 条件帧、参考续段 |
| 视觉稳定性 | 相机运动、背景闪烁、轮廓差异 | 生成全片、首1s |
| 参考运动 | 运动区域IoU、轨迹位移误差 | 固定5s、首1s |
| 参数控制 | 重力、动摩擦和初速度偏差；响应与排序 | 单例、完整受控组 |
| Qwen判断 | 问题类别、严重程度、视频证据 | 条件图、生成全片 |

参考视频与已知参数对照，生成视频与相应请求值对照。重力、动摩擦、初速度分别报告误差、有效样本数、覆盖率和逐例状态。

## 配置评测

在`pipeline.json`中选择评测阶段。下面同时启用重力、动摩擦、初速度、V/P和Qwen，完整示例见[API配置](../../examples/phyediting/pipeline.ltx.example.json)与[本地Qwen配置](../../examples/phyediting/pipeline.qwen-local.example.json)：

```json
"evaluation": {
  "metrics": ["gravtrace", "friction", "velocity", "vp", "qwen"],
  "friction": {"manifest": "/path/to/sliding_conditions.jsonl", "manifest_sha256": "SHA256_OF_SLIDING_CONDITIONS"},
  "vp": {"mask_backend": "sam31", "reference_duration_seconds": 1.0, "reference_fps": 30, "trajectory_duration_seconds": 5, "trajectory_sampling_fps": 30},
  "qwen": {
    "backend": "api",
    "model": "Qwen/Qwen3.5-9B",
    "base_url": "http://127.0.0.1:8000/v1",
    "api_key_env": "QWEN_API_KEY",
    "max_new_tokens": 1024,
    "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}
  }
}
```

`evaluation.metrics`使用五个配置键：`gravtrace`、`velocity`、`friction`、`vp`和`qwen`，分别选择重力、动摩擦、初速度、视觉运动指标和视频判断。为兼容已有配置，省略`evaluation`时只评测重力；一键生成配置仍包含`gravtrace`，其余阶段可分别选择。已有视频补评可选择其中任意阶段并复用原重力结果。

`generation_runtime.gpu_devices`指定生成、跟踪和V/P使用的GPU；`generation_runtime.python`指定生成环境。控制器与SAM使用启动命令的Python。

## Qwen视频判断

Qwen接收条件图和完整生成视频，判断形变、身份变化、穿透、相机运动及初始条件不一致。每类输出可观察性、存在性、0–3级严重度、文字依据和证据帧。时间性判断引用至少两个视频帧；初始条件判断使用第0帧与条件图对照。

支持原生`video_url`的Chat Completions API及本地视觉语言模型。API接收条件图与视频文件；本地处理器将采样帧编码成视频张量。结果按模型版本与采样设置分别汇总。

| 后端 | 配置项 | 运行方式 |
| :---: | :---: | :---: |
| API | `model`、`base_url`、`api_key_env` | 条件图＋原生视频请求 |
| 本地 | `model`、`model_dir`、`python`、`gpu_devices` | 官方模型类＋视频处理器 |

本地配置示例：

```json
"qwen": {
  "backend": "local",
  "model": "Qwen/Qwen3.5-9B",
  "model_dir": "/path/to/Qwen3.5-9B",
  "python": "/path/to/qwen-env/bin/python",
  "gpu_devices": "0",
  "max_new_tokens": 1024
}
```

在Qwen环境安装`python -m pip install -e '.[judge]'`。本地入口支持Qwen2.5-VL、Qwen3-VL及Qwen3.5的官方条件生成类，含MoE变体；Transformers版本需包含所选权重的模型类。权重地址见[模型页](MODELS.md#跟踪与视频评测模型)。

<details>
<summary>视频采样、API与回答格式</summary>

本地默认2fps、最多64帧、`max_pixels=602112`，均匀覆盖第一帧至最后一帧，使用偶数采样帧。保存原生PNG，缩放由模型处理器完成；实际帧号、时间、有效采样率、量化误差、视频SHA、张量形状与`video_grid_thw`随结果记录。超出帧预算的片段报告输入错误，观察范围保持完整。处理器显式接收`videos`与采样fps，并检查`pixel_values_videos`和视频网格。

本地读取已有权重，使用CUDA/BF16、SDPA、非thinking和确定性解码。生成、SAM和Qwen阶段串行执行。模型文件SHA、Torch/Transformers版本与原回答保存在结果中。加载失败保留全部样本状态。

API地址支持`/v1`基址或完整`/chat/completions`路径。服务需同时接受`image_url`与`video_url`，返回`choices[0].message.content`中的JSON。请求非流式，`temperature=0`，默认最多1024输出token，视频上限128MiB。`extra_body`可配置服务的thinking选项；模型、消息与评测参数由入口统一提供。远程服务使用HTTPS，本机服务可使用HTTP。密钥从指定环境变量读取；条件图与视频按实际SHA和时间检查后发送。API内部采样由服务决定，比较时固定模型版本和采样参数。[视频API格式](https://docs.vllm.ai/en/latest/features/multimodal_inputs/#video-inputs)

五类字段为`abnormal_deformation`、`identity_change`、`interpenetration`、`camera_motion`、`condition_inconsistency`。每类包含`assessable`、`present`、`severity`、`evidence`、`evidence_frames`和`basis`；全局记录`confidence`与`insufficient_evidence`。依据区分刚体旋转与形变、遮挡与穿透、离画与身份变化。

依据名称包括`nonrigid_shape_change`、`object_replacement`、`unexplained_disappearance`、`impossible_overlap`、`static_scene_displacement`、`initial_state_mismatch`；无违规使用`visible_consistency`，不可观察使用`not_observable`。格式检查验证字段与帧引用，内容判断由Qwen给出。

类别格式错误记入`category_errors`，有效类别照常统计。部分有效的回答记为`partial`，全部不可用记为`insufficient_evidence`。可观察且严重度≥2计明显违规，各类使用各自的有效分母。不可观察类别保留原因，零严重度不计作无违规。`semantic_accuracy_validated=false`表示这些统计来自模型回答，尚未与人工标注核验准确率。

超时、HTTP错误、回答截断、坏JSON及模型或视频信息漂移保留逐例失败状态。原回答、模型信息、提示与图像SHA、token用量随结果保存；密钥回显脱敏。子进程异常退出时，完整且有效的行保留，未写完或未返回的ID记录失败。重复或陌生ID、损坏中间行会导致完整性检查失败。

提示正文沿用当前事件模板或输入文本，以`builtin_event_template`、`registered_item_text`记录来源；固定相机与请求重力说明统一追加。`prompt_is_exact_official=false`记录这一文本组织方式。Qwen观察版本为`visible_video_full_v2`，结果按提示与回答格式版本保存。

</details>

## V：图像与运动指标

全图SSIM和PSNR分别评估条件帧与参考续段。参考续段默认1s、30Hz，按真实视频时间戳匹配最近原生帧，等距时选择较早帧；条件帧单独统计。每条视频先对帧求平均，再对视频等权平均。原生采样带来的时间量化误差随结果报告。

SSIM和IoU越大越好，PSNR以dB计；其余差异量越小越好。相机、闪烁和轮廓分别报告生成全片及首1s结果；运动IoU与轨迹分别使用固定5s及首1s窗口。

| 指标 | 计算方式 | 有效观测要求 |
| :---: | :---: | :---: |
| 相机运动 | ORB/RANSAC后四角位移／图像对角线 | 有效配对≥50% |
| 背景闪烁 | 配准后背景灰度残差／255 | 配对≥80%，背景>100px |
| 轮廓差异 | 居中缩放后相对首帧的平均1−IoU | 目标≥10px，帧覆盖≥95% |
| 运动区域IoU | 两侧相对条件掩膜的XOR区域并集IoU | 固定窗口，至少3次可见观测 |
| 轨迹误差 | 相对初始位置的质心位移差／图像对角线 | 固定窗口，连续有效目标观测 |

轨迹在相邻真实时间点间线性插值。运动IoU取最近原生掩膜；两侧都无运动时IoU为1。视频长度保持原值，评测使用统一秒数；窗口不足、出画和缺失目标各自保留不可评分原因。各项的分母根据实际必需观测独立计算。

<details>
<summary>像素计算与时间对齐</summary>

固定`scikit-image==0.24.0`，使用解码8-bit RGB及`data_range=255`。PSNR使用三通道全部像素MSE；SSIM逐通道计算后平均，Gaussian 11×11、σ=1.5、K₁=.01、K₂=.03、总体协方差，统计完整窗口覆盖区。两侧统一到源图像尺寸，使用`INTER_AREA`。像素分数直接比较完整图像；尺寸和库版本随结果记录。[SSIM参数](https://scikit-image.org/docs/0.24.x/api/skimage.metrics.html#skimage.metrics.structural_similarity)

续段取条件时刻后的`1/fps, 2/fps, …, duration`；时长与采样率乘积为正整数。低原生fps可能复用帧，记录请求时刻、实际时刻、帧号、最大时间差与唯一帧数。视频须通过完整固定帧率和时间戳检查；时长不足保留状态，条件项和其他有效指标分别计算。时间采用视频容器的原生时间戳，模拟步长与媒体时钟的对应由数据来源提供。

相同帧的PSNR为`+∞`，JSON写作`"+inf"`。算术平均中的无穷值保持原值，同时报告无穷帧数、案例数和中位数。条件项与续段分开汇总。

相机运动取角点归一化位移的中位数。背景闪烁排除变换后的目标掩膜、15px膨胀区及无效padding。轮廓裁剪后居中缩放到128×128。轮廓、IoU和轨迹使用320×180掩膜，背景闪烁使用原媒体尺寸。

运动指标的时间网格由`trajectory_duration_seconds`和`trajectory_sampling_fps`在运行前统一指定。质心插值限定于相邻有效原生观测，缺失目标、外推及时间规整均不参与轨迹计算。实现见[pixel_metrics.py](../../physedit/pixel_metrics.py)和[vp_metrics.py](../../physedit/vp_metrics.py)。

</details>

## 目标掩膜

默认`mask_backend="sam31"`独立提取源条件帧至源末帧、生成首帧至末帧的目标掩膜。V/P观察与参数测量窗口分别保存。SSIM/PSNR使用图像；闪烁和轮廓需要生成侧掩膜；IoU和轨迹需要两侧掩膜。各项只检查自己的观察范围。

已有掩膜可配置`{"mask_backend":"registered","mask_manifest":"/path/to/masks.jsonl"}`。身份复核通过`mask_review_manifest`提供，确认错误的目标帧从相关指标中排除，原掩膜与复核原因共同保留。

<details>
<summary>已有掩膜与身份复核格式</summary>

清单每行包含`sample_id`与`source`／`generated`，侧记录为`{"path":"...npz","sha256":"..."}`。完整NPZ包含二值`masks`（N×高×宽）、连续整数`frames`、原生`fps`、`video_sha256`、`target_name`和`mask_method`。

稀疏NPZ额外提供完整`scope_frames`及等长`unavailable_reasons`。`frames`和`masks`存储实际可用观测，缺失帧附原因，可用帧原因为空。异常尺寸的帧按缺失处理，其他有效范围保留；缺失观测保持缺失状态。视频SHA、身份、时钟、尺寸和范围逐项检查。

身份复核清单每行含`sample_id`及两侧的`{"path":"review.json","sha256":"..."}`。复核JSON包含`video_sha256`、`target_name`和`rejected_frames`；每项提供`frame_index`、`reason`和真实`mask_sha256`。文件、帧和对象逐一绑定，相关范围分别评分。`identity_accuracy_certified=false`记录自动目标跟踪的身份验证状态。

</details>

## 物理参数测量

| 参数 | 配置键 | 测量与输出 |
| :---: | :---: | :---: |
| 重力 | `gravtrace` | 目标轮廓投影拟合；大小偏差与组级响应 |
| 动摩擦 | `friction` | 纯滑动减速拟合；有效系数与静止下界 |
| 初速度 | `velocity` | 自由飞行或沿坡拟合；模长及向量误差 |

`summary.json.physical_parameters`以`gravity`、`friction`、`initial_velocity`并列保存结果。三项共享`registered/scored/failed`、`mean_error_percent/max_error_percent`、`coverage_percent/failure_rate_percent`及逐例失败原因。原重力字段和`evaluations`路径继续兼容已有分析脚本。

重力测量使用预先确定的运动片段，依据三维轮廓投影与SAM边界位移进行拟合，目标重力仅用于评分。

`velocity`读取生成视频的单视角观测。自由飞行样本固定已有重力估计，单独拟合三维初速度；滑动样本在已知坡面与重力条件下，同时估计沿坡初速度和动摩擦。重力结果保持原值。初速度参考时刻随逐例结果保存，大小、方向和零目标误差分别统计。

`friction`的输入清单提供样本身份、初始位置、坡向、坡角、轮廓、阻尼和已知重力，并绑定来源文件。实际边界框与采样时间由生成视频的SAM观测填入；清单中的参考像素不参与拟合。摩擦测量将请求重力作为固定输入，与重力偏差并列报告。格式见[输入示例](../../examples/phyediting/friction.example.jsonl)，场景条件说明见[测量方法](MOTION_PARAMETERS.md#动摩擦)。

各指标独立判定适用性。有独立滑动条件依据的样本可生成并评测摩擦，同时保留重力不适用的原因。静止样本仅在平衡条件明确时报告静摩擦下界，动摩擦点值保持为空。缺源、缺帧、转动、外力或支撑条件不符的样本保留状态与原因。

生成前，启用的速度与摩擦目标写入提示和`parameter_targets`，连同输入文件一起校验。补评已有视频时，新增参考参数与生成时已记录的请求分别标明；已有请求的值或参考时刻发生变化会报错。

## P：参数误差、响应与排序

重力、动摩擦和初速度大小使用相对偏差`100 × |estimate / target − 1|`，各自报告均值、中位数、最大值、覆盖率与失败率。摩擦和初速度另报告P95与绝对误差，零目标只计算绝对误差。初速度同时报告三维向量误差。全部输入样本报告失败率、覆盖率与原因。`at_bound`记录边界估计值及其状态。

响应与排序使用同场景、机位、目标、seed及生成模型的完整受控组，固定其他设置，仅改变该组指定的一个参数。每组输出估计对请求的回归斜率、最高与最低档的估计差、严格同向的成对排序比例，以及至少三个不同档位的Spearman rho。相同估计值计为排序错误；恒定估计的rho为空。斜率与单例误差共同阅读。

每个item通过`parameter_response_registration`提供组文件路径与SHA。文件包含`group_id`、`varying_parameter="gravity"`、`fixed_controls`和`members=[{"item_id":"...","gravity":1.62}, ...]`。成员的事件、机位、对象、split和请求值逐项核验。含缺源、失败、边界估计或未运行成员的组保留全部成员，并标记证据不足。有效组等权汇总。

初速度与摩擦通过各自的`response_manifest`及`response_manifest_sha256`配置受控组，设置位于`evaluation.velocity`或`evaluation.friction`。组文件为JSON数组，字段包括`group_id`、`varying_parameter`、`fixed_controls`和`members`；每个成员提供`item_id`、`item_sha256`与`value`。变化参数分别为`initial_speed`或`effective_kinetic_friction`。除目标参数外，场景、机位、几何、重力和生成seed需相同；速度组保持方向不变。完整组自动汇总响应斜率、严格排序比例和Spearman rho，缺失成员保留在原组中。

## 已有视频补评

在新输出目录评测已有视频：

```bash
physedit evaluate pipeline.json --run runs/pipeline --out runs/evaluation --execute
```

省略`--execute`查看计划。配置可单独选择`velocity`、`friction`、`vp`或`qwen`，也可组合选择。命令读取已有重力预测和视频，在新目录保存逐例结果及`combined_summary.json`。

源运行需包含`registered.json`、`items.jsonl`、`observed_rows.jsonl`和`initial_jobs.jsonl`，并通过文件SHA、样本身份及路径检查。已有重力结果仍可展示，执行完成状态按本次选择的阶段统计。

## 结果文件

| 文件 | 内容 |
| :---: | :---: |
| `summary.json` | 各阶段、集合及场景分组统计 |
| `evaluation/velocity_results.jsonl` | 初速度大小、向量、偏差与状态 |
| `evaluation/friction_results.jsonl` | 动摩擦点值、静摩擦下界与状态 |
| `evaluation/vp_results.jsonl` | 逐样本V/P指标与覆盖情况 |
| `evaluation/qwen_results.jsonl` | 逐样本判断、依据与状态 |
| `combined_summary.json` | 已有视频补评的综合结果 |

误差使用有效估计，覆盖率使用全部输入ID；兼容字段`failed`与`failure_rate_percent`统计全部未评分样本，原因区分执行失败、缺源和不适用。速度与摩擦的点估计覆盖率、可评分覆盖率分别保存；静摩擦下界只计入信息覆盖。各阶段按集合、事件、机位、模型和seed分组汇总，V/P各项报告自己的有效分母。Qwen违规比例使用格式有效且可观察的类别，覆盖定义记录在`coverage_basis`。

`evaluation_failed`统计任一所选阶段未完整评分的案例并集。CLI非零退出时，已完成阶段的结果和所有样本状态保留。原输入、生成视频和失败记录保留在运行目录中。
