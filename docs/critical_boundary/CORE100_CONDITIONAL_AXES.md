# Core100 conditional directions

`annotation_site/resources/core100_distance_bindings.json` remains the unified100-case entry. Its v2 schema supports explicit conditional directions for a joint-input case. The v1 reader remains supported for archived records.

T14_C03 retains its original video hash, physical inputs, event labels, five-second window and old throat-width coordinate. Two verified directions are now present in `conditional_axes`:

| Direction | Source value | Event | Verified interval |
|---|---:|---|---|
| marker_initial_yaw_deg | 4.5 degrees | passed_channel | [5.1796875, 5.1875] |
| marker_initial_yaw_deg | 4.5 degrees | terminal_contact_after_full_exit | [5.171875, 5.1796875] |
| trigger_impulse_magnitude_Ns | 0.0284148 N s | passed_channel | [0.023184263671875, 0.0232062890625] |
| trigger_impulse_magnitude_Ns | 0.0284148 N s | terminal_contact_after_full_exit | [0.0232833779296875, 0.023294390625] |

The yaw and impulse scales are [0,8] degrees and [0.012546,0.0351] N s respectively. They remain separate. No minimum over directions is presented as a global nearest boundary.

For a multi-direction case, `bind_answer(..., axis='marker_initial_yaw_deg')` or an explicit `boundary_axis` is required. Omitting the direction raises an error rather than returning a fabricated not-applicable judgment. An old answer carrying a throat-width theta is rejected if it is passed as an angle answer. Original event labels, reference admission and historical scores are unchanged.

Evidence and the before-integration v1 registry are retained in `review/core100_remaining15_followup_20261031/`. Endpoint state/config hashes, source repeat tracks, source physical specifications, solver settings and observation clocks were checked. CPU64 is a recorded numerical variant; the original GPU32 seed is not independently attested by the retained metadata. Numerical completion does not grant formal media-quality admission.

New T11 actual-force searches are supplemental directions, not relabeled original nominal-speed branches. Their original four-direction observations and source parameters are retained. They remain outside the unified ready set until their own witness and source/event/window checks complete.

This change is local only. It does not upload to HF, update the live annotation server, regenerate model judgments, or replace old model scores.

## Original T11 G_global family

T11_C01–C03 originate from `G_global_06`. Their original family varies five
inputs jointly: nominal driver command, relay gap, edge margin, relay mass and
case friction. The A–D single-input sweeps and an isolated precontact-force
sweep do not replace this family.

The `original_G_global_path` direction follows the eight released G_global
settings in their original order. For each input, let its scale be its range
across these eight settings. Segment length is the Euclidean length of the
five range-normalized input changes. The path coordinate is cumulative segment
length divided by the total path length; its domain is [0,1]. Interpolation
inside a segment changes all five inputs together. G_global_06 has coordinate
0.7209977526762721.

This definition gives a conditional distance **along the original joint path**.
It does not give a nearest boundary in the full parameter space or isolate one
input's causal effect. Near/Mid/Far use that declared coordinate and must report
the direction explicitly. The full source vector remains in `theta`; the path
coordinate is stored inside the selected conditional axis.

Counterfactual probes retain the frozen source seed, solver, geometry context
and event window. The source setting is an exact no-op. The controlled physics
of all eight nodes was checked against the original released configurations.
The reference events and five-second window remain unchanged. Source/reference
hashes and endpoint evidence must pass before a result is admitted; a planned
or uniform-label scan is not a boundary. Supplemental precontact-force results
remain separate and do not count as recovery of the G_global family.

## T05_C01: full passage only

The author confirmed on 2026-11-01 that this case accepts only the
`gate_passage` boundary. Reaching the entry or contacting a guide is diagnostic
information and cannot complete this case. The original friction input and
frozen observation window remain unchanged.

Use the released full-passage predicate: the maximum phone-center x coordinate
in the registered continuation window must reach
`geometry.phone_center_full_pass_x_m` (0.32390548959764603 m for this source).
Read the same registered prefix from a longer simulation; do not extend the
evaluation window to obtain a positive result. No entry-stage label replaces
the original passage label.

Before a new friction probe can witness a boundary, check the simulator's
effective phone and tray friction coefficients against the requested value.
A fallback material value cannot serve as the negative or positive endpoint.
Failed interventions are retained as diagnostics, while valid probes from the
same scan remain eligible. A valid normalization range without an opposite
event pair still leaves the case incomplete.

## T10_C01 and T10_C02: support-pen displacement only

The author confirmed on 2026-11-01 that these cases retain
`support_pen_displacement_reaches_source_threshold`. The predicate is the
maximum Euclidean displacement of `t10_support_pen` from its frame-4 position,
over frames 5 through 209, reaching the released 0.04 m threshold. The physical
continuation window is 4.1 seconds. Folder support loss is a separate event and
does not replace this target.

The original direction is `support_x`, with normalization range [0.08,0.217] m.
Follow its released coupled geometry recipe: support position, folder angle and
tape aim must remain consistent. A geometrically invalid configuration is not
a negative event endpoint. Valid extension probes retain the original
normalization range; the larger scan must not manufacture Near membership.
Use the support position actually written by the recipe when it rounds the
requested value.

All original records and continuation probes remain available. A uniform-label
scan does not supply a boundary or justify changing the case to not applicable.
An old audit for a supported book and wooden rod does not define the event for
this released folder-and-pen scene. An isolated rolling-speed intervention also
does not complete the original support-position direction.

## T11 original friction component

`case_friction_coefficient` is an original component of the released G_global
input vector. A conditional search varies this component alone, preserving the
other four inputs, geometry, mass settings, forces, solver and observation
window. Its scale remains the original component range [0.04,0.22], including
when valid material-domain extension points are tested. The simulator's actual
friction readback must agree with each requested endpoint.

This direction is stored separately from `original_G_global_path` and the
supplemental precontact-force direction. Adding its conditional interval does
not claim recovery of the original ordered G path or a global nearest boundary.
Reference vectors, event labels and existing source-axis coordinates are kept.

## Endpoint repetition and unresolved results

A refined single-run interval remains a local candidate when its endpoint
labels disagree across repeated original-renderer executions. Store each
execution's state/config hashes, physical GPU identity, actual initialization
seed, solver, friction readback and original event window. An absent numerical
seed remains absent; preserving `None` must not be described as replaying a
fixed numerical seed. Run a matched-device control before attributing a change
to GPU identity. Do not infer a unique threshold from a nonmonotonic response.

The registry retains the original interval and all repeated evidence. The
answer-binding interface returns an unavailable boundary for a discordant or
explicitly pending endpoint check; it keeps event truth and ordinary event
denominators intact. Matching endpoint labels establish only the measured
local repeatability, without granting physical quality or reference admission.

For the six remaining original directions, the completed-state readback
separately records the verified point count and observed event-label set.
Uniform labels leave the boundary unresolved; they neither manufacture a
threshold nor change a case to not applicable. T05 full passage, T10's 0.04 m
pen-displacement event, frozen prompts and source input files remain unchanged.
