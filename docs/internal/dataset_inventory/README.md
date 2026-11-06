# Active 72,000-slot media inventory

## Current release decision and T19 update (2026-10-30)

The current standard catalog registers `author_accepted: true` for all 72,000
records. Its old quality labels record evidence coverage and no longer filter
release or training admission. Do not describe the 38,163 pending-evidence
records as confirmed unusable. Current training membership is 45,357 records;
T19 remains in the OOD holdout. Older counts below are dated audit snapshots.

All 960 Isaac T19 source files were compared with the prior inventory:
246 have updated bytes and 714 are unchanged. All 246 updated files passed
full decode and hash checks; all 86 associated configurations are byte-identical.
This does not prove every updated file was resimulated or every ghosting issue
was fixed. Three updated videos from
`T19__bg01_home_ase__g01_moon__boundary_d2_minus_r1` passed dense motion-frame
review and now replace their old files. Six Isaac T19 videos in total have
individual visual-review evidence. No prompt text, training membership or
Core100 inputs changed in this update.

Publication: `phy2/phydataset@33b72021608c628d714ec8657c78cfc270e63efd`.
Proof: `releases/physedit/provenance/quality_review/t19_updated_20261030/`.
Local receipt: `../release_72000_active/t19_rerender_followup_20261030/PUBLISHED.json`.
Updated video hashes, previous versions, prompt-media bindings and scene
indices were verified after publication. Video acceptance does not supply
missing simulation states or new critical-boundary truth.

The author authorized replacing the missing **Isaac old T14** quota with the
existing **T14S** delivery (320 trajectories, 960 videos) on 2026-10-28.
T14S retains its actual scene identity. It does not inherit old T14 events or
critical values. Genesis old T14 and frozen Core100 inputs remain unchanged.

The authoritative local pointer is `../release_72000_active/ACTIVE.json`
relative to the repository root. It selects an immutable, timestamped inventory
containing the baseline, authorized T14S replacement, and completed T18/T19
supplements. Earlier `FINAL_COUNTS.json` files remain historical snapshots.

Run `python scripts/refresh_72000_inventory.py` with the existing SSH access.
It writes all 20 scene quota counts, per-video source host/path/hash, remaining
render tasks, source quality labels, and post-render integrity results.
It refuses duplicate sample-camera keys, conflicting completed receipts,
or over-quota background/gravity cells. It counts successful retries once.

`scripts/watch_72000_inventory.py` refreshes every five minutes. The remote
`scripts/audit_render_supplements.py` performs full video decode, hash checks,
state frame/object/finite-value checks, and produces three-camera review sheets.
These checks do **not** certify collision physics or event observability.
Their completion marker explicitly retains visual/physical review as pending.

Inventory membership is not training or evaluation admission. In particular:

- The author authorized re-review of the 1,830 Genesis T19 videos on 2026-10-29.
  Hash-bound review decisions supersede their blanket exclusion individually:
  9 currently accepted and 1,821 awaiting visual/physical adjudication. All 1,830
  completed full decode, hash and original-state checks. This is not full visual
  acceptance. A later explicit author request permits individually qualified
  Isaac T19: 3 videos are now accepted, 957 remain excluded. This is not batch approval.
- New renderings require visual/physical review; source quality is never silently upgraded.
- New source-bound prompts and train/test source-group exclusions remain separate requirements.
- Existing source QA labels do not mean every baseline video was reviewed again.
- This process does not publish a Hugging Face revision or change frozen evaluations.

## Quality accounting

The active inventory now assigns every present video one mutually exclusive tier:

- `USABLE_PER_EXISTING_SOURCE_ACCEPTANCE`: explicit source acceptance, canonical QA
  pass, source QA pass, or accepted T14S delivery. This preserves original acceptance;
  it does not claim a new full-set visual/physical audit or completed split checks.
- `PENDING_REVIEW`: all other source evidence, including a published archive with
  original QA limitations, partial visual review, integrity-only checks, and new renders.
- `UNUSABLE_RETIRED` / `UNUSABLE_INTEGRITY_FAILURE`: author-retired references or
  verified integrity failures. An audit execution error stays pending, not unusable.

Unrendered quota slots are counted separately, not mislabeled as bad videos.
The three present-video tiers plus unrendered slots must sum to exactly 72,000.
This conservative grouping does not mean every pending video has a defect.

