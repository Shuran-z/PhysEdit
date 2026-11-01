# 评测一个模型

## 需要准备

- Python 3.9 或更新版本，安装 `pyproject.toml` 里的依赖：`pip install -e .`
- SAM 3.1 权重 `sam3.1_multiplex.pt`，以及一台有 GPU 的机器用于跟踪。
- [PhyDataset](https://huggingface.co/datasets/phy2/phydataset) 中的 Core100 任务：参考视频、条件帧、提示词和作者原始的 Genesis 场景。
- Core100 任务的仿真库和可预测窗口，按下文一次性准备。

所有数据放在 `PHYSPROBE_WORK` 下，见 `physprobe/inversion/paths.py`。

## 生成

对每个 Core100 任务，以条件帧即参考视频第 5 帧为输入，三种提示词写法、三个随机种子各生成一条视频。存放方式和[已发布的生成视频](https://huggingface.co/datasets/phy2/phy2-benchmark-generations)相同：每条一个 `resized.mp4`，缩放到参考分辨率，旁边放它的条目记录。

## 评测

```bash
cd physprobe/inversion
python make_gen_jobs.py NAME JOB_DIR --gen-dir DELIVERY --seeds 0,1,2 --annotations 1,2,3
bash server/run_sam_tracker.sh JOB_DIR 4 0
python cam_comp.py sam_gen/NAME/items.json sam_gen/NAME/tracks_lean.jsonl --out sam_gen/NAME/tracks_camcomp.jsonl
python eval_generated.py NAME sam_gen/NAME/tracks_camcomp.jsonl --clock realtime --workers 16
python validation_gate.py NAME NAME
python response_metrics.py NAME_gated
python common_metrics.py NAME sam_gen/NAME/tracks_camcomp.jsonl --out NAME
python benchmark_table.py NAME results_gen/response_metrics_NAME_gated.json sam_gen/NAME/tracks_camcomp_stats.jsonl --out NAME
```

1. **任务**：把条件帧配准到每条生成视频，写出 SAM 提示。
2. **跟踪**：SAM 3.1 跟踪每个物体。
3. **镜头补偿**：从轨迹里去掉镜头运动。
4. **反演**：用仿真器反演 g、μ、v。
5. **验证门**：只保留任务和视频格式通过已知答案测试的结果。
6. **指标**：`response_metrics.py` 给出 P 指标，`common_metrics.py` 给出 V 指标，`benchmark_table.py` 合成按模型的总表。

如果 μ 要按提示词写明的摩擦来算，在验证门之前运行 `apply_declared_mu.py NAME KNOWN_CONDITIONS.json`，使用该版提示词的已知条件文件。

## 一次性准备

| 步骤 | 脚本 |
|---|---|
| 每个物体的可预测窗口 | `horizons_plan.py`、`horizons.py` |
| 仿真库的规划、分队列和仿真 | `library_plan.py`、`library_split.py`，在仿真主机上运行 `server/refine_queue.py` |
| 收集仿真库 | `fetch_library.py` 或 `collect_library.py` |
| 参考视频的跟踪和已知答案测试 | `make_lean_jobs.py`、`server/run_sam_tracker.sh`、`evaluator.py ref` |
| 不确定带校准 | `calibrate_band.py` |
| 按生成视频格式重编码的物理正确视频 | `make_synth.py` |
