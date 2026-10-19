"""Bind T04 stack-sliding interval distances to the pinned published Genesis release.

This does not claim that the pinned inventory revision is the live Hugging Face
HEAD. Live HEAD access is unavailable from the audited environment; the output
records that limitation explicitly.
"""
import json
from pathlib import Path

ROOT = Path("review/scene_family_completion_20261018")
SPLIT = Path("../dataset_splits_v2/huggingface/genesis/train.jsonl")
REPO = "phyeditingvideo/Phyediting"
REVISION = "e2f2e4cdff26cdc26a6dc4ae545d589fd9005de6"
BRACKET = [0.1225, 0.13125]
SPAN = 0.15
IDS = {
    "T04F880V1__bg01_home_ase__g01_moon__cf_stack_sliding_minus__rep01",
    "T04F880V1__bg01_home_ase__g01_moon__cf_stack_sliding_star__rep01",
    "T04F880V1__bg01_home_ase__g01_moon__cf_stack_sliding_plus__rep01",
}


def norm_interval(theta):
    a, b = BRACKET
    low = max(a - theta, theta - b, 0.0) / SPAN
    high = max(abs(theta - a), abs(theta - b)) / SPAN
    if high <= 0.05:
        label = "near"
    elif low > 0.05 and high <= 0.15:
        label = "mid"
    elif low > 0.15:
        label = "far"
    else:
        label = "ambiguous"
    return [low, high], label


def main():
    inv = {}
    with SPLIT.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("sample_id") in IDS:
                inv[row["sample_id"]] = row
    if set(inv) != IDS:
        raise RuntimeError(f"expected 3 Genesis release rows; got {len(inv)}")

    measured = {
        r["sample_id"]: r
        for r in json.loads((ROOT / "t04_measured_published_events.json").read_text(encoding="utf-8"))
        if r.get("sample_id") in IDS and r.get("repo_id") == REPO and r.get("revision") == REVISION
    }
    if set(measured) != IDS:
        raise RuntimeError("measured event records do not match the pinned Genesis release")

    out = []
    for sample_id in sorted(IDS):
        row, state = inv[sample_id], measured[sample_id]
        video = row["videos"]["cam01"]
        theta = float(state["theta"])
        if row["revision"] != REVISION or row["repo_id"] != REPO:
            raise RuntimeError(f"inventory source mismatch: {sample_id}")
        if int(state["events"]["stack_motion"]) not in (0, 1):
            raise RuntimeError(f"invalid event label: {sample_id}")
        d, bucket = norm_interval(theta)
        out.append({
            "sample_id": sample_id,
            "engine": "genesis",
            "repo_id": REPO,
            "pinned_published_revision": REVISION,
            "release": row.get("release"),
            "camera": "cam01",
            "video_path": video["path"],
            "video_sha256": video["sha256"],
            "theta_bottom_book_friction": theta,
            "target_event": "stack_motion",
            "reference_label": int(state["events"]["stack_motion"]),
            "reference_state_sha256": state["sha256"],
            "observed_transition_interval": BRACKET,
            "normalized_absolute_distance_interval": d,
            "distance_bucket": bucket,
            "normalization_domain": [0.05, 0.20],
            "normalization_span": SPAN,
            "nearacc_formally_eligible": False,
            "binding_status": "bound_to_pinned_published_genesis_snapshot",
            "live_huggingface_head_verified": False,
            "live_head_check_note": "HF repo is private; configured remote hosts had no outbound network in this audit, so a newer live HEAD could not be excluded.",
            "boundary_limitations": [
                "observed local bracket, not a point estimate",
                "one replay per added probe; repeatability is unverified",
                "RGB/video visual admission is pending",
            ],
        })

    binding_path = ROOT / "t04_hf_release_distance_binding.json"
    binding_path.write_text(json.dumps({
        "source_scope": "Genesis only; Isaac supportfix release is a distinct engine/version and is not mixed into this binding",
        "repo_id": REPO,
        "pinned_revision": REVISION,
        "live_head_verified": False,
        "target_event": "stack_motion",
        "observed_transition_interval": BRACKET,
        "normalization": {"domain": [0.05, 0.20], "span": SPAN},
        "distance_rule": "distance from theta to interval [a,b], normalized by span; report lower/upper bounds",
        "records": out,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    reg_path = ROOT / "t04_probe_distance_registry.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    by_id = {r["sample_id"]: r for r in out}
    for record in reg:
        b = by_id.get(record["sample_id"])
        if not b:
            continue
        if abs(float(record["theta"]) - b["theta_bottom_book_friction"]) > 1e-12:
            raise RuntimeError(f"theta mismatch: {record['sample_id']}")
        record["published_source_binding"] = {
            "repo_id": REPO,
            "pinned_revision": REVISION,
            "release": b["release"],
            "camera": "cam01",
            "video_path": b["video_path"],
            "video_sha256": b["video_sha256"],
            "live_head_verified": False,
        }
        record["computed_distance"] = {
            "status": "resolved_interval_bounds",
            "bin": b["distance_bucket"] if b["distance_bucket"] != "ambiguous" else None,
            "normalized_absolute_interval": b["normalized_absolute_distance_interval"],
            "boundary_interval": BRACKET,
            "normalization_span": SPAN,
        }
        record["status"] = "interval_distance_bound_to_pinned_hf_genesis_release_live_head_unverified"
        record["computed_distance_reference"] = "pinned_hf_genesis_release_plus_observed_backend_transition_interval"
        record["original_solver_theta_star"] = None
        record["formal_nearacc_eligible"] = False
        record["live_huggingface_head_verified"] = False
        record["binding_evidence"] = str(binding_path.resolve())
        record["blocking_reasons"] = [
            "live_huggingface_head_not_verified",
            "new_interval_repeatability_pending",
            "reference_rgb_observability_pending",
        ]
    reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps([{
        "sample_id": r["sample_id"],
        "theta": r["theta_bottom_book_friction"],
        "label": r["reference_label"],
        "normalized_distance_interval": r["normalized_absolute_distance_interval"],
        "bucket": r["distance_bucket"],
        "video_sha256": r["video_sha256"],
    } for r in out], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