Per-video visual/physical adjudications can be supplied in
`../release_72000_active/visual_review/adjudications.jsonl`. Every decision must
bind the exact video SHA-256, identify its reviewer and evidence. Acceptance
requires explicit identity/geometry, contact physics, declared controls, event
visibility and temporal-coverage checks. Rejection requires a specific reason.
VLM suggestions, sparse-frame inspection and integrity PASS alone never create
acceptance records. Author-retired references cannot be reactivated through this
file without explicit author authorization. The authorized Genesis T19 review
uses a separate `quality_reactivation` record bound to the exact video hash;
this Genesis authorization does not apply to Isaac T19. Isaac uses the separate
`author_20261029_use_qualified_isaac_t19` authorization with its own hash-bound
visual review. New verified acceptance and carried-over source acceptance are counted
separately in `QUALITY_STATUS.md`.

Active recovery/evidence (2026-10-28 local date):

- Two p25 T19 replay renders stalled with 44-byte video headers for over an hour.
  Verified renderer processes were stopped after saving evidence. Fresh-output,
  isolated per-camera cache retries are in
  `/data_cached/wangzijun_p25/t19_stall_recovery_20261029`; the inventory and QA
  watchers include that root. Do not restart the old failed queue or duplicate it.
- The recovered `impact_eccentricity__p002` trajectory matches its original
  210-frame positions, velocities and rotations exactly (10,920 values checked).
  Cache isolation is a successful recovery attempt so far, not a proven root cause.
- Six dense camera sheets (22 sampled frames each) were inspected by the assistant.
  A separate six-video advisory Qwen pixel probe completed on p26 at
  `/data2/wangzijun_p25/liyuhan/reference_pixels_probe_20261029`.
  Collect its `results.jsonl` and `complete.json`; do not auto-approve from outputs.
  In the first T18 result Qwen miscounted 7 books as 4 and incorrectly placed rest
  at frame90; the controlled book moves another 0.2127m by frame120. The local
  `visual_review/qwen_evidence_conflicts.json` records this judge error.
- `visual_review/pending_video_review_queue.jsonl.gz` holds the unreviewed
  inventory with exact video hashes and five required quality checks. This is a
  queue, not completed review. Refresh it when inventory membership changes.
- All 651 supplement trajectories now have original cam01 configuration snapshots
  bound by the prelaunch source SHA-256 in
  `../release_72000_active/supplement_source_configs.jsonl.gz`; the corresponding
  binding report records zero mismatches. This restores input provenance for
  control/parameter checks and later prompt construction, not quality acceptance.

## Recorded contact diagnostics (2026-10-29 UTC)

`scripts/audit_supplement_contacts.py` is running under a single-process lock on
p25 and sg88, expecting 350 and 301 supplement trajectories respectively.
Remote evidence lives in each host dataset root's `supplement_contacts_20261029`.
It records contact-depth peaks, actor pairs, frames, substeps and bound video hashes;
these are diagnostic priorities, not pass/fail thresholds. Decode/state PASS
never overrides these pending physical checks.

The recovered T19 mass-ratio p020 has a 12.46 mm recorded book/can contact peak.
A T18 library/mars friction p020 record has a 147.76 mm solver peak at frame72,
but targeted three-view rendered frames do not corroborate a visible overlap of
that size. Do not equate solver contact depth with measured image penetration.
Evidence and the pending decision are saved in
`../release_72000_active/visual_review/t18_extreme_contact_review.json` and the
adjacent frame sheet. No formal acceptance or rejection was created from these
contact-depth diagnostics or sparse image inspection.

Targeted follow-up compared rendered-frame box geometry with the largest contact
records: T18 library/mars friction p020 frame72 overlaps by 0.2504 mm under the
configured box proxies, whereas the recorded substep peak is 147.76 mm. T19
home/moon mass p009 frame68 has separated box proxies, despite a recorded
107.74 mm substep peak. Three-view frame evidence and exact geometry outputs are
linked by `visual_review/contact_geometry_comparison_review.json`. These checks
rule out interpreting the peak number as measured overlap at that saved frame;
they do not establish the cause of the substep discrepancy or grant full-video
acceptance. Both samples remain pending, with original media/state untouched.

