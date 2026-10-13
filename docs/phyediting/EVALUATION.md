# 生成视频评测

`python -m physedit run phyediting` 依次执行 I2V/V2V 生成、冻结单视角 SAM3.1＋GravTrace、启用的 V/P 和 Qwen 阶段，最后汇总。评测选项对12个登记模型共用，模型输入模式仍仅允许 I2V/V2V。省略 `evaluation` 时沿用仅 GravTrace；完整评测配置见 [API 示例](../../examples/phyediting/pipeline.ltx.example.json)和[本地权重示例](../../examples/phyediting/pipeline.qwen-local.example.json)。

| 阶段 | 输出 | 输入与范围 |
| --- | --- | --- |
| GravTrace | 请求重力相对偏差、失败率、覆盖率 | 原登记窗口内单视角观测；冻结的 V4 方法 |
| V：像素一致性 | 条件图与参考续段的 RGB SSIM/PSNR，以及参考目标前景补充指标 | 条件帧单独评分；续段按固定真实时间网格匹配原生时间戳 |
| V：视觉稳定性 | 相机运动、背景闪烁、轮廓结构差异 | 完整生成片段及首一秒；目标掩膜及可用图像特征 |
| P：参考运动一致性 | 运动区域 mIoU、归一化轨迹误差 | 参考和生成目标掩膜；轨迹固定5秒及首一秒，mIoU仍为片段诊断 |
| Qwen | 五类可见问题的存在性、严重程度、文字依据、置信度、证据不足标记 | 条件图＋完整生成视频；本地视频张量或支持 video_url 的 API |

视频解码、尺寸、帧率和时间戳检查属于输入验证。P 指标衡量参考运动相似性，不证明物理正确或机械因果关系；不同的合理续段也可能具有参考差异。GravTrace 的数值是**相对于请求重力的偏差**，不是相对于生成视频已知物理真值的误差。

## 统一配置

```json
"evaluation": {
  "metrics": ["gravtrace", "vp", "qwen"],
  "vp": {"mask_backend": "sam31", "reference_duration_seconds": 1.0, "reference_fps": 30, "trajectory_duration_seconds": 5, "trajectory_sampling_fps": 30},
  "qwen": {
    "backend": "api",
    "model": "Qwen/Qwen3.5-9B",
    "base_url": "http://127.0.0.1:8000/v1",
    "api_key_env": "QWEN_API_KEY",
    "timeout_seconds": 120,
    "max_new_tokens": 1024,
    "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}
  }
}
```

`metrics` 显式选择阶段；未支持的名称、未知配置字段、已配置但未启用的阶段会报错。生成入口始终包含 `gravtrace`；只补评 V/P 或 Qwen 时使用下文 `evaluate`。`generation_runtime.gpu_devices` 同时用于生成、冻结观测前端及 V/P 掩膜。`generation_runtime.python` 只指定生成模型环境；控制器及 SAM3.1 使用启动命令的 Python。

### Qwen：兼容视觉 API

要求支持原生 `video_url` 的 Chat Completions 接口。`base_url` 可为 `/v1` 基址或完整 `/chat/completions` 地址，`model` 必须填写服务实际接受的模型名。服务需允许一个条件图 `image_url` 与完整视频 `video_url`，启用视频输入并返回 `choices[0].message.content` 中的 JSON 文本；纯文本或仅支持图片的服务不适用，不能自动退化成图片评测。请求为非流式、`temperature=0`；默认最多1024输出 token。按服务要求设置 `extra_body.enable_thinking` 或 `extra_body.chat_template_kwargs.enable_thinking`，不能覆盖模型、消息或其他评估参数。

API 密钥只从 `api_key_env` 指定的环境变量读取，不写入 JSON 配置或结果。远程服务必须使用 HTTPS；本机 `localhost`、`127.0.0.1` 和 `::1` 可以使用 HTTP。配置不会自动启动服务或下载权重；执行时才向该端点发送条件图和完整生成视频的 base64 字节（最大128MiB视频）。视频解码和采样由服务决定，客户端不能认证服务实际观察了哪些帧；正式比较须固定服务的采样参数并保留服务版本。超时、HTTP 错误、重定向、返回截断/过滤、JSON 不符合格式、同次运行实际模型名变化均逐例记失败，不自动重试。

结果保留声明模型名、服务返回模型名（若提供）、原回答、提示/图像 SHA 和数值 token 用量。格式不合法或被截断的文本回答同样保存于失败记录，并脱敏可能被服务回显的密钥；不计评分、不自动重试，不保存 HTTP 错误正文或传输头。API 别名不能证明底层权重不变；正式比较应固定服务模型版本，并分别报告本地/API或不同模型版本的结果。

