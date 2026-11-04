# Current author correction: one Core100-aligned format

The author explicitly rejected global v7 prompts after the unified Core100
submission-text audit. Use the exact actual Core100 texts already bound to
existing generated videos; organize all 72,000 simulation-video prompts in
the same compact three-lead format with each video's own numeric inputs and
necessary control disclosures. Do not use the v7 Setup/Control plan/Physics
renderer for new default prompt generation. Keep complete physical facts in
metadata and never copy the 100 test cases' numeric parameters onto other
videos. `compact_prompt` no longer silently dispatches to `focused_prompt`.

The local delivery is `../prompts_72000_unified` in the parent dataset
workspace. Current Core100 has all 100 tasks, 300 submitted prompts and 100
generation condition images. The 18 repaired references are already included;
the author confirmed reference repair preceded model generation. Never infer
missing Core100 members from legacy source-ID or historical-hash differences.
See `core100_generation_input_bindings.jsonl` for the current input bindings.
Historical version-specific scores and fixed protocol files remain provenance;
the statements below describing default v7 use are historical and superseded.

## Current semantic repair and H3 binding (2026-11-02)

The active 72,000-video prompt entry is `../prompts_72000_unified/CURRENT_AUDITED_PROMPTS.json`.
HF revision: `223aabbe11b3c0e4f739374430269e144853aa24`; policy: `semantic-units-display-dedup-v2-20261102`.
Use the version-bound English variants. All physical fact keys must have a reviewed dimensional type; unknown keys fail publication.
Exact values remain in metadata. Display at most 8 significant digits or a shorter exact fraction, with relative error <=5e-8.
Deduplicate only source-proven identical actor/property information; retain signs, axes, conditional controls and timing.
Publication requires full source numeric, dimensional, display, clause coverage, tokenizer, Parquet and all 216,000 TXT export checks,
followed by fresh remote byte/hash readback. Source producer regressions are covered in `tests/test_prompt_semantic_rules.py`.
The current H3 run is `/data/yangkaiyuan/h3_prompt_retrain_semantic_v2_20261102`. Its model text is exactly the selected published variant; do not append a generic FPS sentence.
Video/VAE features may be reused only with matching media/clock/preprocessing; conditioning reuse also requires byte-identical model input.
The user chose to finish existing CogVideo validation before automatically starting the fresh H3 LoRA run.
Frozen Core100 submitted inputs, old checkpoints and old feature directories remain provenance and are not rewritten.

---

# Historical policy records (superseded defaults)

# Three complementary English input prompts per video — v7

> Later author decision, 2026-10-23: **Core100 evaluation stays frozen on v6**,
> using all 100 tasks / 300 prompts from
> `benchmarks/english_declared_controls_v6_20261023/core100/known_conditions.json`
> at prompt release revision `f23ee3577952ec1e5357c8a729bfc4daa5c7272d`.
> Follow `catalog/active_core100_conditions.json`. Preserve those exact texts;
> do not rebuild them with the v7 renderer. Existing v6 outputs do not require a
> rerun for the v7 wording change. The global v7 video catalog remains available.

Each video has three complementary English input views with the same selected
physical parameters and necessary external-control information:

1. Scene and initial conditions: layout/state first, then prescribed control and properties.
2. Intervention timeline: known control plan first, then initial setup and properties.
3. Physical conditions: gravity/material/mass conditions first, then geometry and control.

These are not synonym-only variants. The second view describes only prescribed
inputs, never future contact/event ordering. Where no control is declared, it
starts from known initial motion without inventing a force or release schedule.
Chinese source prompts and complete physical parameters remain available.
No variant describes future event outcomes or boundary labels.

Current release: `benchmarks/english_three_focus_v7_20261023` in `phy2/phydataset`.
Use `catalog/active_prompt.json` and `catalog/active_core100_conditions.json`;
historical download links below describe v3 only. The v7 manifest binds current
catalogs, the Core100 overlay, and the prompt-only cropped Gravity100 patch.

- `prompt_variants_en`: all three texts, in order 1, 2, 3.
- `prompt_en`: compatibility alias for variant 1, not the only available prompt.
- `prompt_variant_token_counts` and `prompt_variant_sha256`: matching lists.
- `parameter_facts`: complete exact parameters, including those omitted from text.
- `selected_parameter_keys`: the shared key parameters in all three variants.

All three variants are selected under a shared token budget. Counts include EOS,
are checked with the official pinned LTX, CogVideoX and Wan tokenizers, and never
use truncation. See [verification](tokenizer_verification.json).

## Downloads

- [Base catalog](video_prompts_en.jsonl.gz): 71,892 records, three prompts each.
- [Three-row-per-video CSV](prompts_all_videos_en.csv.gz): 215,676 prompt rows.
- [Release supplement](release_supplement_en.jsonl.gz): 21,696 version-bound records, three prompts each.
- [Fixed100 package](gravity100-three-variants-v3.tar.gz): 100 tasks, three prompts each.
- [Fixed100 token counts](fixed100_token_counts.json): 300 prompt variants.
- [T15 critical pilot](t15_critical_three_variants_v3/inputs.jsonl).
- [Manifest](PROMPT_MANIFEST.json), [summary](summary.json).

Inventories overlap across releases; prompt rows are not additional videos.
Join by video ID and exact release. English v1 and compact v2 remain historical
archives. Chinese remains in the original annotation file.

## Training and evaluation

Choose `--prompt-variant 1`, `2`, or `3` in `physedit.prompt_dataset`. Alternatively
set `prompt_variant` on each selected item. For fixed100, set `prompt_variant` on
the task; `generation_prompt_variants` lists all three files and hashes.
The default remains 1 for compatibility. Freeze the same variant across models
in a comparison; record it and its hash. The three variants do not add test
members or independent trajectories. References, scoring clocks and splits are
unchanged; this release claims no new model scores.

For the T15 pilot, select the corresponding entry in `prompt_variants_en` and
use its hash/counts. Gravity and initial book speed are required in all variants.


## Historical deployed mapping: 2026-10-24 per-case Core100 inputs

**2026-10-27 reconciliation:** the current author instructions for this
checkout require the complete frozen v6 package described at the top of this
document. The mapping below describes the existing website deployment and
its preserved historical records; it does not supersede those current
instructions. The site has not been migrated by this audit. Its 31/69
acceptance count must not be reported as complete-v6 coverage. See
[the submission audit](PROJECT_STATUS.md) for both hash counts.

The author chose to retain original inputs for 69 cases and use the v6
control-disclosure correction for 31 cases (T04/T06/T09/T11/T13/T16 C01-C05,
and T18_C04). Report the complete Core100 under this fixed per-case protocol.
All compared models must use the same version for the same case and variant.
This supersedes the earlier blanket requirement that all historical outputs
match the complete v6 package byte for byte; it does not relabel old text as v6.

The executable hash mapping is
`annotation_site/resources/core100_final_input_policy.json`. Each case binds
three exact submitted-text SHA256 values. Do not rebuild via v7 or replace
historical annotations. A case requiring v6 remains input-pending until the
corresponding generated output and submitted text are actually bound. The
existence of a rerun plan or a statement that reruns ran is not a media binding.

Reference event definitions, boundary intervals, observation windows and pair
admission remain independent of the prompt version decision. Missing truth or
human review is N/A, never a fabricated zero. See
`review/critical_scoring_20261024/REPORT.md` for the current calculation receipt.