Renderer implementation provenance is now saved separately under
`../release_72000_active/renderer_source_evidence/` with three source snapshots and
SHA-256 values. The T19 restitution wrapper applies a one-time analytic impulse
on the first detected configured pair contact (77 supplement source groups).
Future prompt/metadata construction must preserve that runtime implementation;
do not describe it as solely a native material coefficient. These are current
source snapshots, not proof of the exact historical executable used by every
render. No frozen Core100 prompts or running render configurations were changed.
Contact collection reads after each `scene.step`, whereas the saved frame pose
follows all frame steps. The source inspection found no demonstrated array-index
bug; it does not resolve the numerical peaks or justify automatic acceptance.

`build_contact_review_evidence.py` produced targeted windows for the top 12
recorded dynamic-contact peaks on each host (24 trajectories / 72 camera sheets,
zero collection errors). Each sheet includes initial/final frames and seven
consecutive frames around the peak, with exact source-video and sheet hashes.
Outputs are in `contact_review_windows_20261029` under each host dataset root.
This is evidence preparation, not 72 quality passes. T18 studio/high overlap p004
was inspected across all three views; the elevated extracted book is explicitly
fixed/scripted in its source configuration. Its partial review remains pending
and is saved under the local `visual_review/contact_windows` directory.

`../release_72000_active/supplement_control_provenance.jsonl.gz` now records
input-only control provenance for all 651 supplement groups: 381 scripted-motion
groups, zero explicit runtime-force groups, and 77 T19 restitution-patch
candidates. Original keyframe indices, fixed flags, initial motion, source paths
and source config hashes are retained. This identifies what new prompts must
disclose without guessing outcomes or release times. No new prompt text has yet
passed token/control verification; these records do not increase prompt-bound
or quality-approved video counts.

Saved-frame geometry follow-up now covers 21 of the 24 peak-contact candidates;
three non-box pairs are explicitly excluded from the box method. No execution
errors occurred. Three library T18 cases still have about 6.28--7.88 mm collision
box overlap in their saved-frame windows and remain priority visual/mesh-alignment
reviews; this is not an automatic rejection threshold. The largest solver peaks
are generally not the largest rendered-frame overlaps. Local batch evidence is
`visual_review/contact_geometry_batch_summary.json`, with frame-level records
in the two host-specific geometry files. The high-gravity friction p002 cam01
window was inspected and retained pending rather than passed from a sparse sheet.

Whole-trajectory follow-up on the three 6--8 mm proxy-overlap candidates found
nominal visual-size box overlap peaks of 4.78--6.38 mm, with 55--58 saved frames
above a 1 mm diagnostic level. All three involve the fixed scripted extraction
book. This persistence must not be dismissed as a single substep spike; it also
does not prove actual mesh intersection. A native-resolution cam01 close-up for
library/highest-gravity friction p002 was inspected and retained pending mesh
alignment review. Evidence: `visual_review/persistent_contact_followup.json`.

A concrete cam01 rejection is now recorded for T18 library/highest-gravity
friction p002. Actual OBJ bounds match the configured sizes. Welding coincident
texture/normal seams without deforming vertices exposes closed page components;
the frame53 witness point is inside both books' page solids. This confirms an
actual mesh intersection, beyond the solver-depth alarm. The SHA-bound decision
is in `visual_review/adjudications.jsonl`; originals remain intact and a separate
repair queue was saved. Other cameras are not automatically rejected from cam01
state evidence. This finding does not affect every T18 video.

A separate T18 collision-repair diagnostic is now at
`/data_cached/wangzijun_p25/t18_contact_repair_probe_20261029` on p25 GPU3.
It compares original 4 versus refined 16 solver substeps, preserving gravity,
actuation and total frame timing. It uses low-resolution raster/no-video output
for state diagnostics only; neither run is a replacement release video. Initial
attempts hit the missing legacy manifest path; those error receipts were retained
and the retry uses the recovered manifest used by the completed sg88 rendering.
Collect both diagnostic state outputs and compare overlap before deciding on a
full-resolution correction. Existing rendering jobs and original media stay intact.

