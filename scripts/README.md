# Repository scripts

Prefer the installed module commands for ordinary use. Files in this directory are mainly reproducibility and recovery utilities for specific dataset releases; many require local `review/` evidence, recorded revisions, or server-side files and are not generic commands.

## Stable user-facing commands

```powershell
python -m physedit boundary --help
python -m physedit boundary-evaluate --help
python -m gravtrace --help
```

See the [critical-boundary workflow](../BOUNDARY_EVALUATION.md) and [protocol index](../docs/critical_boundary/README.md) before running an evaluation.

## Evidence and recovery utilities

- `audit_all_scene_boundary_sources.py`, `collect_scene_boundary_evidence.py`, `collect_original_search_tasks.py`: locate and reconcile historical scene-family search records.
- `audit_t*_completion_states.py`, `collect_completion_states.py`, `audit_nearacc_readiness.py`: derive event outcomes from saved simulation states and rebuild the NearAcc readiness ledger. These read or write paths under `review/scene_family_completion_20261018/`.
- `probe_t*_*.py`, `register_t*_*.py`, `extract_t*_*.py`: scene- and release-specific backend probes, boundary interval extraction, and distance registration. Read each script's constants and source hashes before reuse.
- `prepare_*` and `build_*`: prepare immutable manifests, review sheets, or handoff packages. These do not by themselves mean inference, human review, or simulation has happened.
- `collect_*`, `recover_*`, `finish_*`: retrieve existing artifacts or continue a bounded recovery workflow. Check the exact target host, revision, and output path first.

## Output policy

Raw videos, extracted frames, server logs, model outputs, and large JSON state files belong in local `review/` runs and are ignored by Git. Put stable protocols and compact, source-linked summaries in `docs/`; keep scripts that reproduce a summary alongside this directory. Never commit credentials, signed URLs, or full environment dumps.
