from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from scripts.phyediting_joint_split import CHECKS, audit_bindings, load_training_split, materialize, training_sampling_weights, write_outputs

PLAN = json.loads((Path(__file__).resolve().parents[1] / "docs/joint_split_v3/plan.json").read_text())


def row(rid, event="T01", engine="genesis", group=None, bg="bg01"):
    return {"record_id": rid, "sample_id": f"{event}__{bg}__{rid}", "event_id": event,
            "engine": engine, "leakage_group_id": group or rid, "video_references": 3,
            "release_status": "published_release_qa_not_reaudited"}


def evidence(r):
    return {"record_id": r["record_id"], "identity": {"sample_id": r["sample_id"], "engine": r["engine"],
            "revision": "pinned", "release": "formal"}, "checks": {k: True for k in CHECKS},
            "videos": {c: {"path": f"/{r['record_id']}/{c}.mp4", "sha256": hashlib.sha256(f"{r['record_id']}/{c}".encode()).hexdigest()}
                       for c in ("cam01", "cam02", "cam03")},
            "state": {"path": "/state.json", "sha256": "b" * 64},
            "sampling": {"kind": "global", "family_id": r["record_id"], "propagation_depth": 1},
            "receipt": {"path": "/proof.json", "sha256": "c" * 64}}


def test_views_backgrounds_and_engines_stay_in_one_component():
    rows = [row("a", group="same"), row("b", engine="isaac", group="same", bg="bg02")]
    rr, _ = materialize(PLAN, rows)
    assert len({r["component_id"] for r in rr}) == len({r["split"] for r in rr}) == 1


def test_shared_media_connects_otherwise_unrelated_groups():
    a, b = row("a"), row("b", engine="isaac")
    ea, eb = evidence(a), evidence(b); eb["videos"]["cam02"]["sha256"] = ea["videos"]["cam01"]["sha256"]
    rr, _ = materialize(PLAN, [a, b], [ea, eb])
    assert rr[0]["component_id"] == rr[1]["component_id"]


def test_cross_ood_pool_conflict_quarantines_entire_group():
    rr, _ = materialize(PLAN, [row("a", "T03", group="same"), row("b", "T11", group="same")])
    assert {r["split"] for r in rr} == {"quarantine"}
    assert len(rr) == 2


def test_unverified_scan_not_randomly_assigned_by_point_number():
    a, b = row("p001", "T06"), row("p002", "T06")
    rr, _ = materialize(PLAN, [a, b])
    assert {r["split"] for r in rr} == {"pending"}
    assert all("missing_versioned_asset_and_qa_evidence" in r["release_blockers"] for r in rr)


def test_touching_numeric_intervals_merge_across_engines():
    a, b = row("a", "T06"), row("b", "T06", engine="isaac")
    ea, eb = evidence(a), evidence(b)
    for e, low, high, val, iid in [(ea, 0, 1, .4, "low"), (eb, 1, 2, 1.5, "high")]:
        e["scan"] = dict(parameter="speed", unit="m/s", value=val, low=low, high=high,
                         interval_id=iid, family_id="real-configuration", controls_sha256="d"*64,
                         boundary_guards_reviewed=True)
    rr, _ = materialize(PLAN, [a, b], [ea, eb])
    assert len({r["component_id"] for r in rr}) == 1
    assert not any(r["split"] == "pending" for r in rr)


def test_metric_exposure_closes_group_but_never_drops_ood():
    a, b = row("a", "T03", group="same"), row("b", "T03", group="same")
    rr, _ = materialize(PLAN, [a, b], exposure=[("genesis", a["sample_id"])])
    assert len(rr) == 2 and all(r["metric_development_group_exposed"] for r in rr)
    assert {r["split"] for r in rr} == {"test_ood_1"}


def test_row_order_cannot_change_assignments():
    rows = [row(str(i), engine="isaac" if i%2 else "genesis", bg=f"bg0{1+i%4}") for i in range(80)]
    a, _ = materialize(PLAN, rows); b, _ = materialize(PLAN, list(reversed(rows)))
    assert a == b
    assert {r["split"] for r in a} == {"train", "val", "test_id"}


def test_candidate_cannot_be_loaded_or_frozen_as_ready():
    rr, summary = materialize(PLAN, [row("a")])
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "candidate"; write_outputs(out, rr, summary, [])
        with pytest.raises(ValueError, match="not a training-ready"):
            load_training_split(out, "train")
        with pytest.raises(ValueError, match="Release blocked"):
            write_outputs(Path(tmp) / "release", rr, summary, [], freeze=True)
        assert not (Path(tmp) / "release").exists()


def test_complete_hashed_receipt_freezes_and_detects_mutation():
    r = row("a"); e = evidence(r)
    small_plan = deepcopy(PLAN)
    small_plan["video_targets"] = {engine: {event: 3 if engine == "genesis" and event == "T01" else 0
                                           for event in PLAN["events"]} for engine in PLAN["video_targets"]}
    with tempfile.TemporaryDirectory() as tmp:
        proof = Path(tmp) / "receipt.json"; proof.write_text(json.dumps({k:v for k,v in e.items() if k!='receipt'}))
        e["receipt"] = {"path": str(proof), "sha256": hashlib.sha256(proof.read_bytes()).hexdigest()}
        rr, summary = materialize(small_plan, [r], [e]); out = Path(tmp) / "release"
        write_outputs(out, rr, summary, [], freeze=True)
        split = rr[0]["split"]; assert len(load_training_split(out, split)) == 1
        with pytest.raises(ValueError, match="immutable"):
            write_outputs(out, rr, summary, [], freeze=True)
        (out / (split + ".jsonl")).write_text("\n")
        with pytest.raises(ValueError, match="content changed"):
            load_training_split(out, split)