Both initial repair diagnostics completed (210 state frames each): original
substeps4 reproduces approximately 6.367 mm nominal visual-box overlap;
substeps16 still gives 6.241 mm, with 55 frames over 1 mm in both. Increasing
substeps alone did not fix the issue. Comparison evidence is saved locally in
`visual_review/t18_substep_repair_comparison.json` and remotely as `comparison.json`.
Two further isolated diagnostics test `constraint_timeconst=0.002` and `0.001`
with original substeps4, since the installed solver default is 0.01 and this
option is explicitly forwarded by the renderer. These remain unvalidated solver
experiments, not accepted replacement videos; controls and gravity are unchanged.

The contact-time-constant probes also completed: 0.002 and 0.001 did not remove
the 6 mm overlap; 0.001 increased maximum dynamic speed from 2.63 to 9.36 m/s,
so neither is an accepted repair. Initial-geometry audit found every adjacent
book pair starts with 0.4 mm nominal visual overlap and 1.9 mm collision-proxy
overlap. Oversized stacked proxies underneath a fixed extraction book are now
the concrete repair hypothesis. Two isolated diagnostics test exact-size proxies,
and exact-size proxies plus 0.2 mm initial inter-book clearance. All changed
sizes and corresponding pose/keyframe z offsets are recorded in remote
`geometry_repair_changes.json`. These change the physical configuration and
require a distinct dataset version and fresh boundary association if adopted;
old source prompts/boundaries must not be inherited silently. Original videos
remain untouched, and neither candidate is accepted or published.

The exact-proxy plus 0.2 mm clearance diagnostic removes the original persistent
extraction-book overlap (target pair maximum signed overlap -0.2 mm; zero frames
over 1 mm). Other pairs still reach 4.18 mm nominal-box overlap during motion,
so this is not a complete physical-quality pass. A separate original-resolution
ray-traced cam01 candidate is now rendering in `fullres_geometry_candidate` for
visual/state review; it is excluded from the active quota inventory. Source
configuration changes and old-boundary incompatibility remain explicit.

The local inventory watcher was found absent and restarted once after confirming
no live instance. Its script now holds a process-lifetime OS lock and retries
transport/process timeouts instead of exiting. The prior exit cause is unknown;
no timeout root cause was asserted. Remote render jobs were unaffected.

The full-resolution repaired cam01 candidate completed and decodes all 210 frames.
Its target-pair overlap remains absent across all saved states; 22 sampled frames
were inspected for object identity, scripted extraction and upper-book motion.
The candidate is still pending review of other contact intervals. Full-resolution
cam02/cam03 candidates are now running sequentially with the same declared
geometry correction and their own original camera configs. No candidate has
replaced a quota entry or inherited its old boundary/prompt binding. Local cam01
evidence: `visual_review/t18_fullres_candidate_review.json`.

Original cam02/cam03 runtime logs were now checked: both replay exactly cam01
trajectory SHA `07ce95a4da098818dcac6c19a6180820e29bb93e5ec74fc844579dad0a8c5d9e`.
Their physical defect is therefore shared; two additional SHA-bound rejections
are recorded with that replay proof (three videos from this trajectory total).
The repaired candidate's other-view launch initially referenced the legacy state
path; its failed receipts were kept, and retries now explicitly bind corrected
cam01 state SHA `3eeb1234e0f702a0ea1300df28bdfb5c7911ef93959fccd522323f91d91913d0`.
This preserves one trajectory across views instead of accidentally mixing states.

### 2026-10-29 GPU scale-out

The remaining unstarted sg88 tasks were partitioned once, with exact IDs and
upstream configuration hashes in `../release_72000_active/scaleout_assignment_20261029.json`
and `scaleout_config_bundle.json`. The old dispatcher was interrupted only in its
main loop; its five active workers drained normally. Do not restart that original
301-task dispatcher: 60 tasks now belong to other hosts.

* p25: `/data_cached/wangzijun_p25/t19_scaleout_20261029`, 30 trajectories,
  GPUs 1/2/3, at most two workers per GPU and six total, minimum 18,000 MiB free
  before each admission. Completed 36 videos before raising concurrency.
* p26: `/data2/wangzijun_p25/liyuhan/t19_scaleout_20261029`, 30 trajectories,
  GPUs 0/2/4/5, one worker each, minimum 18,000 MiB free. Missing source modules
  and incompatible OpenCV were repaired in this task's isolated asset/compat
  directories. Failed setup attempts are archived, not counted as renders.
* sg88: `t18_t19_resume_20261028/scaleout_20261029`, 25 remaining trajectories;
  receipts still go to the original root. GPUs 1/2 remain subject to 24,000 MiB
  admission. GPU utilization is already approximately 100 percent.
