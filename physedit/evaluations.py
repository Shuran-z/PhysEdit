"""Independent V/P and visual-judge stages, retaining all registered cases."""

import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from .runners.media_contract import (
    sha256,
    validate_video,
    verified_completion,
    row_digest,
    completion_path,
)
from . import vp_metrics as dm
from . import pixel_metrics as pm
from .qwen_judge import CATEGORIES, PROMPT_PATH, InvalidJudgeResponse, call_api, parse_judgement

VP_NAMES = (
    "condition_ssim",
    "condition_psnr_db",
    "reference_ssim",
    "reference_psnr_db",
    "condition_foreground_ssim",
    "condition_foreground_psnr_db",
    "reference_foreground_ssim",
    "reference_foreground_psnr_db",
    "camera_motion_full",
    "camera_motion_1s",
    "background_flicker_full",
    "background_flicker_1s",
    "silhouette_full",
    "silhouette_1s",
    "motion_region_iou_full",
    "motion_region_iou_1s",
    "trajectory_error_full",
    "trajectory_error_1s",
)


def generated_video(row):
    return row.get("final_resized") or row["generated_video_resized_to_source"]


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def dump(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def write_rows(path, rows):
    with Path(path).open("x") as f:
        for row in rows:
            f.write(json.dumps(row, allow_nan=False) + "\n")
            f.flush()


def context(row):
    if row.get("input_failure"):
        raise ValueError(row["input_failure"])
    receipt = verified_completion(row)
    source = Path(row["source_video"])
    if (
        not row.get("source_video_sha256")
        or sha256(source) != row["source_video_sha256"]
    ):
        raise ValueError("reference_video_sha256_mismatch")
    media = validate_video(
        source,
        fps=row["source_native_fps"],
        width=row["source_width"],
        height=row["source_height"],
    )
    c = row["condition_frame_index"]
    if type(c) is not int or not 0 <= c < media["frames"]:
        raise ValueError("invalid_condition_index")
    condition = cv2.imread(row["condition_image"])
    if condition is None or not np.array_equal(condition, frame(source, c)):
        raise ValueError("condition_image_reference_pixel_mismatch")
    return dict(
        source_frames=media["frames"],
        condition_frame=c,
        source_fps=float(row["source_native_fps"]),
        generated_frames=int(row["num_frames"]),
        generated_fps=float(row["output_fps"]),
        source_sha256=row["source_video_sha256"],
        generated_sha256=receipt["media"]["video_sha256"],
        row_sha256=row_digest(row),
        completion_sha256=sha256(completion_path(row)),
    )


def frame(path, index):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, bgr = cap.read()
        if not ok:
            raise ValueError("frame_decode_failure: " + str(index))
        return bgr
    finally:
        cap.release()


def qwen_evidence(row, ctx, folder, config=None):
    from .judge_video import sampling
    config = config or {}
    indices, fps = sampling(ctx["generated_frames"], ctx["generated_fps"], config)
    folder.mkdir()
    condition = cv2.imread(row["condition_image"])
    reference = frame(row["source_video"], ctx["condition_frame"])
    if condition is None or not np.array_equal(condition, reference):
        raise ValueError("condition_image_reference_pixel_mismatch")

    def save(bgr, path):
        image = bgr  # Preserve native pixels; the model processor owns resizing.
        if not cv2.imwrite(str(path), image):
            raise ValueError("judge_image_write_failure")
        return dict(
            path=str(path.resolve()),
            png_sha256=sha256(path),
            decoded_bgr_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
            size=[image.shape[1], image.shape[0]],
        )

    cond = save(condition, folder / "condition.png")
    frames = []
    for k, index in enumerate(indices):
        record = save(
            frame(generated_video(row), index), folder / f"frame_{index:06d}.png"
        )
        frames.append(
            dict(
                record,
                frame_index=index,
                time_seconds=index / ctx["generated_fps"],
                requested_time_seconds=k / fps,
            )
        )
    evidence = dict(
        condition_image=cond["path"],
        condition=cond,
        frames=frames,
        prompt_sha256=sha256(PROMPT_PATH),
        protocol="visible_video_full_v2",
        video=dict(path=str(Path(generated_video(row)).resolve()), sha256=ctx["generated_sha256"],
                   frame_count=ctx["generated_frames"], native_fps=ctx["generated_fps"],
                   duration_seconds=ctx["generated_frames"]/ctx["generated_fps"]),
        sampling_fps=fps,
        requested_sampling_fps=config.get("video_fps", 2.0),
        processor_max_pixels=config.get("max_pixels", 602112),
        temporal_sampling_error_seconds=max(abs(f["time_seconds"]-f["requested_time_seconds"]) for f in frames),
        **ctx,
    )
    dump(folder / "registered_evidence.json", evidence)
    return evidence


def verify_evidence(evidence):
    from .judge_video import verify_evidence as verify
    verify(evidence, PROMPT_PATH)


def mask_sequence(entry, ctx, kind, target, size):
    from .mask_evidence import load_sequence
    return load_sequence(entry, ctx, kind, target, size)


def automatic_masks(rows, contexts, items, initial, spec, root):
    """Separate full-video observations, never reuse/extend inversion windows."""
    from scripts import sam31_frontend as frontend

    jobs = []
    for row in rows:
        sid = row["sample_id"]
        if sid not in contexts:
            continue
        ctx = contexts[sid]
        it = items[row["item_id"]]
        seed = initial.get(sid, {})
        for kind in ("source", "generated"):
            source = kind == "source"
            start = ctx["condition_frame"] if source else 0
            jobs.append(
                dict(
                    id=sid + "__vp_" + kind,
                    video=row["source_video"] if source else generated_video(row),
                    video_sha256=(
                        ctx["source_sha256"] if source else ctx["generated_sha256"]
                    ),
                    frames=list(
                        range(
                            start,
                            ctx["source_frames"] if source else ctx["generated_frames"],
                        )
                    ),
                    prompt_frame=start,
                    scene_boxes=seed.get("objects", {}),
                    target_name=it["object_name"],
                    fps=ctx["source_fps"] if source else ctx["generated_fps"],
                    input_failure=seed.get("input_failure"),
                )
            )
    if not jobs:
        return {}, {}
    write_rows(root / "vp_mask_jobs.jsonl", jobs)
    frontend.prepare(root / "vp_mask_jobs.jsonl", root / "vp_sam31")
    try:
        frontend.run(root / "vp_sam31", spec["sam3"], spec["checkpoint"])
    except Exception:
        # Existing partial outputs and the frontend's explicit failure file stay retained.
        if not (root / "vp_sam31/measurements_v4.jsonl").is_file():
            return {}, {
                r["sample_id"]: "vp_segmentation_failure"
                for r in rows
                if r["sample_id"] in contexts
            }
    return export_observed_masks(rows, contexts, items, root)


def export_observed_masks(rows, contexts, items, root, observations_root=None):
    """Export existing observations only; missing frames remain explicit, never zero masks."""
    from .mask_evidence import export_masks
    return export_masks(rows, contexts, items, Path(root),
                        Path(observations_root) if observations_root else Path(root) / "vp_sam31")


def vp_case(row, ctx, item, pair, vp_settings=None):
    config = vp_settings or {}
    result = {
        "sample_id": row["sample_id"],
        "metrics": {},
        "protocol": "phyediting_vp_v3",
        "pixel_settings": pm.settings(vp_settings),
        "provenance": ctx,
    }

    def metric(name, fn):
        try:
            output = fn()
            diagnostic = output if isinstance(output, dict) else {}
            value = output.get("error") if diagnostic else output
            if diagnostic and value == math.inf:
                diagnostic = dict(diagnostic, error="+inf")
            perfect = type(value) in (int, float) and value == math.inf and "psnr" in name
            if type(value) not in (int, float) or (not math.isfinite(value) and not perfect):
                result["metrics"][name] = dict(
                    status="insufficient_evidence",
                    value=None,
                    reason="insufficient_valid_frames_or_pairs",
                    diagnostic=diagnostic,
                )
            else:
                result["metrics"][name] = dict(
                    status="ok", value=pm.json_value(float(value)), diagnostic=diagnostic,
                    positive_infinity=perfect,
                )
        except pm.InsufficientEvidence as e:
            result["metrics"][name] = dict(
                status="insufficient_evidence", value=None, reason=str(e)
            )
        except Exception as e:
            result["metrics"][name] = dict(
                status="failed", value=None, reason=type(e).__name__ + ": " + str(e)
            )

    def read_video(path):
        cap = cv2.VideoCapture(str(path))
        frames = []
        stamps = []
        try:
            while True:
                ok, bgr = cap.read()
                if not ok:
                    break
                frames.append(bgr)
                stamps.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        finally:
            cap.release()
        return frames, np.asarray(stamps)

    source, source_times = read_video(row["source_video"])
    generated, generated_times = read_video(generated_video(row))
    if len(source) != ctx["source_frames"] or len(generated) != ctx["generated_frames"]:
        raise ValueError("vp_full_decode_count_changed")
    c = ctx["condition_frame"]
    source = source[c:]
    source_times = source_times[c:] - source_times[c]
    generated_times = generated_times - generated_times[0]
    source_size = source[0].shape[:2]
    result["pixel_spatial_mapping"] = dict(
        source_size=list(source_size[::-1]),
        generated_input_size=list(generated[0].shape[1::-1]),
        interpolation="INTER_AREA", generated_resized=generated[0].shape[:2] != source_size,
    )
    generated = [dm.resize_like(image, source[0]) for image in generated]
    metric("condition_ssim", lambda: dm.ssim(source[0], generated[0]))
    metric("condition_psnr_db", lambda: dm.psnr(source[0], generated[0]))
    alignment = None
    alignment_error = None
    pixel_settings = result["pixel_settings"]
    try:
        alignment = pm.fixed_time_alignment(
            source_times, generated_times,
            pixel_settings["reference_duration_seconds"], pixel_settings["reference_fps"],
        )
        alignment["source_absolute_indices"] = [i + c for i in alignment["source_indices"]]
        alignment["paired_frame_coverage_percent"] = 100.0
        result["pixel_alignment"] = alignment
    except ValueError as e:
        alignment_error = e
        result["pixel_alignment"] = dict(
            reason=str(e), source_available_seconds=float(source_times[-1]),
            generated_available_seconds=float(generated_times[-1]),
            requested_duration_seconds=pixel_settings["reference_duration_seconds"],
            paired_frame_coverage_percent=0.0,
        )

    def reference_score(name, masks=None):
        if alignment_error is not None:
            raise alignment_error
        return pm.video_score(source, generated, alignment, name, masks)

    metric("reference_ssim", lambda: reference_score("ssim"))
    metric("reference_psnr_db", lambda: reference_score("psnr"))
    result["reference_alignment"] = "post_condition_fixed_real_time"
    result["mask_metric_size"] = [320, 180]
    for suffix, seconds in (("full", None), ("1s", 1.0)):
        k = (
            len(generated)
            if seconds is None
            else min(len(generated), math.floor(ctx["generated_fps"] + 1e-6) + 1)
        )
        if suffix == "1s" and (len(generated) - 1) / ctx["generated_fps"] < 1:
            result["metrics"]["camera_motion_1s"] = dict(
                status="insufficient_evidence",
                value=None,
                reason="incomplete_one_second_window",
            )
        else:
            metric(
                "camera_motion_" + suffix,
                lambda k=k: dm.camera_motion_diagnostics(generated[:k], 0),
            )
    from .mask_evidence import required_masks
    sequences, sequence_errors = {}, {}
    pair = pair or {}
    result["mask_provenance"] = {}
    for kind in ("source", "generated"):
        try:
            if kind not in pair:
                raise ValueError("missing_registered_or_sam31_" + kind + "_masks")
            sequences[kind], provenance = mask_sequence(
                pair[kind], ctx, kind, item["object_name"],
                (row["source_width"], row["source_height"]),
            )
            result["mask_provenance"][kind] = provenance
        except Exception as error:
            sequence_errors[kind] = str(error)

    def masks(kind, indices):
        if kind in sequence_errors:
            raise ValueError(sequence_errors[kind])
        return required_masks(sequences[kind], indices, kind,
                              result["mask_provenance"][kind])

    def reference_masks():
        if alignment_error is not None:
            raise alignment_error
        # Only registered, actually paired source frames are required by this metric.
        masks("source", alignment["source_indices"])
        return sequences["source"]

    metric("condition_foreground_ssim", lambda: pm.ssim(source[0], generated[0], masks("source", [0])[0]))
    metric("condition_foreground_psnr_db", lambda: pm.psnr(source[0], generated[0], masks("source", [0])[0]))
    metric("reference_foreground_ssim", lambda: reference_score("ssim", reference_masks()))
    metric("reference_foreground_psnr_db", lambda: reference_score("psnr", reference_masks()))
    if "source" in result["mask_provenance"]:
        result["reference_foreground_provenance"] = result["mask_provenance"]["source"]

    def small(sequence):
        return [cv2.resize(m.astype(np.uint8), (320, 180), interpolation=cv2.INTER_NEAREST).astype(bool)
                for m in sequence]

    for suffix in ("full", "1s"):
        kg = len(generated) if suffix == "full" else math.floor(ctx["generated_fps"] + 1e-6) + 1
        ks = len(source) if suffix == "full" else math.floor(ctx["source_fps"] + 1e-6) + 1

        def window(kind, count):
            available = len(source) if kind == "source" else len(generated)
            fps = ctx[kind + "_fps"]
            if suffix == "1s" and (available - 1) / fps < 1:
                raise pm.InsufficientEvidence("incomplete_one_second_window")
            return masks(kind, range(count))

        metric("background_flicker_" + suffix,
               lambda: dm.background_flicker_diagnostics(generated[:kg], window("generated", kg)))

        def silhouette():
            gm = small(window("generated", kg))
            if np.mean([m.sum() >= 10 for m in gm]) < 0.95:
                raise pm.InsufficientEvidence("insufficient_visible_target_frames")
            return dm.silhouette_structure_error(gm, 0)

        metric("silhouette_" + suffix, silhouette)

        def paired(fn):
            sm, gm = small(window("source", ks)), small(window("generated", kg))
            if min(sum(m.sum() >= 10 for m in sm), sum(m.sum() >= 10 for m in gm)) < 3:
                raise pm.InsufficientEvidence("too_few_visible_target_frames")
            return fn(sm, gm, 0, 0)

        metric("motion_region_iou_" + suffix, lambda: paired(dm.motion_region_iou))
        def trajectory():
            duration = float(config.get('trajectory_duration_seconds', 5.0)) if suffix == 'full' else 1.0
            sample_fps = float(config.get('trajectory_sampling_fps', 30.0))
            for times in (source_times, generated_times):
                if times[-1] + 1e-8 < duration:
                    raise pm.InsufficientEvidence('incomplete_trajectory_time_window')
            counts = [min(np.searchsorted(times, duration, side='left') + 1, len(times))
                      for times in (source_times, generated_times)]
            sm = small(masks('source', range(counts[0])))
            gm = small(masks('generated', range(counts[1])))
            return dm.trajectory_error(sm, gm, 0, 0,
                source_times=source_times[:counts[0]], generated_times=generated_times[:counts[1]],
                duration_seconds=duration, sampling_fps=sample_fps)
        result.setdefault('trajectory_settings', {})[suffix] = dict(
            protocol='phyediting_trajectory_real_time_v2',
            duration_seconds=float(config.get('trajectory_duration_seconds', 5.0)) if suffix == 'full' else 1.0,
            sampling_fps=float(config.get('trajectory_sampling_fps', 30.0)),
            alignment='linear_native_centroids_no_time_stretch_no_extrapolation',
            normalization='source_image_diagonal', initial_translation_removed=True)
        metric("trajectory_error_" + suffix, trajectory)
    result["status"] = (
        "ok"
        if all(m["status"] == "ok" for m in result["metrics"].values())
        else "partial"
    )
    if context(row) != ctx:
        raise ValueError("media_drift_during_vp_evaluation")
    if result["status"] != "ok":
        result["reason"] = "one_or_more_metrics_unavailable; see per-metric reasons"
    return result


def aggregate(records, metric=None):
    values = []
    failures = []
    for row in records:
        result = row["metrics"][metric] if metric else row
        if result["status"] == "ok":
            if metric:
                values.append(result["value"])
        else:
            failures.append(
                {
                    "sample_id": row["sample_id"],
                    "status": result["status"],
                    "reason": result.get("reason", result["status"]),
                }
            )
    n = len(records)
    good = n - len(failures)
    output = dict(
        registered=n,
        scored=good,
        failed=n - good,
        coverage_percent=100 * good / n if n else None,
        failure_rate_percent=100 * (n - good) / n if n else None,
        failures=failures,
    )
    if metric:
        numbers = [math.inf if v == "+inf" else v for v in values]
        output.update(
            mean=pm.json_value(statistics.mean(numbers)) if numbers else None,
            median=pm.json_value(statistics.median(numbers)) if numbers else None,
            positive_infinity_cases=sum(v == math.inf for v in numbers),
            weighting="equal_weight_per_video",
        )
    output["unscored_by_status"] = {
        status: sum(f["status"] == status for f in failures)
        for status in sorted({f["status"] for f in failures})
    }
    return output


def summarize(rows, records, kind, items=None):
    if [r["sample_id"] for r in records] != [r["sample_id"] for r in rows]:
        raise ValueError("evaluation_denominator_or_order_mismatch")
    items = items or {}

    def stats(selected):
        output = aggregate(selected)
        if kind == "vp":
            output["metrics"] = {name: aggregate(selected, name) for name in VP_NAMES}
        else:
            output['coverage_basis'] = 'category_valid_and_model_reported_assessability'
            output['semantic_accuracy_validated'] = False
            good = [r for r in selected if r["status"] in ('ok', 'partial')]
            category_good = {name:[r for r in good if r['judgement'][name].get('assessable', True)] for name in CATEGORIES}
            output["clear_violation_percent"] = {
                name: (
                    100
                    * sum(r["judgement"][name]["severity"] >= 2 for r in category_good[name])
                    / len(category_good[name])
                    if category_good[name]
                    else None
                )
                for name in CATEGORIES
            }
            output["violation_rate_denominator"] = (
                "per_category_schema_valid_and_assessable_cases"
            )
            output['category_coverage'] = {name:dict(registered=len(selected),assessed=len(category_good[name]),
                coverage_percent=100*len(category_good[name])/len(selected) if selected else None,
                unassessed_ids=[r['sample_id'] for r in selected if r not in category_good[name]]) for name in CATEGORIES}
            output["judgement_protocols"] = sorted({r.get("judgement_protocol", "legacy_unspecified") for r in selected})
            output["judge_models"] = sorted(
                {str(r.get("served_model") or r.get("judge_model")) for r in selected}
            )
        return output

    result = stats(records)
    result["groups"] = {}
    for key in ("split", "event", "camera_id", "gravity_truth"):
        groups = {}
        for row, record in zip(rows, records):
            value = row.get(key, items.get(row.get("item_id"), {}).get(key, "unspecified"))
            groups.setdefault(str(value), []).append(record)
        result["groups"][key] = {
            group: stats(selected) for group, selected in groups.items()
        }
    return result


def read_local_responses(path, expected_ids, returncode):
    """Keep fully written cases after child termination; never score a partial line."""
    lines = [line for line in Path(path).read_text().splitlines() if line.strip()]
    responses = {}
    incomplete_tail = False
    for index, line in enumerate(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            if returncode != 0 and index == len(lines) - 1:
                incomplete_tail = True
                break
            raise ValueError('local_judge_response_json_invalid') from None
        if (not isinstance(value, dict) or not isinstance(value.get('sample_id'), str)
                or value['sample_id'] not in expected_ids or value['sample_id'] in responses):
            raise ValueError('local_judge_identity_mismatch')
        responses[value['sample_id']] = value
    return responses, dict(returncode=returncode, incomplete_tail_retained=incomplete_tail,
                           completed_response_ids=list(responses))


def run_additional(spec, rows, items, initial, root):
    """Existing/generated media only. Each stage fails independently per original ID."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    evaluation = spec.get("evaluation", {"metrics": ["gravtrace"]})
    enabled = evaluation["metrics"]
    if not set(enabled) & {"vp", "qwen"}:
        return {}
    contexts = {}
    failures = {}
    for row in rows:
        try:
            contexts[row["sample_id"]] = context(row)
        except Exception as error:
            failures[row["sample_id"]] = type(error).__name__ + ": " + str(error)
    dump(
        root / "registered.json",
        dict(
            evaluation=evaluation,
            registered=len(rows),
            rows_sha256=hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()
            ).hexdigest(),
        ),
    )
    summaries = {}
    if "vp" in enabled:
        vp = evaluation.get("vp", {})
        entries = {}
        mask_failures = {}
        try:
            if vp.get("mask_backend", "sam31") == "sam31":
                entries, mask_failures = automatic_masks(
                    rows, contexts, items, initial, spec, root
                )
            else:
                masks = read_rows(vp["mask_manifest"])
                ids = [m["sample_id"] for m in masks]
                if len(set(ids)) != len(ids) or set(ids) - {
                    r["sample_id"] for r in rows
                }:
                    raise ValueError("mask_manifest_identity_mismatch")
                entries = {m["sample_id"]: m for m in masks}
        except Exception as error:
            mask_failures = {
                r["sample_id"]: "vp_mask_stage_failure: "
                + type(error).__name__
                + ": "
                + str(error)
                for r in rows
            }
        if vp.get("mask_review_manifest"):
            from .mask_evidence import attach_reviews
            # Malformed or stale review must not silently fall back to unreviewed scoring.
            try:
                attach_reviews(entries, rows, vp["mask_review_manifest"])
            except Exception as error:
                entries = {}
                mask_failures = {r["sample_id"]: "mask_review_failure: " + str(error) for r in rows}
        records = []
        with (root / "vp_results.jsonl").open("x") as out:
            for row in rows:
                sid = row["sample_id"]
                try:
                    if sid in failures:
                        raise ValueError(failures[sid])
                    record = vp_case(
                        row, contexts[sid], items[row["item_id"]], entries.get(sid), vp
                    )
                    if sid in mask_failures:
                        record["mask_failure"] = mask_failures[sid]
                        for value in record["metrics"].values():
                            if value["status"] == "failed":
                                value["reason"] = (
                                    mask_failures[sid] + "; " + value["reason"]
                                )
                except Exception as e:
                    reason = type(e).__name__ + ": " + str(e)
                    record = dict(
                        sample_id=sid,
                        status="failed",
                        protocol="phyediting_vp_v2",
                        pixel_settings=pm.settings(vp),
                        reason=reason,
                        metrics={
                            n: dict(status="failed", value=None, reason=reason)
                            for n in VP_NAMES
                        },
                    )
                records.append(record)
                out.write(json.dumps(record, allow_nan=False) + "\n")
                out.flush()
        summaries["vp"] = summarize(rows, records, "vp", items)
        summaries["vp"]["protocol"] = "phyediting_vp_v3"
        summaries["vp"]["pixel_settings"] = pm.settings(vp)
    if "qwen" in enabled:
        config = evaluation["qwen"]
        jobs = []
        evidence = {}
        responses = {}
        judge_failures = dict(failures)
        for row in rows:
            sid = row["sample_id"]
            if sid in judge_failures:
                continue
            try:
                folder = root / (
                    hashlib.sha256(sid.encode()).hexdigest()[:20] + "_judge"
                )
                evidence[sid] = qwen_evidence(row, contexts[sid], folder, config)
                jobs.append(dict(sample_id=sid, evidence=evidence[sid]))
            except Exception as e:
                judge_failures[sid] = type(e).__name__ + ": " + str(e)
        if config["backend"] == "local" and jobs:
            write_rows(root / "local_qwen_jobs.jsonl", jobs)
            dump(root / "local_qwen_spec.json", config)
            env = os.environ.copy()
            package_root = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = package_root + (
                os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
            )
            if config.get("gpu_devices"):
                env["CUDA_VISIBLE_DEVICES"] = config["gpu_devices"]
            command = [
                config.get("python", sys.executable),
                "-m",
                "physedit.qwen_judge",
                "--spec",
                str(root / "local_qwen_spec.json"),
                "--jobs",
                str(root / "local_qwen_jobs.jsonl"),
                "--output",
                str(root / "local_qwen_responses.jsonl"),
            ]
            try:
                with (root / "local_qwen.log").open("x") as log:
                    result = subprocess.run(
                        command, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                process_info = {"returncode": result.returncode}
                try:
                    if (root / "local_qwen_responses.jsonl").is_file():
                        responses, process_info = read_local_responses(
                            root / "local_qwen_responses.jsonl", set(evidence), result.returncode)
                        for response in responses.values():
                            response['local_process_returncode'] = result.returncode
                finally:
                    # Keep the actual process outcome even if reading its output fails.
                    dump(root / "local_qwen_exit.json", process_info)
                for job in jobs:
                    if job['sample_id'] not in responses:
                        judge_failures[job['sample_id']] = (
                            'missing_complete_local_judge_response: process_exit=' + str(result.returncode))
            except Exception as error:
                for job in jobs:
                    judge_failures[job["sample_id"]] = (
                        "local_qwen_process_failure: " + type(error).__name__
                    )
        records = []
        served = None
        with (root / "qwen_results.jsonl").open("x") as out:
            for row in rows:
                sid = row["sample_id"]
                record = dict(
                    sample_id=sid,
                    judge_model=config["model"],
                    backend=config["backend"],
                )
                try:
                    if sid in judge_failures:
                        raise ValueError(judge_failures[sid])
                    verify_evidence(evidence[sid])
                    response = (
                        call_api(config, evidence[sid])
                        if config["backend"] == "api"
                        else responses.get(
                            sid,
                            {
                                "status": "failed",
                                "reason": "missing_local_judge_response",
                            },
                        )
                    )
                    record.update(response, evidence=evidence[sid])
                    if response.get("status", "ok") != "ok":
                        raise ValueError(response.get("reason", "local_judge_failure"))
                    parse_judgement(json.dumps(response["judgement"]))
                    verify_evidence(evidence[sid])
                    if context(row) != contexts[sid]:
                        raise ValueError("media_drift_during_judgement")
                    # Retain the actual response/version even when model drift rejects scoring.
                    record.update(response, evidence=evidence[sid])
                    current = response.get("served_model")
                    if current is not None:
                        if served is not None and current != served:
                            raise ValueError("served_judge_model_changed_within_run")
                        served = current
                    record.update(
                        response,
                        evidence=evidence[sid],
                        status=(
                            "insufficient_evidence"
                            if response["judgement"]["insufficient_evidence"]
                            else ('partial' if not all(response['judgement'][k].get('assessable', True) for k in CATEGORIES) else 'ok')
                        ),
                    )
                    if record["status"] != "ok":
                        record["reason"] = ('judge_category_not_assessable' if record['status']=='partial' else 'judge_reported_insufficient_evidence')
                except Exception as error:
                    if isinstance(error, InvalidJudgeResponse):
                        record.update(error.response, evidence=evidence[sid])
                    record.update(
                        status="failed", reason=type(error).__name__ + ": " + str(error)
                    )
                records.append(record)
                out.write(json.dumps(record, allow_nan=False) + "\n")
                out.flush()
        summaries["qwen"] = summarize(rows, records, "qwen", items)
    dump(root / "summary.json", summaries)
    return summaries


def attach_summary(gravity, extra, metrics):
    result = dict(gravity, evaluation_metrics=metrics, evaluations=extra)
    failed = (
        {f["sample_id"] for f in gravity["failures"]}
        if "gravtrace" in metrics
        else set()
    )
    for stage in extra.values():
        failed.update(f["sample_id"] for f in stage["failures"])
    result["evaluation_failed"] = len(failed)
    result["all_requested_metrics_complete"] = not failed
    return result


def existing_run(spec, run_dir, output_dir, execute=False):
    """Evaluate a registered existing run, without generation or another gravity fit."""
    from .phyediting import validate_settings
    from scripts.sam31_frontend import lock
    from scripts.phyediting_gen_summary import report

    metrics = validate_settings(spec)
    lock()
    run = Path(run_dir).resolve()
    registration = json.loads((run / "registered.json").read_text())
    expected = registration["plan"]["input_items_sha256"]
    if sha256(spec["items"]) != expected or sha256(run / "items.jsonl") != expected:
        raise ValueError("existing_run_items_drift")
    prior = registration["spec"]
    for key in ("model", "model_dir", "data_root", "compact", "sam3", "checkpoint"):
        if spec.get(key) != prior.get(key):
            raise ValueError("existing_run_spec_mismatch: " + key)
    items = {i["id"]: i for i in read_rows(run / "items.jsonl")}
    rows = read_rows(run / "observed_rows.jsonl")
    ids = [r["sample_id"] for r in rows]
    if (
        len(set(ids)) != len(ids)
        or len(rows) != registration["plan"]["registered"]
        or {r["item_id"] for r in rows} != set(items)
    ):
        raise ValueError("existing_run_denominator_mismatch")
    plan = dict(
        registered=len(rows),
        evaluation_metrics=metrics,
        vp_pixel_settings=pm.settings(spec.get("evaluation", {}).get("vp")) if "vp" in metrics else None,
        execution_requested=False,
        generation_started=False,
        fitter_started=False,
        output_dir=str(Path(output_dir).resolve()),
    )
    if not execute:
        return plan
    predictions = (
        read_rows(run / "predictions.jsonl")
        if (run / "predictions.jsonl").is_file()
        else []
    )
    gravity = report(rows, predictions, items)
    initial = {r["id"]: r for r in read_rows(run / "initial_jobs.jsonl")}
    result = attach_summary(
        gravity, run_additional(spec, rows, items, initial, Path(output_dir)), metrics
    )
    dump(Path(output_dir) / "combined_summary.json", result)
    return result
