"""Materialize joint v3 group assignments and enforce evidence before release.

Routing-only inputs produce explicit candidate manifests, never a training-ready
release. No network, video generation, estimator changes or score selection.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from scripts.phyediting_joint_plan_audit import validate_plan

SPLITS = ("train", "val", "test_id", "test_ood_1", "test_ood_2")
CHECKS = ("media_decode_and_sync", "state_time_units_objects", "runtime_parameters",
          "event_labels", "visual_physical_qa", "aliases_duplicates_reviewed",
          "cross_engine_mapping_reviewed")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def scan_required(row, plan):
    return (row["event_id"] in plan["continuous_scan_review_events"]
            or row.get("release_status") == "legacy_scan_not_52800_contract")


def scan_key(evidence):
    """Require numerical provenance; p001 is never treated as a numeric value."""
    s = evidence.get("scan", {})
    required = ("parameter", "unit", "value", "low", "high", "interval_id", "family_id", "controls_sha256")
    if not all(k in s for k in required) or not is_sha(s.get("controls_sha256")):
        return None
    if not s["parameter"] or not s["unit"] or not s["family_id"] or not s["interval_id"]:
        return None
    try:
        low, value, high = map(float, (s["low"], s["value"], s["high"]))
        if not (-float("inf") < low <= value <= high < float("inf")):
            return None
    except (ValueError, TypeError):
        return None
    if s.get("boundary_guards_reviewed") is not True:
        return None
    return (s["family_id"], s["parameter"], s["unit"], s["controls_sha256"], s["interval_id"])


def evidence_blockers(row, e, plan):
    blockers = []
    if not e:
        return ["missing_versioned_asset_and_qa_evidence"]
    identity = e.get("identity", {})
    if identity.get("sample_id") != row["sample_id"] or identity.get("engine") != row["engine"]:
        blockers.append("identity_mismatch")
    if not identity.get("revision") or not identity.get("release"):
        blockers.append("missing_pinned_revision_or_release")
    media = e.get("videos", {})
    if set(media) != {"cam01", "cam02", "cam03"} or any(
            not v.get("path") or not is_sha(v.get("sha256")) for v in media.values()):
        blockers.append("missing_three_view_media_paths_or_sha256")
    if not e.get("state", {}).get("path") or not is_sha(e.get("state", {}).get("sha256")):
        blockers.append("missing_state_path_or_sha256")
    if not e.get("receipt", {}).get("path") or not is_sha(e.get("receipt", {}).get("sha256")):
        blockers.append("missing_inspectable_validation_receipt")
    blockers.extend("unverified:" + key for key in CHECKS if e.get("checks", {}).get(key) is not True)
    sampling = e.get("sampling", {})
    if (sampling.get("kind") not in ("global", "critical") or not sampling.get("family_id")
            or type(sampling.get("propagation_depth")) is not int or sampling["propagation_depth"] < 0):
        blockers.append("missing_verified_sampling_kind_family_or_depth")
    if scan_required(row, plan) and scan_key(e) is None:
        blockers.append("missing_numeric_interval_and_boundary_review")
    return blockers


def audit_bindings(rows, links=()):
    """Recheck output ownership without consulting the assignment graph."""
    owners = defaultdict(set)
    intervals = defaultdict(list)
    for r in rows:
        e = r.get("asset_evidence") or {}
        keys = ["source:" + r["leakage_group_id"], "component:" + r["component_id"]]
        keys += ["media:" + v["sha256"].lower() for v in e.get("videos", {}).values() if is_sha(v.get("sha256"))]
        keys += [field + ":" + e[field] for field in ("physical_configuration_group", "critical_family_group") if e.get(field)]
        if e.get("sampling", {}).get("kind") == "critical" and e["sampling"].get("family_id"):
            keys.append("critical_sampling_family:" + e["sampling"]["family_id"])
        sk = scan_key(e)
        if sk is not None:
            keys.append("interval:" + digest(sk))
            intervals[sk[:-1]].append((float(e["scan"]["low"]), float(e["scan"]["high"]), r["split"]))
        for key in keys: owners[key].add(r["split"])
    by_id = {r["record_id"]: r for r in rows}
    for i, link in enumerate(links):
        owners[f"link:{i}"] = {by_id[rid]["split"] for rid in link["record_ids"]}
    conflicts = [key for key, splits in owners.items() if len(splits) > 1]
    for family, spans in intervals.items():
        high = -float("inf"); split = None
        for low, end, current in sorted(spans):
            if low <= high and current != split:
                conflicts.append("overlapping_intervals:" + digest(family))
            if low > high or end > high: high, split = end, current
    if conflicts: raise ValueError("Cross-split binding conflict: " + ", ".join(conflicts[:5]))
    if len(by_id) != len(rows): raise ValueError("Duplicate assignment IDs")
    return {"checked_binding_keys": len(owners), "cross_split_conflicts": len(conflicts)}


def materialize(plan, rows, evidence=(), links=(), exposure=(), seed=20261011):
    validate_plan(plan)
    if set(plan["ratios"]) != set(SPLITS[:3]):
        raise ValueError("Ratios must address train, val and test_id")
    ids = [r["record_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs")
    rows = sorted(rows, key=lambda r: r["record_id"])
    by_id = {r["record_id"]: r for r in rows}
    evid = {}
    for e in evidence:
        rid = e["record_id"]
        if rid not in by_id or rid in evid:
            raise ValueError("Orphan or duplicate evidence")
        evid[rid] = e
    pools = {e: p for p in ("train_pool", "test_ood_1", "test_ood_2") for e in plan[p]}
    parent = {rid: rid for rid in ids}

    def root(rid):
        while parent[rid] != rid:
            parent[rid] = parent[parent[rid]]; rid = parent[rid]
        return rid

    def union(a, b):
        a, b = root(a), root(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    keys = {}
    intervals = defaultdict(list)
    for r in rows:
        rid = r["record_id"]
        if r["event_id"] not in pools or r["engine"] not in plan["video_targets"]:
            raise ValueError("Unknown event or engine")
        if not r.get("leakage_group_id") or r.get("video_references") != 3:
            raise ValueError("Missing source group or expected three-view inventory grain")
        e = evid.get(rid, {})
        tokens = ["known_group:" + r["leakage_group_id"]]
        tokens += ["media_sha:" + v["sha256"].lower() for v in e.get("videos", {}).values()
                   if is_sha(v.get("sha256"))]
        if e.get("physical_configuration_group"):
            tokens.append("physical_configuration:" + e["physical_configuration_group"])
        if e.get("critical_family_group"):
            tokens.append("critical_family:" + e["critical_family_group"])
        if e.get("sampling", {}).get("kind") == "critical" and e["sampling"].get("family_id"):
            tokens.append("critical_sampling_family:" + e["sampling"]["family_id"])
        sk = scan_key(e)
        if sk is not None:
            tokens.append("scan_interval:" + digest(sk))
            intervals[sk[:-1]].append((rid, float(e["scan"]["low"]), float(e["scan"]["high"])))
        for token in tokens:
            if token in keys:
                union(rid, keys[token])
            else:
                keys[token] = rid
    # Shared interval endpoints/overlaps are connected across the entire family.
    for rr in intervals.values():
        last = None
        for rid, low, high in sorted(rr, key=lambda x: (x[1], x[2], x[0])):
            if last is not None and low <= last[1]:
                union(last[0], rid)
            if last is None or high > last[1]:
                last = (rid, high)
    for link in links:
        members = link["record_ids"]
        if not members or any(rid not in by_id for rid in members):
            raise ValueError("Empty link or orphan linked record")
        if not link.get("receipt_path") or not is_sha(link.get("receipt_sha256")):
            raise ValueError("Explicit links require inspectable source evidence")
        for rid in members[1:]:
            union(members[0], rid)
    components = defaultdict(list)
    for r in rows:
        components[root(r["record_id"])].append(r)
    exposed = set(exposure)
    # Exposure is scientific disclosure, never an exclusion criterion.
    group_exposure = {}
    for k, rr in components.items():
        group_exposure[k] = any((r["engine"], r["sample_id"]) in exposed for r in rr)
    assignment = {}
    candidates = []
    for k, rr in components.items():
        pp = {pools[r["event_id"]] for r in rr}
        if len(pp) > 1:
            assignment[k] = "quarantine"
        elif pp != {"train_pool"}:
            assignment[k] = next(iter(pp))
        elif any(scan_required(r, plan) and scan_key(evid.get(r["record_id"], {})) is None for r in rr):
            assignment[k] = "pending"
        else:
            candidates.append((k, rr))
    # One assignment across both engines, with full-group rather than exact-count priority.
    features = {}
    totals = Counter()
    for k, rr in candidates:
        f = Counter()
        for r in rr:
            bg = re.search(r"bg0[1-4]", r["sample_id"])
            for key in ("all", "event:" + r["event_id"], "engine:" + r["engine"],
                        "event_engine:" + r["event_id"] + ":" + r["engine"],
                        "event_background:" + r["event_id"] + ":" + (bg.group() if bg else "unknown")):
                f[key] += r["video_references"]
            sampling = evid.get(r["record_id"], {}).get("sampling", {})
            if sampling.get("kind") in ("global", "critical"):
                f["event_kind:" + r["event_id"] + ":" + sampling["kind"]] += r["video_references"]
        features[k] = f; totals.update(f)
    counts = {split: Counter() for split in ("train", "val", "test_id")}
    for k, rr in sorted(candidates, key=lambda pair: (-features[pair[0]]["all"], digest([seed, pair[0]]))):
        f = features[k]
        def delta(split):
            ratio = plan["ratios"][split]
            return sum(((counts[split][key] + n - ratio * totals[key]) ** 2
                        - (counts[split][key] - ratio * totals[key]) ** 2) / totals[key]
                       for key, n in f.items())
        split = min(counts, key=lambda s: (delta(s), digest([seed, k, s])))
        assignment[k] = split; counts[split].update(f)
    # Repair feasible observed coverage by moving whole components, never rows.
    owners = defaultdict(list)
    for k, f in features.items():
        for key in f:
            if key.startswith(("event:", "event_engine:", "event_background:", "event_kind:")):
                owners[key].append(k)
    feasible = {key for key, kk in owners.items() if len(kk) >= 3}
    for key in sorted(feasible):
        for dest in counts:
            if counts[dest][key]:
                continue
            options = []
            for k in owners[key]:
                donor = assignment[k]; f = features[k]
                if any(counts[donor][q] - n <= 0 for q, n in f.items() if q in feasible):
                    continue
                change = 0.
                for q, n in f.items():
                    for split, step in ((donor, -n), (dest, n)):
                        target = plan["ratios"][split] * totals[q]; before = counts[split][q] - target
                        change += ((before + step) ** 2 - before ** 2) / totals[q]
                options.append((change, digest([seed, k, dest]), k))
            if options:
                k = min(options)[2]; counts[assignment[k]].subtract(features[k])
                assignment[k] = dest; counts[dest].update(features[k])
    out = []
    for r in rows:
        rid = r["record_id"]; k = root(rid); split = assignment[k]
        blockers = evidence_blockers(r, evid.get(rid, {}), plan)
        if split == "quarantine": blockers.append("cross_event_pool_component_conflict")
        if split == "pending": blockers.append("group_waits_for_numeric_interval_review")
        out.append({**r, "split": split, "component_id": digest(sorted(x["record_id"] for x in components[k]))[:24],
                    "metric_development_group_exposed": group_exposure[k],
                    "assignment_stage": "candidate_source_group_assignment",
                    "training_ready": False, "release_blockers": blockers,
                    "asset_evidence": evid.get(rid)})
    summary = {"plan_version": plan["version"], "seed": seed,
               "status": "candidate_assignments_not_frozen_release", "registered_trajectories": len(rows),
               "registered_video_references": sum(r["video_references"] for r in rows),
               "components": len(components), "source_inventory_rows_retained": len(out) == len(rows),
               "trajectory_counts": dict(Counter(r["split"] for r in out)),
               "video_reference_counts": dict(sum_counters(out, "split")),
               "blocker_counts": dict(Counter(b for r in out for b in r["release_blockers"])),
               "metric_exposed_trajectories": sum(r["metric_development_group_exposed"] for r in out),
               "group_split_conflicts": 0, "estimator_modified": False,
               "explicit_links": list(links),
               "coverage": {key: {"available_components": len(kk),
                                    "splits_present": [s for s in counts if counts[s][key] > 0],
                                    "all_three_feasible_by_component_count": key in feasible}
                            for key, kk in sorted(owners.items())},
               "missing_target_event_engine_pairs": [f"{engine}:{event}" for engine, targets in plan["video_targets"].items()
                                                      for event, target in targets.items() if target > 0 and not any(
                                                          r["engine"] == engine and r["event_id"] == event for r in rows)],
               "groups": {field: grouped(out, field) for field in ("event_id", "engine")}}
    summary["binding_audit"] = audit_bindings(out, links)
    return out, summary


def sum_counters(rows, field):
    counts = Counter()
    for r in rows: counts[r[field]] += r["video_references"]
    return counts


def grouped(rows, field):
    groups = defaultdict(list)
    for r in rows: groups[r[field]].append(r)
    return {k: {"trajectories": len(rr), "videos_by_split": dict(sum_counters(rr, "split")),
                "blocked_trajectories": sum(bool(r["release_blockers"]) for r in rr)}
            for k, rr in sorted(groups.items())}


def write_outputs(out, rows, summary, sources, freeze=False):
    audit_bindings(rows, summary.get("explicit_links", []))
    prior = out / "audit.json"
    if prior.exists() and json.loads(prior.read_text()).get("release_ready") is True:
        raise ValueError("Frozen releases are immutable; use a new output version")
    if freeze and (summary["blocker_counts"] or summary["missing_target_event_engine_pairs"]
                   or any(v["all_three_feasible_by_component_count"] and len(v["splits_present"]) < 3
                          for v in summary["coverage"].values())
                   or any(r["split"] not in SPLITS for r in rows)):
        raise ValueError("Release blocked: unresolved source/interval/asset/QA evidence; no frozen manifests written")
    if freeze:
        for row in rows:
            e = row["asset_evidence"]; receipt = Path(e["receipt"]["path"])
            if not receipt.is_file() or hashlib.sha256(receipt.read_bytes()).hexdigest() != e["receipt"]["sha256"]:
                raise ValueError("Validation receipt unavailable or SHA mismatch")
            proof = json.loads(receipt.read_text())
            if proof.get("record_id") != row["record_id"] or any(
                    proof.get(key) != e.get(key) for key in ("identity", "checks", "videos", "state", "scan",
                                                            "physical_configuration_group", "critical_family_group", "sampling")):
                raise ValueError("Validation receipt identity/assets/checks mismatch")
        for link in summary.get("explicit_links", []):
            path = Path(link["receipt_path"])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != link["receipt_sha256"]:
                raise ValueError("Linked-source receipt unavailable or SHA mismatch")
            if set(json.loads(path.read_text()).get("record_ids", [])) != set(link["record_ids"]):
                raise ValueError("Linked-source receipt membership mismatch")
    out.mkdir(parents=True, exist_ok=True)
    summary = {**summary, "source_sha256": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources}}
    for split in (*SPLITS, "pending", "quarantine", "assignments"):
        rr = rows if split == "assignments" else [r for r in rows if r["split"] == split]
        text = "".join(json.dumps({**r, "training_ready": freeze,
                                 "assignment_stage": "frozen_release" if freeze else r["assignment_stage"]},
                                ensure_ascii=False, sort_keys=True) + "\n" for r in rr)
        (out / (split + ".jsonl")).write_text(text, encoding="utf-8")
    summary["manifest_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.jsonl"))}
    summary["release_ready"] = freeze
    if freeze: summary["status"] = "frozen_versioned_joint_split"
    (out / "audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def load_training_split(directory, split):
    if split not in SPLITS:
        raise ValueError("Unknown split")
    directory = Path(directory); audit = json.loads((directory / "audit.json").read_text())
    if audit.get("release_ready") is not True or audit.get("status") != "frozen_versioned_joint_split":
        raise ValueError("Candidate assignment is not a training-ready release")
    path = directory / (split + ".jsonl")
    if hashlib.sha256(path.read_bytes()).hexdigest() != audit["manifest_sha256"][path.name]:
        raise ValueError("Frozen manifest content changed")
    rows = jsonl(path)
    if any(r.get("training_ready") is not True or r.get("split") != split for r in rows):
        raise ValueError("Frozen row readiness/split mismatch")
    return rows


def training_sampling_weights(directory):
    """Equal event, family and observed propagation-depth mass on a frozen train set.

    Returns trajectory weights; views/backgrounds remain within their source split.
    Does not launch training or invent event/propagation labels from filenames.
    """
    rows = load_training_split(directory, "train")
    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        s = r["asset_evidence"]["sampling"]
        groups[r["event_id"]][s["family_id"]][s["propagation_depth"]].append(r["record_id"])
    weights = {}
    for families in groups.values():
        for depths in families.values():
            for ids in depths.values():
                mass = 1 / (len(groups) * len(families) * len(depths) * len(ids))
                weights.update({rid: mass for rid in ids})
    return weights


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, default=Path("docs/joint_split_v3/plan.json"))
    ap.add_argument("--routing", type=Path, default=Path("docs/joint_split_v3/event_pool_routing.jsonl"))
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--links", type=Path)
    ap.add_argument("--development", type=Path, default=Path("docs/phyediting/sam31_subpixel_v4_case_scores.csv"))
    ap.add_argument("--historical-exposure", type=Path,
                    help="Prior-attempt inventory JSON with prior_prediction_trajectory_ids; disclosure only")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args(); rows = jsonl(args.routing)
    # Exact prefix matching from actual trajectory IDs, not event-level exposure.
    case_ids = [r["id"] for r in csv.DictReader(args.development.open())]
    exposure = {(r["engine"], r["sample_id"]) for r in rows if r["engine"] == "genesis"
                and any(cid.startswith(r["sample_id"] + "__") for cid in case_ids)}
    if args.historical_exposure:
        prior_ids = set(json.loads(args.historical_exposure.read_text())["prior_prediction_trajectory_ids"])
        exposure.update((r["engine"], r["sample_id"]) for r in rows
                        if r["engine"] == "genesis" and r["sample_id"] in prior_ids)
    out, summary = materialize(json.loads(args.plan.read_text()), rows,
                               jsonl(args.evidence) if args.evidence else [],
                               jsonl(args.links) if args.links else [], exposure, args.seed)
    summary["exposure_scope"] = ("accepted development cases and supplied prior-attempt inventory plus connected-group closure; "
                                 "absence is not proof of untouched settings; metadata/historical gaps remain disclosed")
    sources = [args.plan, args.routing, args.development] + [p for p in (args.evidence, args.links, args.historical_exposure) if p]
    summary = write_outputs(args.out, out, summary, sources, args.freeze)
    print(json.dumps({k: summary[k] for k in ("status", "registered_trajectories", "video_reference_counts", "release_ready")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