* p29: only approximately 3 GiB free per card at inspection; no work assigned.

Use `status.json` under these scheduler roots for live queues; the original
sg88 `tuning_status.json` is stale. `scripts/run_scaled_render_queue.py` holds
a scheduler lock and each worker claims its sample atomically. Completed receipts
are collected from p25, p26 and sg88 with host-specific source bindings.
The single existing local inventory watcher remains active. Integrity/frame-sheet
audit targets are now p25 380, p26 30, sg88 241 trajectories (651 total).
These checks do not grant visual or physical acceptance. p26 outputs remain
review-required and require their actual runtime provenance, like other new data.

#### 08:41 UTC follow-up: p26 visualizer crash and recovery

p26 subsequently failed five camera-1 jobs with renderer exit -11 (SIGSEGV)
at visualizer construction after simulation kernel compilation. No completed
video receipt was produced. Its scheduler exited; `REASSIGNED.json` prohibits
restarting this assignment. Failure logs and setup attempts remain on p26.
All 30 trajectories were moved to the working p25 renderer under
`/data_cached/wangzijun_p25/t19_p26_recovery_20261029`, with original sg88 config
snapshots and hashes preserved. This recovery queue allows two concurrent workers
on GPUs 1/2/3, each admitted only with 18,000 MiB free, alongside the six-worker
existing queue. This is a fallback, not a claim that p26 is successfully rendering.
Active inventory now collects the new p25 recovery root instead of p26.
Integrity/frame-sheet targets are p25 410 and sg88 241; the idle p26 audit watcher
was stopped. Total assignment remains 651 trajectories without duplication.

#### 08:56 UTC follow-up

The first p25 scale-out queue finished all 90 videos without failed receipts.
Its freed resources now serve the p26 recovery queue: GPUs 0/1/2/3, eight total
workers, two per GPU, still requiring 18,000 MiB free before admission. Eight
active workers were verified; 18 recovery videos already completed.
The p25 audit replacement had lost a lock race and sg88's old audit script did
not support `--expected-count`. Both were repaired: p25 restarted after verifying
the prior process was absent, and sg88 now uses the current script at
`supplement_quality_20261028/audit_scaled.py`. No rendering jobs were restarted.
Quality approval remains separate from these integrity and evidence-sheet jobs.

At the 09:11 UTC follow-up, both render queues and both integrity auditors were
advancing without new failed receipts. Twelve actual frames from each repaired
T18 candidate cam02/cam03 were inspected; hashes, indices and findings are saved
in `../release_72000_active/visual_review/t18_candidate_other_views.json`.
Book identities remain recognizable in those samples; cam02 partially crops the
fallen red book, while cam03 covers it more widely. Remaining contact intervals
are still pending, so no candidate was admitted or substituted into inventory.

09:26 UTC: sg88 finished its 25-task scale-out queue and its full 241-trajectory
integrity audit (all integrity PASS, no physical acceptance implied). p25's
recovery reached 72 videos with zero failures. To admit its last three queued
tasks despite other users' GPU allocations, its free-memory threshold was lowered
to 14,000 MiB; concurrency remains capped at two workers per GPU/eight total.
Candidate T18 frames 70/72/74/76/78 were examined in all three views around the
remaining contact peak. Evidence and unresolved millimetre-scale contact limits
are saved in `visual_review/t18_candidate_contact74_review.json`; no acceptance
or inventory replacement was made.

### File completion confirmed at 09:59 UTC

Snapshot `20261029T094017Z` has all 72,000 quota entries, 3,600 per scene.
All 651 supplement trajectories (1,953 videos) finished; p25 audited 410 and
sg88 241 with integrity PASS. The inventory watcher exited normally after its
file-and-integrity completion condition; do not restart it or the render queues.
Run a single inventory refresh when new adjudications or replacement videos exist.

This is not usable-dataset delivery: strict current-round counts are 0 verified
usable, 70,167 pending review, 1,833 unusable, and 0 absent files. The pending
number includes 31,722 entries carrying historical acceptance, not current-round
approval. The unusable count includes 1,830 retired T19 videos and three confirmed
T18 penetration videos. Unique content hashes number 67,532; 72,000 quota entries
must not be described as 72,000 unique video contents. New prompt bindings and
quality replacements remain incomplete, and no new release was published.
The heartbeat now follows quality/provenance completion rather than rendering.

