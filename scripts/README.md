# Repository scripts

Prefer the installed module commands for ordinary use. Files in this directory are mainly reproducibility and recovery utilities for specific dataset releases; many require local `review/` evidence, recorded revisions, or server-side files and are not generic commands.

## Stable user-facing commands

```powershell
python -m physedit boundary --help
python -m physedit boundary-evaluate --help
python -m gravtrace --help
```

See the [critical-boundary workflow](../BOUNDARY_EVALUATION.md) and [protocol index](../docs/critical_boundary/README.md) before running an evaluation.

## Current task entry points

| Task | Tools |
|---|---|
| Current Core100 input identities | `prepare_core100_current_inputs.py`, `install_core100_t19_replacement.py` |
| Existing boundary records and distances | `collect_core100_binding_evidence.py`, `recover_core100_released_scans.py`, `build_core100_distance_bindings.py` |
| Original-family audit | `reaudit_core100_original_references.py` |
| Local reference status / read-only export | `python -m physedit.core100_bindings status`, `python -m physedit.core100_bindings export --out NEW.jsonl` |
| Download published dataset | `download_standardized_72000.py`, `download_physedit_final.py` |
| Inventory / release assembly | `refresh_72000_inventory.py`, `assemble_72000_prompt_release.py` |
| Simulator inversion | [physprobe/inversion/README.md](../physprobe/inversion/README.md) |

`publish_*`, `launch_*`, `resume_*`, `render_*` and remote workers are operational tools, not an automatic setup sequence. Their names and paths stay stable because registered jobs and source receipts reference them. Read constants and `main()` before executing release-specific scripts.

## Evidence and recovery utilities

- `audit_all_scene_boundary_sources.py`, `collect_scene_boundary_evidence.py`, `collect_original_search_tasks.py`: locate and reconcile historical scene-family search records.
- `audit_t*_completion_states.py`, `collect_completion_states.py`, `audit_nearacc_readiness.py`: derive event outcomes from saved simulation states and rebuild the NearAcc readiness ledger. These read or write paths under `review/scene_family_completion_20261018/`.
- `probe_t*_*.py`, `register_t*_*.py`, `extract_t*_*.py`: scene- and release-specific backend probes, boundary interval extraction, and distance registration. Read each script's constants and source hashes before reuse.
- `prepare_*` and `build_*`: prepare immutable manifests, review sheets, or handoff packages. These do not by themselves mean inference, human review, or simulation has happened.
- `collect_*`, `recover_*`, `finish_*`: retrieve existing artifacts or continue a bounded recovery workflow. Check the exact target host, revision, and output path first.
- `inspect_live_boundary_releases.py`, `recover_t11_current_release.py`, `recover_t12_current_release.py`, `recover_t13_current_release.py`: recover immutable current HF release identities and verify server-side files against published hashes. `bind_current_release_parameter_families.py` checks actual parameter fields for these releases.
- `t07_original_boundary_worker.py`: server-side T07 original-backend numerical worker; requires an authenticated local plan and isolated output root. `register_t07_original_searches.py` binds completed searches to published branches; `snapshot_boundary_completion.py` reads live job status. Neither status registration nor distance computation automatically admits reference videos.

## Output policy

Raw videos, extracted frames, server logs, model outputs, and large JSON state files belong in local `review/` runs and are ignored by Git. Put stable protocols and compact, source-linked summaries in `docs/`; keep scripts that reproduce a summary alongside this directory. Never commit credentials, signed URLs, or full environment dumps.
