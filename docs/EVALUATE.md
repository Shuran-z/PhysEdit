# Evaluating a model

## Requirements

- Python 3.9 or newer with the packages of `pyproject.toml`: `pip install -e .`
- The SAM 3.1 checkpoint `sam3.1_multiplex.pt` and a GPU host for tracking.
- The Core100 tasks from [PhyDataset](https://huggingface.co/datasets/phy2/phydataset): reference videos, condition frames, prompts and the original Genesis scenes.
- The simulation libraries and predictability windows of the Core100 tasks, built once as listed below.

All data live under `PHYSPROBE_WORK`, see `physprobe/inversion/paths.py`.

## Generate

For every Core100 task, generate one video from its condition frame, which is frame 5 of the reference video, for each of the three prompt variants and three seeds. Store the videos in the layout of the [released generations](https://huggingface.co/datasets/phy2/phy2-benchmark-generations): one `resized.mp4` per item, resized to the reference resolution, next to its item record.

## Evaluate

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

1. **Jobs**: register the condition frame onto each generated video and write the SAM prompts.
2. **Tracking**: SAM 3.1 tracks every object.
3. **Camera compensation**: remove camera motion from the tracks.
4. **Inversion**: simulator inversion of g, μ and v.
5. **Validation gate**: keep the results whose task and video format pass the known-answer test.
6. **Metrics**: `response_metrics.py` gives the P metrics and `common_metrics.py` the V metrics; `benchmark_table.py` combines them into the per-model table.

To score μ against the friction stated in the prompts, run `apply_declared_mu.py NAME KNOWN_CONDITIONS.json` before the gate, with the known-condition file of the prompt release.

## One-time setup

| Step | Scripts |
|---|---|
| Predictability window of every object | `horizons_plan.py`, `horizons.py` |
| Library plan, queues and simulation | `library_plan.py`, `library_split.py`, `server/refine_queue.py` on the simulation hosts |
| Collecting the libraries | `fetch_library.py` or `collect_library.py` |
| Reference tracks and known-answer test | `make_lean_jobs.py`, `server/run_sam_tracker.sh`, `evaluator.py ref` |
| Band calibration | `calibrate_band.py` |
| Physically correct videos in the generated formats | `make_synth.py` |