10:24 UTC quality follow-up: extended p25 contact-state audit from its old 350
trajectories to all 410 completed trajectories, including both scale-out roots.
Cached contact results now require matching video hashes and state path; prior
errors are retried. Started CPU-only contact-window evidence production for all
eligible dynamic-contact cases on both hosts in `supplement_full_contact_review_20261029`.
p25's launcher waits for the 410-result contact audit; sg88 uses its completed
241-result audit. Each sheet is tied to video hashes and includes initial/final
frames and the seven-frame window around the peak. This prepares review evidence,
not a physical pass; videos without recorded dynamic contacts need another review
route. Existing render jobs and the completed inventory watcher stay stopped.

10:39 UTC: sg88 evidence generation completed 241 groups without errors, giving
651 groups/1,953 camera sheets across both hosts. Visually inspected all three
views for T18 bg04/g02/contact_friction/p020 around frames 69-75. The logged
147.8 mm substep contact depth is not demonstrated by the saved images. Independent
proxy z-interval gaps at saved poses range from -0.464 to +0.084 mm; negative gap
alone does not prove 3D intersection, and these poses are not the contact substep.
The sample remains pending, with SHA-bound visual and geometric notes at
`visual_review/T18__bg04_library_shelf__g02_mars__contact_friction__p020_review.json`.
No quality counts were upgraded or videos rejected from contact depth alone.

11:02 UTC provenance follow-up: built
`../release_72000_active/supplement_prompt_input_bindings.jsonl.gz` for all 1,953
completed videos/651 groups, joining exact video hashes, per-camera runtime config
bindings, original control declarations and recorded timeline diagnostics. Original
config/control hashes agree for all groups. 1,050 videos directly match their
original cam01 source hash; 903 use relocated sg88-source snapshots and still need
a transitive source-content check before original prompt inputs can be inherited.
This is a prompt-input manifest, not generated or tokenizer-verified prompt text;
prompt coverage and quality counts remain unchanged. Summary and artifact hash:
`supplement_prompt_input_bindings_summary.json` beside the manifest.

11:17 UTC: fetched and hash-verified all 301 relocated cam01 source snapshots.
`scripts/verify_supplement_source_relocation.py` compares every JSON value against
the original source records. Seventeen groups (51 videos) differ only in relocated
paths. The other 284 groups (852 videos) additionally point to a recovered
background manifest, so their source status remains `SOURCE_CHANGE_REQUIRES_REVIEW`.
No numeric/control changes were found in those source JSON comparisons. The
original library manifest path on p25 is absent; its recovered counterpart exists.
Background equivalence and asset bytes are not yet established. Proofs preserve
each changed path and source hash in `supplement_source_relocation_proofs.json`.
This closes 51 source joins, not 51 physical-quality reviews or prompt releases.

## Author acceptance and upload authorization, 2026-10-29

The author explicitly stated they reviewed the newly rendered 1,953 videos and
requested accepting all of them, organizing the dataset and uploading it.
`visual_review/author_acceptance_20261029.jsonl` binds this instruction to each
video SHA. `USABLE_AUTHOR_ACCEPTED` is separate from assistant-certified checks;
no per-check results were invented. Prior T18 diagnostic rejections remain visible
but are superseded for admission by author acceptance. Old retired T19 remains
excluded. Current counts: author-accepted 1,953; historical acceptance 31,722;
other pending 36,495; retired 1,830; absent files zero. Three admission regression
checks passed (author override, retired exclusion, integrity-failure exclusion).

Publication target: `phy2/phydataset/releases/72000_author_review_20261029`.
Five host/scene shards package 2,913 videos (1,953 new and 960 T14S); the 69,087
baseline entries reference existing pinned source releases. The full manifest
retains all 72,000 slots and their distinct quality states. Source/trajectory
metadata, author instruction and prior diagnostic decisions are included.
English prompts not yet built and recovered-background limitations are explicitly
documented. No Core100, split, old release or critical value is overwritten.

Upload state: local `../release_72000_active/upload_live.log`, and p25
`/data_cached/wangzijun_p25/author_release_20261029/upload_progress.json`.
Only that root's `PUBLISHED.json` after remote LFS hash verification confirms
publication; a running uploader does not. Check existing processes before retry.

