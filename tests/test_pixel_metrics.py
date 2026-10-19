import json
import math

import cv2
import numpy as np
import pytest

from physedit import evaluations as ev, pixel_metrics as pm
from physedit.evaluation_settings import validate


def image(value):
    return np.full((24, 30, 3), value, np.uint8)


def test_rgb_color_error_is_not_lost_by_grayscale_conversion():
    left, right = image(0), image(0)
    left[:] = [0, 0, 255]
    right[:] = [0, 130, 0]
    assert np.array_equal(cv2.cvtColor(left, cv2.COLOR_BGR2GRAY),
                          cv2.cvtColor(right, cv2.COLOR_BGR2GRAY))
    mse = (255 ** 2 + 130 ** 2) / 3
    assert pm.psnr(left, right) == pytest.approx(10 * math.log10(255 ** 2 / mse))
    c1 = (0.01 * 255) ** 2
    expected_ssim = (c1 / (255 ** 2 + c1) + c1 / (130 ** 2 + c1) + 1) / 3
    assert pm.ssim(left, right) == pytest.approx(expected_ssim)


def test_standard_identical_images_and_strict_json_infinity():
    assert pm.psnr(image(15), image(15)) == math.inf
    assert pm.ssim(image(15), image(15)) == pytest.approx(1)
    assert json.dumps({"psnr": pm.json_value(math.inf)}, allow_nan=False) == '{"psnr": "+inf"}'


def test_library_version_drift_rejected_before_scoring(monkeypatch):
    monkeypatch.setattr(pm.skimage, "__version__", "unregistered-version")
    with pytest.raises(RuntimeError, match="require_scikit_image_0.24.0"):
        pm.settings()


def test_native_timestamps_not_video_progress_and_speed_difference():
    source = [image(20 * i) for i in range(11)] + [image(200)] * 10
    generated = [image(min(10 * i, 200)) for i in range(81)]
    alignment = pm.fixed_time_alignment(np.arange(21) / 10, np.arange(81) / 20, fps=10)
    assert alignment["source_indices"] == list(range(1, 11))
    assert alignment["generated_indices"] == list(range(2, 21, 2))
    assert pm.video_score(source, generated, alignment, "psnr")["error"] == math.inf
    slow = [image(min(5 * i, 200)) for i in range(81)]
    assert math.isfinite(pm.video_score(source, slow, alignment, "psnr")["error"])


def test_time_grid_tie_earlier_condition_excluded_and_native_frames_reused():
    plan = pm.fixed_time_alignment([0, .25, .5, .75, 1], [0, .5, 1], fps=8)
    assert plan["generated_indices"] == [1, 1, 1, 1, 1, 1, 2, 2]
    assert 0 not in plan["source_indices"]
    assert plan["generated_unique_frames"] == 2
    assert plan["requested_times_seconds"][-1] == 1


@pytest.mark.parametrize("side", ["source", "generated"])
def test_short_video_does_not_shorten_registered_window(side):
    a, b = np.arange(11) / 10, np.arange(11) / 10
    if side == "source":
        a = a[:-1]
    else:
        b = b[:-1]
    with pytest.raises(pm.InsufficientEvidence, match=side):
        pm.fixed_time_alignment(a, b)


@pytest.mark.parametrize("times", [[0, .5, .5, 1], [0, float("nan"), 1], [.1, .5, 1]])
def test_bad_clock_is_rejected(times):
    with pytest.raises(ValueError, match="native_pixel_timestamps"):
        pm.fixed_time_alignment(times, [0, .5, 1])


def test_reference_foreground_ignores_background_but_detects_foreground_error():
    left, right = image(10), image(220)
    mask = np.zeros(left.shape[:2], bool)
    mask[7:17, 10:20] = True
    right[mask] = 10
    assert pm.psnr(left, right, mask) == math.inf
    assert math.isfinite(pm.psnr(left, right))
    right[mask] = 20
    assert pm.psnr(left, right, mask) == pytest.approx(20 * math.log10(255 / 10))
    assert pm.ssim(left, right, mask) < 1
    with pytest.raises(pm.InsufficientEvidence, match="empty_reference"):
        pm.psnr(left, right, np.zeros_like(mask))
    edge = np.zeros_like(mask)
    edge[0, 0] = True
    with pytest.raises(pm.InsufficientEvidence, match="valid_ssim"):
        pm.ssim(left, right, edge)


def test_empty_foreground_in_one_frame_is_not_silently_dropped():
    seq = [image(10)] * 3
    masks = [np.ones((24, 30), bool)] * 2 + [np.zeros((24, 30), bool)]
    alignment = pm.fixed_time_alignment([0, .5, 1], [0, .5, 1], fps=2)
    with pytest.raises(pm.InsufficientEvidence, match="empty_reference"):
        pm.video_score(seq, seq, alignment, "ssim", masks)


@pytest.mark.parametrize("vp", [
    {"reference_duration_seconds": False}, {"reference_fps": float("inf")},
    {"reference_duration_seconds": .11, "reference_fps": 30},
    {"reference_duration_seconds": 1e308, "reference_fps": 1e308},
])
def test_invalid_registration_rejected(vp):
    with pytest.raises(ValueError):
        validate({"metrics": ["vp"], "vp": vp})


def test_video_equal_weight_and_missing_ids_preserved():
    records = [
        {"sample_id": "short", "metrics": {"x": {"status": "ok", "value": 10, "frames": 1}}},
        {"sample_id": "long", "metrics": {"x": {"status": "ok", "value": 30, "frames": 1000}}},
        {"sample_id": "missing", "metrics": {"x": {"status": "failed", "reason": "missing_source"}}},
        {"sample_id": "incomplete", "metrics": {"x": {"status": "insufficient_evidence", "reason": "short_video"}}},
    ]
    summary = ev.aggregate(records, "x")
    assert summary["mean"] == 20 and summary["coverage_percent"] == 50
    assert summary["registered"] == 4 and summary["failed"] == 2
    assert summary["unscored_by_status"] == {"failed": 1, "insufficient_evidence": 1}
    assert [r["sample_id"] for r in summary["failures"]] == ["missing", "incomplete"]
    records[0]["metrics"]["x"]["value"] = "+inf"
    summary = ev.aggregate(records, "x")
    assert summary["mean"] == "+inf" and summary["positive_infinity_cases"] == 1
    json.dumps(summary, allow_nan=False)