### Qwen：已有本地权重

将 `qwen` 替换为：

```json
"qwen": {
  "backend": "local",
  "model": "Qwen/Qwen3.5-9B",
  "model_dir": "/absolute/path/Qwen3.5-9B",
  "python": "/absolute/path/qwen-env/bin/python",
  "gpu_devices": "0",
  "max_new_tokens": 1024
}
```

本地评估在独立进程中使用与实际 `model_type` 对应的官方条件生成类和 `AutoProcessor`、CUDA/BF16、SDPA、非 thinking、确定性解码；只读取 `model_dir` 已有权重，不允许远程代码或自动下载。进程串行运行，不与生成或 SAM 阶段并发；可指定另一个兼容环境，包路径由控制器传入。权重文件 SHA、Torch/Transformers 版本随结果保存；加载失败保留所有案例且只尝试加载一次。

在独立 Qwen 环境安装本仓库的可选依赖：`python -m pip install -e '.[judge]'`。本地入口读取权重 `config.json` 的实际 `model_type`，支持 Qwen2.5-VL、Qwen3-VL（含 MoE）和 Qwen3.5（含 MoE）的官方条件生成类；不加载纯文本权重或远程自定义代码。Qwen2.5-VL 可使用 Transformers 4.51.3，更新模型须使用包含其官方类的版本，缺类会明确报错。旧 SAM/生成环境无需升级；例如已有 Qwen2.5-VL-3B 时，将 `model` 设为 `Qwen/Qwen2.5-VL-3B-Instruct`、`model_dir` 设为实际权重目录。本机 API 后端只用标准库 HTTP，无需安装 Qwen 权重或 SDK。实现依据 [Qwen2.5-VL 官方说明](https://huggingface.co/docs/transformers/v4.51.3/en/model_doc/qwen2_5_vl)和[Qwen3.5-9B 官方模型说明](https://huggingface.co/Qwen/Qwen3.5-9B)，目标服务器仍须逐模型验收。

### Qwen 的观察与判断口径

协议 `visible_video_full_v2`：使用原生分辨率的声明条件图和完整生成视频，不限制为首秒。默认 `video_fps=2.0`、`max_video_frames=64`、`max_pixels=602112`，在运行前固定。视频处理必然涉及时序采样，但本地将采样序列编码为视频张量与视频 token，不作为彼此独立的图片消息。均匀覆盖第一帧至最后一帧，并用偶数帧避免模型暗中补帧；实际原生索引/时间、有效采样fps、时间量化误差、视频SHA、处理器张量形状及视频网格全部保存。长片超过帧预算整例拒绝，不只保留片头或自动缩短范围。源条件像素不一致同样拒绝。

本地保存原生PNG，不先压缩到224像素；尺寸缩放由模型处理器按已登记 `max_pixels` 完成。本地显式传入 `videos`、采样fps，并强制核验 `pixel_values_videos` / `video_grid_thw`。本地和API发送前共同核验条件图实际路径、像素SHA、视频SHA和登记的帧索引/时间，避免路径别名或时间登记漂移。API发送完整视频容器；本地与API使用同一提示和视频，但服务内部采样可能不同，不能声称分数或实际观察帧相同。原生视频API格式参见 [vLLM 官方说明](https://docs.vllm.ai/en/latest/features/multimodal_inputs/#video-inputs)。

五类为 `abnormal_deformation`、`identity_change`、`interpenetration`、`camera_motion`、`condition_inconsistency`。当前回答校验版本为 `visible_category_evidence_v3`，提示版本为 `visible_category_evidence_v3.2`，显式列出五类嵌套对象的字段类型；原生视频输入仍是 `visible_video_full_v2`。每类包含 `assessable`、`present`、0–3级 `severity`、非空 `evidence`、`evidence_frames` 和 `basis`，全局保留 `confidence`、`insufficient_evidence`。时间性判断须引用至少两个已登记视频帧；初始条件一致性只允许引用第0帧并对照条件图，后续离桌/出画不能作为初始条件违规依据。

正例依据分别是 `nonrigid_shape_change`、`object_replacement` / `unexplained_disappearance`、`impossible_overlap`、`static_scene_displacement`、`initial_state_mismatch`。可判断的无违规用 `visible_consistency`；不可判断用 `not_observable` 并说明原因。刚体旋转不是形变，遮挡不是穿透，离画不是身份消失；引用帧和依据字段只检验回答是否合规，不能自动证明语义判断正确。

类别字段、依据或证据帧不合规时，只将该类别标为未知，并在 `category_errors` 保存原因；完整原回答 `raw` 保留，其他合法类别仍可统计。任一类别未知则整例为 `partial`；全类未知为 `insufficient_evidence`。坏JSON、传输截断、模型漂移或视频证据漂移仍拒绝整例，不自动重试。`assessable=false` 的零严重度不是无违规，不进入该类违规率分母。各类有效且严重度≥2计明显违规，逐类报告分母/覆盖率；全部登记ID保留。

该校验不验证模型的判断准确率，汇总保持 `semantic_accuracy_validated=false`。旧回答不会被重写；旧缺少结构化证据的输出不能直接视为v3评分。提示词或校验版本不同的结果分别登记，不能仅修JSON就宣称旧误判已纠正。两次最早实测首秒四张图片使用 `visible_multiframe_1s_v1`，同样不可与完整视频协议混合。

## V/P 的计算与掩膜

输出18项量：全画面及参考目标前景的条件 SSIM/PSNR、参考续段 SSIM/PSNR，以及相机运动、背景闪烁、轮廓差异、运动区域 mIoU、轨迹误差的 `full` / `1s` 版本。SSIM和mIoU越大越好，PSNR以dB计；其他差异量越小越好。

像素评测使用独立版本 `phyediting_pixels_real_time_rgb_v2`，由 `phyediting_vp_v2` 接入；旧灰度SSIM/整段进度对齐结果不能与新版合并。固定 `scikit-image==0.24.0`，使用解码8-bit RGB、`data_range=255`。PSNR按三通道全部像素MSE计算；SSIM逐颜色通道计算后平均，Gaussian 11×11、σ=1.5、K₁=.01、K₂=.03、总体协方差，只统计完整窗口覆盖区域。参考/生成尺寸统一到源尺寸，使用 `INTER_AREA`，不作单应变换、动态裁剪或颜色归一化；尺寸与库版本随结果记录。[标准库参数](https://scikit-image.org/docs/0.24.x/api/skimage.metrics.html#skimage.metrics.structural_similarity)

`reference_duration_seconds` 默认1.0、`reference_fps` 默认30，在配置中于执行前固定，所有案例共用。续段在条件时刻后 `1/fps, 2/fps, …, duration` 采样，时长×采样率须为正整数。按两侧实际解码时间戳分别取最近原生后续帧，等距时选较早帧；条件帧不参与续段。低原生fps会复用帧，逐对保存请求时刻、实际时刻、索引、最大采样时间差和唯一帧数，不插造图像，不拉伸时间。该对齐具有原生采样量化误差，不能称精确连续时刻真值。

任一侧最后可用帧时间不足所登记时长，整个参考像素指标为 `insufficient_evidence`，不以共同短片段替换窗口；条件分数和其他可用指标仍保留。评测仅支持已通过完整时钟检查的固定帧率视频，缺失/重复/VFR时间戳拒绝评分。完整源/生成视频仍解码验证、留存，窗口外尾帧不删除。

这里的真实时间指视频容器的原生时间戳，不推断或修正未知的历史模拟步长；源视频时钟与物理时钟的对应仍由数据来源核验。

每条视频先对固定网格的逐帧分数求算术平均，再对视频等权平均。完全相同的帧 PSNR 为 `+∞`，JSON 用字符串 `"+inf"` 表示；不伪造100dB或丢弃该帧。算术平均中出现 `+∞` 时视频/组均值也为 `"+inf"`，同时报告无穷值帧数/案例数及中位数，`+∞` 不算失败。条件项单独报告，不混入参考续段均值。

前景PSNR只用每个已配对源帧的参考目标二值掩膜，对掩膜内RGB误差取平均；生成掩膜不参与选择评分像素。前景SSIM对原完整图像生成标准SSIM map，再取参考掩膜内且落在有效窗口区域的中心点及通道平均，不把背景涂黑后计算。窗口邻域仍包含背景，因此它是参考前景局部结构分数。任何请求帧参考目标不可见/掩膜为空，整个前景续段指标为证据不足，不跳过困难帧；全画面分数仍保留。参考掩膜来源与SHA随结果保存，SAM掩膜不冒人工真值。

- 相机运动：ORB/RANSAC 单应变换后，图像四角位移除以图像对角线，取中位数；有效配对覆盖率至少0.5。它是图像运动诊断，前景占优时不能独立证明相机移动。
- 背景闪烁：相邻帧配准，排除变换后的目标掩膜、15像素膨胀区及无效 padding；背景灰度残差除以255，有效配对覆盖率至少0.8且有效背景超过100像素。不使用百分位回退。
- 轮廓差异：目标裁剪并居中缩放到128×128，计算相对首帧的平均 `1−IoU`；可见目标至少10掩膜像素，帧覆盖率至少0.95。
- 运动区域 mIoU：相对各自条件时刻目标掩膜的 XOR 并集之间的 IoU。两侧至少三个可见目标帧；有效且无运动的两侧区域均为空时按原公式为1。
- 轨迹误差：掩膜质心按归一化时间插值到32点，去除初始位置后平均欧氏差除以图像对角线；两侧至少三个可见目标帧。

轮廓/运动区域/轨迹使用320×180掩膜，背景闪烁使用原媒体尺寸；源片段从登记条件帧开始，生成片段从首帧开始。一秒版本保留 `[0,1]` 内原生帧，不插造图像或改 fps；任一必需片段不足一秒时该项为证据不足。完整版本保留全部帧；出画、空掩膜和特征缺失可能造成不可评分，原因如实记录，不删尾帧或放宽门槛。

默认 `mask_backend="sam31"` 为 V/P 单独运行冻结的单视角前端，获取源条件帧至源末帧及生成全片段的逐帧掩膜；这些观察不替换 GravTrace 的固定窗口。该阶段可能耗时，且需要可用的 SAM 环境/权重。既有轨迹框不能冒充完整掩膜；前端失败时像素项可保留，依赖掩膜的项分别记失败。

源视频与生成视频独立导出逐帧证据，每项指标只要求其登记范围和必需侧的掩膜。条件前景指标只用源条件帧；参考前景指标只用固定时间对齐实际配对的源帧；闪烁/轮廓只依赖生成侧；mIoU/轨迹需要两侧。末段缺失不抹掉完整首秒，首秒内缺失仍失败，`full` 保留全范围并如实失败，不删尾/缩分母。部分指标有效不等于整例评分成功。

已有掩膜可用 `{"mask_backend":"registered","mask_manifest":"/absolute/path/masks.jsonl"}`，只读取、不启动SAM。清单每行含 `sample_id` 和 `source` / `generated`，侧记录是 `{"path":"...npz","sha256":"..."}`。完整NPZ包含二值 `masks`（N×高×宽）、连续整数 `frames`、原生 `fps`、实际 `video_sha256`、`target_name`、`mask_method`。稀疏NPZ额外含完整 `scope_frames`、与其等长的 `unavailable_reasons`；`frames` / `masks` 只存实际可用观测，缺失帧必须有原因、可用帧原因必须为空。尺寸异常的单帧掩膜按缺失原因保留，不抹掉同侧其他完整范围。没有范围/缺失声明的截短文件仍拒绝，缺失不会补成零掩膜。源范围为条件帧至源末帧，生成范围为0至末帧；SHA、时钟、身份、尺寸、范围漂移仍拒绝。

掩膜非空或SHA匹配不证明目标身份正确。可通过 `evaluation.vp.mask_review_manifest` 添加独立的**否决**记录，不修改SAM或反演。该JSONL每行含 `sample_id`、`source` / `generated` 对应的 `{"path":"review.json","sha256":"..."}`。复核JSON包含 `video_sha256`、`target_name`、`rejected_frames`；每项须有 `frame_index`、非空 `reason` 和该帧真实 `mask_sha256`。视频、对象、帧、掩膜及复核文件逐一绑定，漂移拒绝；已确认错误目标的帧不能参与需要它的指标，其他登记范围独立计算。该入口不能把未知/缺失提升为有效，未复核帧也不宣称身份认证；结果保留 `identity_accuracy_certified=false`。复核发现的错误与原掩膜共同留存。

相机运动/闪烁/轮廓/mIoU/轨迹诊断沿用已核对的现存公式，历史源码 SHA 见 [vp_metrics.py](../../physedit/vp_metrics.py)。轨迹误差现采用 `phyediting_trajectory_real_time_v2`：默认固定5s与1s、30Hz时间网格，原生目标质心在相邻真实时间点间线性插值，移除初始平移并按参考图像对角线归一化。不按视频长度归一化时间、不外推、不跨缺失目标补点；参考或生成未覆盖完整窗口则保留 `insufficient_evidence`，不能缩窗。`trajectory_duration_seconds` 与 `trajectory_sampling_fps` 必须在运行前登记，各模型采用同一值。此变化仅影响V/P轨迹诊断，没有修改冻结反演或原观察窗口；旧轨迹成绩不能与新版本混合。像素实现见 [pixel_metrics.py](../../physedit/pixel_metrics.py)，不能把旧 SAM2 结果称为新 SAM3.1 结果。

## 只补评既有生成产物

```bash
# 默认只打印计划，不生成、反演、加载模型或调用 API。
python -m physedit evaluate phyediting --spec pipeline.json \
  --run-dir runs/existing_generation --output-dir runs/new_evaluation

# 显式执行选定指标；读取既有 predictions，不重新拟合。
python -m physedit evaluate phyediting --spec pipeline.json \
  --run-dir runs/existing_generation --output-dir runs/new_evaluation --execute
```

要求真实既有运行目录的 `registered.json`、`items.jsonl`、`observed_rows.jsonl` 和 `initial_jobs.jsonl`；原清单 SHA、全量身份分母及源/模型路径绑定一致。输出目录必须为新的。可只设 `metrics=["qwen"]` 或 `["vp","qwen"]`；未请求 GravTrace 时已有重力结果仍展示，但不用于综合完成状态。缺失预测不补造。

## 汇总与验证范围

新生成运行的 `summary.json` 保留原重力统计，并在 `evaluations.vp` / `evaluations.qwen` 增加独立汇总；各阶段按全登记分母报告成功、不可评分数、覆盖率、失败率及 `split` / `event` / `camera_id` / `gravity_truth` 分组。V/P 每个量另有自己的可评分分母，视频等权，并按 `unscored_by_status` 区分执行失败/证据不足，保留原ID与原因。兼容字段 `failed` / `failure_rate_percent` 表示全部未评分样本，不只软件异常；缺源和不适用不会当作零误差。Qwen 明显违规比例仅用格式有效且证据充分的记录。`evaluation_failed` 是任一请求阶段未完整评分的案例并集；CLI返回非零不等于其他阶段结果被丢弃。

逐例文件为 `evaluation/vp_results.jsonl`、`evaluation/qwen_results.jsonl`；掩膜清单、Qwen 抽帧/提示 SHA、原回答和模型信息也保留。只评测入口在独立输出目录保存同名文件及 `combined_summary.json`。失败、缺源、不适用、证据不足和 `at_bound` 均保留原ID和原因，不填零误差。本地Qwen子进程异常退出时，完整写出的逐例结果仍经原检查后保留；未写完的尾行和未返回的ID记录失败，保留原JSONL及进程退出码，不自动重试。重复/陌生ID、中间损坏行或正常退出却JSON损坏仍拒绝。

Qwen 汇总标注 `coverage_basis="category_valid_and_model_reported_assessability"` 和 `semantic_accuracy_validated=false`：可评分输出覆盖率不等于判断准确率，模型自报可观察性仍需人工核验。

site_a 已运行两条 LTX I2V 单例完整链路：原T04反演 `at_bound`；另一个已有资格的T03样本得到有效冻结反演及18项V/P结果。两次旧Qwen评测均报告证据不足，原失败结果保留；不能把空依据的五类 `present=false` 当作无违规。

对同一条已生成T03视频的后续诊断未重新生成、运行SAM或拟合。旧接入只有首秒四张224×126图片；提示中的置信度示例和全局不足定义影响回答，单改提示可令置信度由0变成0.8，但依据仍全空。完整视频输入的真实 `pixel_values_videos`、`video_grid_thw` 和时间信息已确认。明确嵌套输出结构后，Qwen2.5-VL-3B在修复后的公开 `evaluate` 入口返回五类完整对象及非空依据，程序退出0；12个采样帧覆盖0–5秒，原81帧视频不裁尾、不改字节。中间的空依据与错误结构回答均保留，严格验证不把它们计为有效判断。

此结果验证视频输入、结构化回答与汇总可以执行，不是判断准确性验收。该3B样本的依据偏笼统，静态背景不能证明运动目标没有变形；模型置信度也不是校准后的准确率。正式报告须核验对象及依据的相关性，并用人工标注验证判断质量。相机稳定性可观察不代表隐藏接触也可认证。

服务器实际逐条执行的生成模型包括LTX、CogVideoX、Wan与Hunyuan，运行时完整代码文件树与GitHub一致。真实生成成功不代表冻结反演、全部18项V/P和Qwen均可评分；各模型范围见 [MODELS.md](MODELS.md)。外部视频API与另8个生成模型未实测，不声称各服务与本地采样等价。未启动批量、正式ID/OOD测试或联合训练。