Release validation additionally found 960 baseline Isaac T20 entries with only
local p25 paths. They are now packaged as a sixth shard, retaining their original
quality state. Final upload scope is 3,873 videos: 1,953 new author-approved,
960 T14S, and 960 local-only T20. The other 68,127 entries have pinned original
release references. All 72,000 download references and unique source/camera keys,
the 20 quotas and approval/exclusion counts passed release checks. The six-shard
uploader replaces the initial five-shard attempt before catalog publication.

11:54 UTC upload recovery: the proxied LFS S3 upload repeatedly hit TLS EOF.
Direct HTTPS to the S3 data host was tested successfully (403 without credentials,
confirming connectivity); direct Hugging Face API still fails. The uploader now
keeps HF API through the SSH proxy but uses NO_PROXY for `.amazonaws.com`.
Stopped only the failed release uploader, verified its exit and resumed through
`scripts/publish_author_release_remote.py`. Actual socket counters show roughly
98 MB acknowledged directly to S3 after the first 30 seconds, rather than a
proxy-only loop. Current PID is in UPLOAD_ACTIVE.json; do not rely on historical
PIDs. Logs redact URLs and library URL-bearing warnings are suppressed.
No shard commit or completed publication is claimed until the hash receipts exist.

13:00 UTC upload recovery: four shards (3,150 videos) were remotely hash-verified.
The previous uploader exited during sg88/T18 multipart completion with a TLS
ConnectError, after transferring parts. Added bounded retries around the small
completion POST so transient API failures do not immediately retransmit the
whole archive. Confirmed previous PID exited, then resumed once; existing
matching shards are skipped. Publication remains incomplete until PUBLISHED.json.

Publication completed: revision `30097d99582f63ded517f3308a1c297ce1fe9791` in `phy2/phydataset`.
All six shards (3,873 videos) passed remote LFS SHA-256 and size checks;
14 metadata files were confirmed at the published revision. Local receipt:
`../release_72000_active/publication_receipt_20261029.json`. The manifest indexes
72,000 entries, including retired/pending states; this is not all-video quality
approval. English prompt variants remain missing for 2,913 entries (T14S 960,
T18 1,143, T19 810), as disclosed in the released README. Upload follow-up ends.

Prompt completion 2026-10-29: built all 2,913 missing video prompt bindings
(T14S 960, T18 1,143, T19 810), 8,739 new texts. Full catalog has 72,000
three-variant records / 216,000 texts; 69,087 existing prompt rows retained.
Shared v7 renderer and pinned tokenizers validated each new text, with EOS and
no truncation; maximum LTX/CogVideoX 128 tokens, Wan 189. Exact-hash patches
are in `../release_72000_active/prompt_completion_20261029/`. T18 kinematic
withdrawal and T14S spring controls are disclosed. T19 restitution sweeps
include analytic contact-impulse disclosure. Seven regression checks passed
(outcome exclusion, motion/control mismatch rejection, renderer hash, inventory
patch identity). Upload remains pending until that folder PUBLISHED.json.
Current user chose existing T19 inputs; no rerender or quality auto-approval.

Prompt-complete catalog published and all 12 remote files hash/size verified:
`phy2/phydataset@ced0cf6057a3281f19ea961d63132bffd2d81560`, prefix `releases/72000_prompt_complete_20261029`.
`../release_72000_active/ACTIVE_PROMPTS.json` binds the complete catalog and
exact-media patch for later inventory refreshes. All 72,000 entries have three
prompts. T19 uses existing media. Quality statuses and Core100 v6 remain as
recorded; this prompt publication does not independently approve retired media.

Standardized browse/catalog release 2026-10-29 completed at
`phy2/phydataset@9f1215d077a66d1bb4cb7c4997ef236b5d46cf72`. Added the missing `data/T20`
browse entry with 3,600 exact-source bindings (Genesis 2,640; Isaac 960).
All 20 quota directories now use consistent README/INDEX/per-engine indexes;
native T14S remains distinct. Added collision-free canonical IDs, filenames and
materialized paths for all 72,000 records. A streaming archive-aware download
script writes that layout and verifies each video SHA. Original archive members
and source IDs remain intact; no physical media rename or prompt rewrite claimed.
All 110 remote files passed hash/size verification; live directory listing and
T20 INDEX.json were checked. Four download safety/integrity checks passed.
Local active pointer: `../release_72000_active/ACTIVE_CATALOG.json`.

