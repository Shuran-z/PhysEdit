# T18 supplementary-search correction — 2026-10-27

## Verified defect

The T18 supplementary worker launched the original renderer with the scene project as its working directory. Released background manifests contain mesh paths relative to the **asset importer root**. Those files did not resolve, and the renderer silently substituted a colliding bounding box for visual-only background geometry. Published videos and original critical-value records are not modified.

On `T18__bg02_physics_lab__g01_moon__contact_friction__p029`, the incorrect replay acquired a `static_geom_1` collision penetrating 0.345122 m at frame 24. The original trajectory did not contain this collision. Position divergence at frame 24 reached 0.219022 m. Restoring full raytracing/resolution alone did not fix it.

Using the importer root restores the released `visual_only_decor_mesh` branch. The repaired source replay has the correct positive event, frame-24 position error 0, and maximum position error 0.000345945 m across all 210 frames. This is one verified source replay, not a claim that all 55 failures are fixed.

All 55 prior source mismatches were audited: 6 differ in terminal contact despite both having earlier contact; 49 differ in whether any contact occurs. 54 first diverge by over 1 mm at frame 24; one at frame 75. These are observed classifications; final per-case causes require repaired replays.

## Code and admission

- `t18_table_contact_boundary_worker.py`: launch from importer root; preflight declared background meshes and prohibit silent bbox fallback. Preserve source parameters, seeds, and native contact event.
- Each new probe records `execution_context.contract=importer_root_relative_assets_v1`.
- Old supplementary T18 runs remain on disk and in evidence but are excluded from the active T18 distance ledger. The original-value catalogs are retained. The pre-fix supplementary ledger is archived separately.
- The registrar admits only repaired runs with matching source/state/config receipts and actual opposite-label endpoint probes. No interval is invented when the searched range has no flip.
- Output eligibility for formal NearAcc remains separate from numerical distance availability.

## Execution

p25: 55 previous mismatches in `original_render_retry_cwd_fix_20261027`, plus 441 other contexts across three `cwd_fix_parallel_20261027_*` queues. p26: 71 contexts across `run_0_cwd_fix` and `run_1_cwd_fix`. These are disjoint source IDs totaling 567. Previously completed supplementary computations are included because their execution directory was affected; this is correction of our supplementary worker, not missing original render metadata.

p26 compatibility fixes use an isolated OpenCV 4.10.0.84 directory (NumPy 2 and glibc 2.27 compatible) and preload the matching system `libGLdispatch`, `libEGL`, and `libOpenGL`. GDB traced the prior segfault to `glGetString` with mixed Conda/system libraries. A minimal scene built successfully after the library fix, and the first repaired T18 source simulation subsequently completed and entered parameter scanning.

Automatic collectors: `scripts.collect_t18_p26_migration --watch`, existing T18 registrar, and `scripts.register_t07_full_grid --watch`. Completed repaired intervals feed `combine_recovered_boundary_distances`; launches and source probes are not counted as completed boundary searches.

T07-B uses the importer root already and is unaffected by this cwd defect.
