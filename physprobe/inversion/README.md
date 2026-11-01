# physprobe.inversion

Simulator inversion of gravity, friction and initial speed, and the V and P metrics of the PhysEdit benchmark. Method: [docs/INVERSION.md](../../docs/INVERSION.md) · Metrics: [docs/METRICS.md](../../docs/METRICS.md) · Running an evaluation: [docs/EVALUATE.md](../../docs/EVALUATE.md)

| Stage | Files |
|---|---|
| Paths and shared geometry | `paths.py`, `common.py` |
| Tracking jobs and camera compensation | `make_gen_jobs.py`, `make_lean_jobs.py`, `gen_register.py`, `cam_comp.py`, `server/sam_tracker.py`, `server/run_sam_tracker.sh` |
| Simulation libraries | `library_plan.py`, `library_split.py`, `library_half_steps.py`, `library_bisect.py`, `library_refine_plan.py`, `fetch_library.py`, `collect_library.py`, `server/` |
| Predictability windows | `horizons_plan.py`, `horizons.py` |
| Inversion | `evaluator.py` for reference videos, `eval_generated.py` for generated videos, `calibrate_band.py` |
| Validation and results | `validation_gate.py`, `merge_generated.py`, `apply_declared_mu.py`, `summarize_generated.py`, `compare_runs.py` |
| Re-generated deliveries | `combine_jobsets.py`, `regen_compare.py`, `tools/evaluate_regenerated.sh` |
| Metrics and tables | `response_metrics.py`, `common_metrics.py`, `benchmark_table.py` |
| Known-answer videos | `make_synth.py`, `make_pan_test.py` |
| Diagnostics | `ref_stats.py`, `ref_ab.py`, `ref_overlay.py`, `ref_residuals.py`, `best_fit_stats.py`, `motion_check.py`, `camera_motion_check.py`, `track_noise.py`, `sam_compare.py`, `sam_vs_truth.py`, `qa_overlay.py`, `report_figures.py`, `vertex_ab.py`, `refined_clips.py`, `apply_object_rules.py` |
| Simulator integration checks | `integration_report.py`, `host_consistency.py`, `projection.py` |
| Deployment | `deploy/`, `tools/` |