User-authorized review directory removal completed 2026-10-29.
Removed exactly 16 files under top-level `review/` from main at
`phy2/phydataset@f9aaa8064ecb47286fa4d0298e780ef80ecedaef`, and removed its active
README/DIRECTORY navigation section. All 72,000 manifest rows checked: zero
download references to review/. Before deletion created verified backup branch
`snapshot-before-review-removal-20261029` at 9f1215d077a66d1bb4cb7c4997ef236b5d46cf72.
Git trees for data, benchmarks, annotations, assets, scenes, releases and archive
are unchanged. Receipt: `../release_72000_active/review_removal_20261029/REMOVED.json`.
This removes old review media from main; it changes no per-video quality label.

2026-10-29 full publication audit completed at `phy2/phydataset@670213c55a94c6583627bf467a329f65897459aa`.
Earlier zero-review-reference assertions missed full HTTPS URLs stored as
`download.path`; this was a normalization bug, not missing source bytes.
Corrected 3,840 path bindings, 3,600 temporal-unit prompt records / 10,800 texts,
and 960 Isaac T19 admission records explicitly excluded by their source batch.
Current counts: usable 32,868 (30,915 source acceptance + 1,953 author acceptance),
pending 36,342, excluded 2,790. No automatic visual approval was granted.
Consolidated all 69,210 non-retired media records to current scene/engine
directories as 54,354 files/archives; every destination LFS SHA verified.
2,790 retired records retain source bindings only; top-level review remains absent.
T01 now has real genesis/ and isaac/ media directories. All 157 card/catalog
files verified remotely. Core100/benchmarks and annotation trees unchanged.
README and project introduction describe current state, with no chronology.
Visibility remains private and authorization unchanged at author request.
Report: docs/internal/PUBLICATION_CHECK_20261029.md. Full 72k visual approval and a
verified final training-source-group exclusion manifest remain incomplete.


## Active T19 hash-bound re-review (2026-10-29 author authorization)

Current catalog: `../release_72000_active/ACTIVE_CATALOG.json`. Current totals:
32,877 usable (30,915 original source acceptance, 1,953 author acceptance, 9
visual/state review), 38,163 pending, 960 retired, zero missing.

All 1,830 recovered Genesis videos completed full decode and exact SHA checks.
The 610 original metadata records contain 10,512 published parameter facts; all
match. Actor identities and all saved pose/motion values are stable/finite.
Only 9 videos have completed dense event-frame review; 1,821 are still awaiting
visual/physical adjudication. Full visual review is NOT complete. The retirement
gate is superseded only by exact-hash authorized per-video decisions.

Isaac: 369 repair candidate files found, 138 identical to retired inventory and
231 different hashes, not a complete accepted replacement. All 960 old Isaac
T19 records remain retired. No candidate was substituted or deleted.

Evidence and individual decisions are published under
`releases/72000_release_candidate_20261029/t19_review/`. All 1,830 recovered
Genesis media objects are now in canonical T19/genesis directories, with every
destination LFS hash verified. Copying media is not quality approval.

One conflicting retry triplet was kept outside the active inventory using the
exact published hashes; details are in `unselected_retry_receipts.json`. Neither
render was deleted. Frozen Core100, license and visibility are unchanged.


## Qualified Isaac T19 enabled (latest author request)

Three existing videos from `T19__bg03_neutral_studio__g01_moon__value_0.14__global_16`
are enabled following dense motion-frame RGB review, full decode, exact source
input/QA/MP4 receipt matching and parameter comparison. They show one can
bypassing the target. This is an existing triplet, not a newly rendered batch.
Original prompts, video hashes, parameters and canonical IDs are unchanged.
The other 957 Isaac T19 records remain retired. State-file recovery and critical
truth are not granted by this visual admission. Frozen Core100 is unchanged.

Current totals: 32,880 usable (30,915 source acceptance + 1,953 author acceptance +
12 individually reviewed videos), 38,163 pending, 957 retired, zero missing.
The current published manifest and exact revision are selected by ACTIVE_CATALOG.json.
Review evidence: `isaac_admission_20261029/` inside the current release.
