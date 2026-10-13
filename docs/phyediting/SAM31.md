# SAM3.1单视角目标跟踪

`scripts/sam31_frontend.py`连接SAM3.1目标身份跟踪、RGB处理、观测检查和图像边界测量，输出目标轨迹供参数评分器读取。每条任务使用一个视频；重力评分由`gravtrace/fit.py`完成。

开发集结果：1038例、13918帧、30 fps，未知初始线速度，平均相对误差 **2.700312065%**，最大 **15.148096294%**，失败率 **0%**，覆盖率 **100%**。该结果使用SAM3.1目标跟踪和图像边界测量，详见[开发集性能](validation.md)。

## 依赖与版本

从仓库根目录运行，先 `pip install -e '.[test]'`。推理需要另外准备官方 SAM3 源码及其 PyTorch/CUDA 依赖，以及 SAM3.1 multiplex checkpoint；模型权重与官方源码由运行环境提供。

依赖清单见[`scripts/sam31_frozen/manifest.json`](../../scripts/sam31_frozen/manifest.json)：官方源码commit `0570b3a5be9c4e694f23d85232fb55f4a6f1f7fc`，checkpoint revision `daa63191845a41281374e725f4c9e51c7a824460`，文件SHA256 `0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`。`run`校验模型、10份跟踪源码以及拟合、相机和边界测量文件的SHA；使用标准Python模式运行，以执行全部断言检查。

## 单视角输入与运行

JSONL 每行提供预先登记的观测帧，以及提示帧上的场景框。下例展示输入格式，框坐标按实际视频填写：

```json
{"id":"case01","video":"/absolute/path/case01.mp4","video_sha256":"actual_file_sha256","fps":30,"prompt_frame":0,"frames":[24,25,26,27],"target_name":"book_right","scene_boxes":{"book_right":[100,80,180,160],"mug":[220,90,250,140]}}
```

提示点使用初始场景框规则自动构建。输入拒绝额外的重力真值、参考初速度、逐帧 oracle 框；`frames` 必须原样保留，窗口由调用者预登记。`video_sha256` 是文件 SHA，不是解码 RGB SHA。一个 `id` 对应一个视频中的一个目标；不同相机应为不同任务，不会融合。

```bash
python scripts/sam31_frontend.py prepare jobs.jsonl runs/sam31_new
CUDA_VISIBLE_DEVICES=0 python scripts/sam31_frontend.py run runs/sam31_new \
  --sam3 /absolute/path/official-sam3 \
  --checkpoint /absolute/path/sam3.1_multiplex.pt
```

`prepare` 只做 CPU 输入验证和记录，不初始化模型。`run` 显式开始一次推理，依次使用同一个设备执行原分支，保留全部阶段的日志、原轨迹、mask 与审计。已有运行目录不覆盖；已尝试的运行不自动重试，失败/partial 留存。

`sam31_scope.py`将数据规模断言绑定到登记任务，保留原图像策略和数值常量。实际任务数量见`prepared.json`与`completed.json`。

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

- `tracks_v4.jsonl`：原 `id`/fps/观测帧，目标 `xyxy`，逐帧原因及视频SHA/前端manifest/测量文件SHA绑定；缺失观测保持 `null`。
- `measurements_v4.jsonl`：边界测量状态、实际 BGR 和 uint8 mask SHA、源视频 SHA。直接调用现有 `gravtrace.observations.refine_box`；四支撑不足时回退整数框。
- `prepared.json`：全部注册任务、输入失败原因和文件锁。缺视频、SHA不符、空窗口、提示不可读、实际fps不一致、缺帧或时钟异常均保留为失败任务，记录具体原因。
- `completed.json` / `failure.json`：前端执行状态及逐例成功、失败数量。全流水线中断时导出全部注册任务的失败轨迹，原 partial 继续保留。

前端输入、媒体和版本校验由软件回归检查；模型运行状态见[模型说明](MODELS.md)，测量结果见[项目性能](validation.md)。

完整生成→前端→固定评分→全部注册样本汇总的操作步骤见 [QUICKSTART.md](QUICKSTART.md)，评分方法见 [GENERATION.md](GENERATION.md)。
