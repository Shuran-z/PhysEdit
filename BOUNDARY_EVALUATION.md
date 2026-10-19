# Critical-boundary evaluation

This repository contains an independent evaluation path for controlled physical video-generation tests. It complements the benchmark's causal-event and GravTrace inversion measurements. It does not change the frozen GravTrace pipeline.

## What is implemented

- Preregistration of the complete sample roster and a separate answer key.
- Generation manifests built from an explicit allowlist, so reference labels, threshold values, distance bins, and inversion eligibility are not sent to the generator.
- Media checks for decode, frame count, resolution, native frame rate, and timestamps.
- Human or independently validated event annotations bound to generated-video SHA-256.
- Balanced target accuracy, verified-boundary distance buckets, cross-outcome pair accuracy, event-chain exact match, and first-error summaries.
- Optional import of frozen, hash-bound GravTrace predictions. Inversion eligibility does not filter samples from branch evaluation.

The pipeline does not include an automatic physical-event judge. Qwen plausibility, image similarity, and successful GravTrace inversion are not substitutes for event labels. Unknown or failed outputs remain in the denominator and score incorrect for the relevant primary metric.

## Install and inspect the interface

From the repository root:

```bash
python -m pip install -e .
python -m physedit boundary --help
python -m physedit boundary run --help
python -m physedit boundary score --help
```

The controller uses only the Python standard library. Actual media validation needs OpenCV (`opencv-python-headless` is already a project dependency). A model runner has its own environment and dependencies.

## Prepare a registration

Create three UTF-8 files: `inputs.jsonl`, `answers.jsonl`, and `spec.json`. Each JSONL has one object per sample. IDs must match exactly. Use [the example schemas](examples/boundary/).

Each input row declares `sample_id`, `condition_image`, `condition_sha256`, `prompt`, `seed`, `num_frames`, `fps`, `evaluation_duration_s`, `source_width`, and `source_height`. Optional `negative_prompt`, `width`, `height`, and condition/trigger timestamps may be kept in the input record. The image hash is the SHA-256 of the exact conditioning file.

Each answer row declares scene/source/family/point IDs, the physical parameter `theta`, `target_event`, all binary reference `events`, inversion status and reason, and either a verified boundary or an explicit unavailable status. A verified boundary includes `source` and positive `normalization_span`, plus either `theta_star` or `[lower, upper]` bracket. Do not fill a boundary from a filename, a nominal `theta_star` tag, or a three-point midpoint. Keep the parameter and boundary in one documented unit.

The spec names a model, the two JSONL paths, and (for generation) a non-empty `generation_command` **as an argv list**, for example `["python", "path/to/runner.py", "--manifest", "{manifest}"]`. Supported substitutions are `{manifest}` and `{run_dir}`; commands are not sent through a shell. The runner reads only the generated manifest. Make the destination run directory new and empty.

Inspect the command-line interface:

```bash
python -m physedit boundary run --help
```

To validate a registration, use the run command without `--execute`:

```bash
python -m physedit boundary run --spec spec.json --run-dir runs/t15
```

It reports counts and hashes without creating a run. Execute only after reviewing the registered inputs and answer key:

```bash
python -m physedit boundary run --spec spec.json --run-dir runs/t15 --execute
```

The run directory is created exclusively and records the registration, hashes, prepared inputs, generation-only manifest, per-sample preparation status, observed media status, receipt, and annotation template. Input errors and model failures remain attached to their registered IDs. Do not re-run into an existing directory.

## Annotate videos and score

`event_annotation_template.jsonl` begins with unknown labels. For every judged video, an annotator or validated event evaluator fills `events` with `0`, `1`, or `null`, and supplies `method`, `evidence`, and the exact `video_sha256` from `observed_rows.jsonl`. Add `event_times_s` for events used in required-order checks. Preserve `null` when an event cannot be judged. The pipeline rejects unbound hashes and does not infer an event from the reference label.

```bash
python -m physedit boundary score --run-dir runs/t15 \
  --annotations events.jsonl --out runs/t15/score.json
```

Optional frozen GravTrace predictions can be supplied with `--gravity predictions.jsonl`. Rows must bind both the generated-video SHA and the reference-registration SHA. The inversion report distinguishes registered, eligible, and fitted denominators.

## Metric interpretation

- **Balanced target accuracy**: average of positive-branch and negative-branch accuracy, first within registered points/seeds and then across source groups/scenes.
- **NearAcc**: balanced accuracy for samples whose normalized distance interval lies wholly in the `near` bucket (distance ≤ 0.05 of the registered normalization span). Ambiguous bucket membership and unverified boundaries do not enter NearAcc; the output reports coverage.
- **Independent PairAcc**: product of the two endpoint accuracies for each preregistered opposite-outcome pair, averaged at family/source level. Seed streams must be disjoint. The current implementation does not support coupled same-seed pair scoring.
- **EventExact**: every registered event bit and every required temporal order must match. Report target accuracy separately so intermediate-chain errors remain visible.
- **GravTrace**: optional relative gravity deviation on its registered eligible subset, with coverage and failure statuses. It is not merged into an arbitrary single score.

The numerical bins are implementation defaults and must be frozen before the test set is scored. The T15 pilot registration has no verified boundary, so it can test obvious branch outcomes and the pipeline, but NearAcc must be `null`. One seed is an engineering smoke test, not a model-performance estimate.

## Status and reproducibility

Full protocol and rationale: [`docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md`](docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md). T15 pipeline-specific caveats: [`docs/critical_boundary/PIPELINE.md`](docs/critical_boundary/PIPELINE.md).

The local T15 renders, source-state exports, prompts tied to those paths, and model outputs are not part of this code release. Prepare a fresh registration from the selected public/release dataset version and record its provenance. Do not commit private videos, credentials, model weights, or local machine paths.

Near-bin interval clarification (2026-10-18): `[0, u]` is near when `0 < u <= 0.05`; zero lower bound is uncertainty, not proof of an exact threshold point. Only `[0,0]` is `at_boundary`. Intervals crossing 0.05 remain ambiguous.
