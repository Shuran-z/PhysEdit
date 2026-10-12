# 冻结的单视角 SAM3.1 前端

`scripts/sam31_frontend.py` 把实际使用的 SAM3.1 目标身份跟踪、RGB 清理、观测检查以及 V4 图像边界测量连接起来，输出可直接供公开生成评分器读取的 `tracks_v4.jsonl`。没有三视角联合反演；每条任务只读取一个视频。反演仍使用现有 `gravtrace/fit.py`，运行前端本身不会拟合重力。

冻结开发结果：1038例、13918帧、30 fps，未知初始线速度，平均相对误差 **2.700312065%**，最大 **15.148096294%**，失败率 **0%**，覆盖率 **100%**。提升来自完整前端和已冻结的 V4 图像边界测量，不能仅归因于替换模型。这些是已完成的开发实验结果，上传代码没有重新测量，也不是 ID/OOD 独立测试结果。

## 依赖与版本

从仓库根目录运行，先 `pip install -e '.[test]'`。推理需要另外准备官方 SAM3 源码及其 PyTorch/CUDA 依赖，以及 SAM3.1 multiplex checkpoint；这里不下载、不包含模型权重或第三方源码。

版本锁见 [`scripts/sam31_frozen/manifest.json`](../../scripts/sam31_frozen/manifest.json)：官方源码 commit `0570b3a5be9c4e694f23d85232fb55f4a6f1f7fc`，checkpoint revision `daa63191845a41281374e725f4c9e51c7a824460`，文件 SHA256 `0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`。`run` 核对这些版本，以及10份原样前端源码和 fitter/camera/V4 文件 SHA；不允许 Python `-O` 跳过原断言。

## 单视角输入与运行

JSONL 每行提供预先登记的观测帧，以及提示帧上的场景框。例如（框需对应实际视频，不是可直接运行的样本）：

```json
{"id":"case01","video":"/absolute/path/case01.mp4","video_sha256":"actual_file_sha256","fps":30,"prompt_frame":0,"frames":[24,25,26,27],"target_name":"book_right","scene_boxes":{"book_right":[100,80,180,160],"mug":[220,90,250,140]}}
```

提示点使用冻结的初始场景框规则自动构建。输入拒绝额外的重力真值、参考初速度、逐帧 oracle 框；`frames` 必须原样保留，窗口由调用者预登记。`video_sha256` 是文件 SHA，不是解码 RGB SHA。一个 `id` 对应一个视频中的一个目标；不同相机应为不同任务，不会融合。

```bash
python scripts/sam31_frontend.py prepare jobs.jsonl runs/sam31_new
CUDA_VISIBLE_DEVICES=0 python scripts/sam31_frontend.py run runs/sam31_new \
  --sam3 /absolute/path/official-sam3 \
  --checkpoint /absolute/path/sam3.1_multiplex.pt
```

`prepare` 只做 CPU 输入验证和记录，不初始化模型。`run` 显式开始一次推理，依次使用同一个设备执行原分支，保留全部阶段的日志、原轨迹、mask 与审计。已有运行目录不覆盖；已尝试的运行不自动重试，失败/partial 留存。

历史源码中1038/365/519等数据规模断言由 `sam31_scope.py` 仅在 `assert` 的测试表达式中绑定到实际任务规模；两个分片可一奇一偶，也允许空分片。逆 AST 核验确保图像策略和数值常量未变。历史源码打印的固定规模不是新运行计数证据，实际计数看 `prepared.json`、`completed.json`。原源码文件本身保持逐字节一致。

## 接入生成模型评测

先用既有入口生成初始提示任务，再转换成与公开固定窗口评分器完全一致的 SAM3.1 任务：

```bash
python scripts/phyediting_gen.py jobs ITEMS.jsonl ROWS.jsonl INITIAL_JOBS.jsonl --compact COMPACT_DIR
python scripts/sam31_frontend.py generation-jobs ITEMS.jsonl ROWS.jsonl INITIAL_JOBS.jsonl SAM31_JOBS.jsonl
python scripts/sam31_frontend.py prepare SAM31_JOBS.jsonl runs/sam31_generated
# 在可用设备上显式执行上述 run 命令，然后评分：
python scripts/phyediting_gen.py score ITEMS.jsonl ROWS.jsonl \
  runs/sam31_generated/tracks_v4.jsonl RESULTS.jsonl --v0 agnostic
```

`INITIAL_JOBS` 只提供条件帧的物体框；转换器只读取目标名、固定窗口和视频帧率，不把重力/参考速度传给跟踪器。生成视频必须已经缩放到源画布，符合原 `jobs` 的输入约定。生成偏差是对请求重力的偏差，不是已知生成物理真值的误差。

## 输出与失败

- `tracks_v4.jsonl`：原 `id`/fps/观测帧，目标 `xyxy`，逐帧原因及视频SHA/冻结manifest/测量文件SHA绑定；缺失观测保持 `null`。
- `measurements_v4.jsonl`：V4状态、实际 BGR 和 uint8 mask SHA、源视频 SHA。直接调用现有 `gravtrace.observations.refine_box`；四支撑不足时按冻结规则回退整数框。
- `prepared.json`：全部注册任务、输入失败原因和文件锁。缺视频、SHA不符、空窗口、提示不可读、实际fps不一致、缺帧或时钟异常均保留为失败任务，不悄悄删除。
- `completed.json` / `failure.json`：前端执行状态；完成不等于全部观测成功或正式科学 QA。全流水线中断时导出全部注册任务的失败轨迹，原 partial 继续保留。

新入口的验证包括 CPU 输入/故障检查、原 RGB 阶段与 V4 的实际媒体 fixture、源文件锁和固定窗口对应检查。初次公开前端时只做了CPU验证；随后site_a的LTX单条真实运行验证已完成SAM3.1推理和V4评分，但拟合为 `at_bound`，详见 [验证状态](QUICKSTART.md#已完成的验证)。1038开发集没有重跑，正式ID/OOD尚未评测。数据、权重、失败研究源与私有路径未上传。

完整生成→前端→固定评分→全部注册样本汇总的操作步骤见 [QUICKSTART.md](QUICKSTART.md)，评分方法见 [GENERATION.md](GENERATION.md)。
