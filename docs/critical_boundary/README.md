# Critical-boundary evaluation

This directory contains the protocol and user-facing workflow for the critical-boundary benchmark module. The raw videos, model outputs, intermediate annotations, and machine-specific audit files live under the local `review/` directory and are intentionally excluded from Git.

## Start here

- [Protocol and metric definitions](CRITICAL_BOUNDARY_PROTOCOL.md)
- [Setup and command workflow](../../BOUNDARY_EVALUATION.md)
- [Two-stage quality screening and event judging](TWO_STAGE_PIPELINE.md)
- [Failure handling and denominator rules](FAILURE_HANDLING.md)
- [Window-aware event judging](WINDOW_AWARE_JUDGE.md)
- [Dual-judge procedure](DUAL_JUDGE.md)
- [T15 protocol](T15_EVALUATION_PROTOCOL.md)
- [H3/T15 handoff](H3_T15_HANDOFF.md)
- [Triage rules](TRIAGE_V2.md)
- [Historical search-recovery status](SEARCH_RECOVERY_STATUS.md)
- [Group-meeting slide notes](GROUP_MEETING_SLIDE_NOTES.md)

## Reproducible reference records

- [T04 Genesis release distance example](results/T04_RELEASE_DISTANCE_BINDING.json): three published samples bound to a pinned repository snapshot and a locally measured transition interval. The record explicitly marks live Hugging Face HEAD verification, repeatability, and visual admission as pending.

Generated artifacts are not automatically publication-ready data. Check the source revision, fixed context, event truth, parameter normalization, repeatability, and visual observability before promoting a record to the formal NearAcc denominator.
