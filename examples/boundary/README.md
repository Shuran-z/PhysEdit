# Registration templates

Copy these files, replace every `REPLACE_*` value, and supply a valid condition image and a real model runner. These templates are deliberately not runnable: they contain no sample data, labels, image, or model command. Compute `condition_sha256` from the final image bytes, not from a resized preview.

`inputs.jsonl` is visible to the generator after the controller writes the allowlisted `generation_rows.jsonl`. `answers.jsonl` stays in the answer file and is never passed to the generation command. `spec.json` points at the two files and gives the runner as an argv array. Follow [`BOUNDARY_EVALUATION.md`](../../BOUNDARY_EVALUATION.md) for execution and scoring.