def test_boolean_claims_without_actual_receipt_cannot_freeze():
    r = row("a"); small_plan = deepcopy(PLAN)
    small_plan["video_targets"] = {engine: {event: 3 if engine == "genesis" and event == "T01" else 0
                                           for event in PLAN["events"]} for engine in PLAN["video_targets"]}
    rr, summary = materialize(small_plan, [r], [evidence(r)])
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="receipt unavailable"):
            write_outputs(Path(tmp), rr, summary, [], freeze=True)


def test_capacity_targets_do_not_fabricate_missing_rows():
    rr, summary = materialize(PLAN, [row("a", "T11")])
    assert summary["registered_video_references"] == 3 and len(rr) == 1
    assert rr[0]["split"] == "test_ood_2"


def test_conflicting_or_orphan_evidence_is_rejected():
    a = row("a"); e = evidence(a)
    with pytest.raises(ValueError): materialize(PLAN, [a], [e, e])
    bad = deepcopy(e); bad["record_id"] = "unknown"
    with pytest.raises(ValueError): materialize(PLAN, [a], [bad])


def test_feasible_background_and_event_coverage_uses_whole_groups():
    rows = [row(f"{group}-{bg}", group=str(group), bg=f"bg0{bg}") for group in range(5) for bg in range(1, 5)]
    rr, summary = materialize(PLAN, rows)
    for group in range(5):
        assert len({r["split"] for r in rr if r["leakage_group_id"] == str(group)}) == 1
    assert all(len(v["splits_present"]) == 3 for v in summary["coverage"].values())


def test_missing_planned_event_blocks_formal_freeze():
    r = row("a"); rr, summary = materialize(PLAN, [r], [evidence(r)])
    assert "genesis:T13" in summary["missing_target_event_engine_pairs"]
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="Release blocked"):
            write_outputs(Path(tmp), rr, summary, [], freeze=True)


def test_sampling_strata_need_evidence_and_keep_group_coverage():
    rows = [row(str(i)) for i in range(10)]
    ev = [evidence(r) for r in rows]
    for i, e in enumerate(ev): e["sampling"]["kind"] = "critical" if i % 2 else "global"
    rr, summary = materialize(PLAN, rows, ev)
    for kind in ("global", "critical"):
        assert len(summary["coverage"]["event_kind:T01:" + kind]["splits_present"]) == 3
    del ev[0]["sampling"]
    rr, _ = materialize(PLAN, rows, ev)
    assert "missing_verified_sampling_kind_family_or_depth" in rr[0]["release_blockers"]


def test_actual_link_receipt_is_required_at_freeze():
    a, b = row("a"), row("b"); ev = [evidence(a), evidence(b)]
    small = deepcopy(PLAN)
    small["video_targets"] = {engine: {event: 6 if engine == "genesis" and event == "T01" else 0
                                       for event in PLAN["events"]} for engine in PLAN["video_targets"]}
    with tempfile.TemporaryDirectory() as tmp:
        for e in ev:
            p = Path(tmp) / (e["record_id"] + ".json")
            p.write_text(json.dumps({k:v for k,v in e.items() if k != "receipt"}))
            e["receipt"] = dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        link = dict(record_ids=["a", "b"], receipt_path=str(Path(tmp) / "absent.json"), receipt_sha256="f"*64)
        rr, summary = materialize(small, [a,b], ev, links=[link])
        with pytest.raises(ValueError, match="Linked-source receipt unavailable"):
            write_outputs(Path(tmp) / "release", rr, summary, [], freeze=True)
        assert not (Path(tmp) / "release").exists()


def test_independent_binding_audit_rejects_split_group_mutation():
    rr, _ = materialize(PLAN, [row("a", group="same"), row("b", group="same")])
    rr[1]["split"] = "val" if rr[0]["split"] != "val" else "train"
    with pytest.raises(ValueError, match="Cross-split binding conflict"):
        audit_bindings(rr)


def test_balanced_sampler_does_not_overweight_large_event_or_depth(monkeypatch):
    rows = [row(str(i), "T01" if i < 10 else "T02") for i in range(12)]
    for i, r in enumerate(rows):
        r["asset_evidence"] = evidence(r)
        r["asset_evidence"]["sampling"].update(family_id="one", propagation_depth=0 if i < 9 else 1)
    monkeypatch.setattr("scripts.phyediting_joint_split.load_training_split", lambda directory, split: rows)
    weights = training_sampling_weights("unused")
    assert sum(weights.values()) == pytest.approx(1.)
    assert sum(weights[r["record_id"]] for r in rows if r["event_id"] == "T02") == pytest.approx(.5)
    assert sum(weights[str(i)] for i in range(9)) == pytest.approx(.25)


def test_verified_critical_family_binds_branches_without_optional_alias():
    a,b=row("minus"),row("plus",engine="isaac")
    ev=[evidence(a),evidence(b)]
    for e in ev:e["sampling"].update(kind="critical",family_id="paired-real-family")
    rr,_=materialize(PLAN,[a,b],ev)
    assert rr[0]["component_id"]==rr[1]["component_id"]
