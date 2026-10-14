# 生成视频评测

PhysEdit依次运行生成、SAM3.1单视角跟踪、重力测量及所选评测阶段。V衡量图像质量和视觉稳定性，P衡量物理参数控制，Qwen根据条件图与生成视频判断可见问题。默认评测重力；完整配置见[API示例](../../examples/phyediting/pipeline.ltx.example.json)和[本地Qwen示例](../../examples/phyediting/pipeline.qwen-local.example.json)。

| 评测类别 | 主要指标 | 观察范围 |
| :---: | :---: | :---: |
| 像素一致性 | 全图SSIM、PSNR | 条件帧、参考续段 |
| 视觉稳定性 | 相机运动、背景闪烁、轮廓差异 | 生成全片、首1s |
| 参考运动 | 运动区域IoU、轨迹位移误差 | 固定5s、首1s |
| 参数控制 | 参数偏差、响应斜率、排序一致性 | 单例、完整受控组 |
| Qwen判断 | 问题类别、严重程度、视频证据 | 条件图、生成全片 |

重力对参考视频报告真值误差，对生成视频报告相对请求值的偏差。速度和摩擦通过[独立测量入口](MOTION_PARAMETERS.md)报告。各项结果分别包含误差或分数、可评分数量、覆盖率及逐例状态。

## 配置评测

在`pipeline.json`中选择阶段：

```json
"evaluation": {
  "metrics": ["gravtrace", "vp", "qwen"],
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

生成入口包含`gravtrace`；已有视频可单独补评V/P或Qwen。`generation_runtime.gpu_devices`用于生成、跟踪和V/P掩膜，`generation_runtime.python`指定生成环境；控制器与SAM使用启动命令的Python。阶段名称和配置字段在执行前检查。

## Qwen视频判断

Qwen接收条件图和完整生成视频，判断形变、身份变化、穿透、相机运动及初始条件不一致。每类输出可观察性、存在性、0–3级严重度、文字依据和证据帧。时间性判断引用至少两个视频帧；初始条件判断使用第0帧与条件图对照。

可选择支持原生`video_url`的Chat Completions API，或本地视觉语言模型。API发送条件图与视频容器；本地处理器将时序采样编码成视频张量。两种后端按实际模型版本与采样设置分别汇总。

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

类别格式错误记入`category_errors`，其他有效类别独立统计；部分有效的回答记为`partial`，全部不可用记为`insufficient_evidence`。可观察且严重度≥2计明显违规，各类使用各自的有效分母。不可观察类别保留原因，零严重度不计作无违规。统计对象是模型判断，结果用`semantic_accuracy_validated=false`标识判断准确率的验证状态。

超时、HTTP错误、回答截断、坏JSON及模型或视频信息漂移保留逐例失败状态。原回答、模型信息、提示与图像SHA、token用量随结果保存；密钥回显脱敏。子进程异常退出时，完整且有效的行保留，未写完或未返回的ID记录失败。重复或陌生ID、损坏中间行经过完整性检查。

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

## P：参数误差、响应与排序

单例重力相对偏差为`100 × |estimated_g / requested_g − 1|`。有效估计报告均值、中位数和最大值；全部输入样本报告失败率、覆盖率与原因。`at_bound`记录边界估计值及其状态。

响应与排序使用同场景、机位、目标、seed及生成模型的完整受控组，固定其他设置，仅改变重力。每组输出估计对请求的回归斜率、最高与最低档的估计差、严格同向的成对排序比例，以及至少三个不同档位的Spearman rho。相同估计值计作排序未正确；恒定估计的rho为空。斜率与单例误差共同阅读。

每个item通过`parameter_response_registration`提供组文件路径与SHA。文件包含`group_id`、`varying_parameter="gravity"`、`fixed_controls`和`members=[{"item_id":"...","gravity":1.62}, ...]`。成员的事件、机位、对象、split和请求值逐项核验。缺源、失败、边界估计或未运行成员保留在组中，组结果记录证据不足；完整受控组等权汇总。

## 已有视频补评

在新输出目录评测已有视频：

```bash
physedit evaluate pipeline.json --run runs/pipeline --out runs/evaluation --execute
```

省略`--execute`查看计划。配置可只选择`qwen`或`vp`与`qwen`。入口读取已有预测和视频，在指定新目录保存逐例结果及`combined_summary.json`。

源运行需包含`registered.json`、`items.jsonl`、`observed_rows.jsonl`和`initial_jobs.jsonl`，并通过文件SHA、样本身份及路径检查。已有重力结果仍可展示，执行完成状态按本次选择的阶段统计。

## 结果文件

| 文件 | 内容 |
| :---: | :---: |
| `summary.json` | 各阶段、集合及场景分组统计 |
| `evaluation/vp_results.jsonl` | 逐样本V/P指标与覆盖情况 |
| `evaluation/qwen_results.jsonl` | 逐样本判断、依据与状态 |
| `combined_summary.json` | 已有视频补评的综合结果 |

误差使用有效估计，覆盖率使用全部输入ID；兼容字段`failed`与`failure_rate_percent`统计全部未评分样本，原因区分执行失败、缺源和不适用。V/P各项报告自己的有效分母。Qwen违规比例使用格式有效且可观察的类别，覆盖定义记录在`coverage_basis`。

`evaluation_failed`统计任一所选阶段未完整评分的案例并集。CLI非零退出时，已完成阶段的结果和所有样本状态保留。输入、生成和失败文件随运行目录保存。
