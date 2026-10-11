"""Fixed-time, full-reference pixel metrics (independent of GravTrace)."""

import math

import numpy as np
import skimage
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


class InsufficientEvidence(ValueError):
    pass


def settings(vp=None):
    if skimage.__version__ != "0.24.0":
        raise RuntimeError("pixel_metrics_require_scikit_image_0.24.0")
    vp = vp or {}
    return {
        "protocol": "phyediting_pixels_real_time_rgb_v2",
        "reference_duration_seconds": float(vp.get("reference_duration_seconds", 1.0)),
        "reference_fps": float(vp.get("reference_fps", 30.0)),
        "library": "scikit-image",
        "library_version": skimage.__version__,
        "data_range": 255,
        "color_space": "RGB",
        "ssim": {"gaussian_weights": True, "sigma": 1.5, "win_size": 11,
                 "K1": 0.01, "K2": 0.03, "use_sample_covariance": False,
                 "border": "valid", "channel_reduction": "arithmetic_mean"},
        "spatial_alignment": "source_resolution_inter_area_no_warp",
        "temporal_alignment": "nearest_native_timestamp_tie_earlier_no_time_stretch",
        "condition_in_reference_score": False,
        "frame_reduction": "arithmetic_mean",
        "video_reduction": "equal_weight",
        "foreground_support": "reference_target_mask_only",
    }


def _images(left, right):
    if left.shape != right.shape:
        raise ValueError("pixel_image_shape_mismatch")
    if left.ndim != 3 or left.shape[2] != 3 or min(left.shape[:2]) < 11:
        raise ValueError("pixel_metrics_require_three_channels_and_at_least_11_pixels")
    if left.dtype != np.uint8 or right.dtype != np.uint8:
        raise ValueError("pixel_metrics_require_uint8_data_range_255")
    # OpenCV media are BGR; explicitly convert both images to RGB.
    return left[..., ::-1], right[..., ::-1]


def psnr(left, right, mask=None):
    left, right = _images(left, right)
    if mask is None:
        if np.array_equal(left, right):
            return math.inf
        return float(peak_signal_noise_ratio(left, right, data_range=255))
    mask = _mask(mask, left.shape[:2])
    error = (left.astype(np.float64) - right.astype(np.float64)) ** 2
    mse = float(error[mask].mean())
    return math.inf if mse == 0 else float(10 * math.log10(255 ** 2 / mse))


def _mask(mask, shape):
    if mask.shape != shape or mask.dtype != np.bool_:
        raise ValueError("reference_foreground_mask_shape_or_type_mismatch")
    if not mask.any():
        raise InsufficientEvidence("empty_reference_foreground_mask")
    return mask


def ssim(left, right, mask=None):
    left, right = _images(left, right)
    score, score_map = structural_similarity(
        left, right, data_range=255, channel_axis=-1, win_size=11,
        gaussian_weights=True, sigma=1.5, use_sample_covariance=False,
        K1=0.01, K2=0.03, full=True,
    )
    if mask is None:
        return float(score)
    mask = _mask(mask, left.shape[:2])[5:-5, 5:-5]
    if not mask.any():
        raise InsufficientEvidence("no_reference_foreground_inside_valid_ssim_region")
    # Select window centres in the reference mask, never mask/blacken input pixels.
    return float(score_map[5:-5, 5:-5][mask].mean())


def fixed_time_alignment(source_times, generated_times, duration=1.0, fps=30.0):
    n = duration * fps
    if (not math.isfinite(duration) or not math.isfinite(fps) or not math.isfinite(n) or duration <= 0
            or fps <= 0 or not math.isclose(n, round(n), abs_tol=1e-8, rel_tol=1e-10)):
        raise ValueError("invalid_fixed_reference_time_grid")
    n = round(n)
    if n < 1:
        raise ValueError("empty_fixed_reference_time_grid")
    clocks = [np.asarray(t, dtype=float) for t in (source_times, generated_times)]
    for times in clocks:
        if (times.ndim != 1 or not len(times) or not np.isfinite(times).all()
                or abs(times[0]) > 1e-8 or (np.diff(times) <= 0).any()):
            raise ValueError("invalid_native_pixel_timestamps")
    missing = [kind for kind, times in zip(("source", "generated"), clocks)
               if len(times) < 2 or times[-1] + 1e-8 < duration]
    if missing:
        raise InsufficientEvidence("incomplete_fixed_reference_window: " + ",".join(missing))
    requested = np.arange(1, n + 1, dtype=float) / fps
    output = {"requested_times_seconds": requested.tolist(),
              "duration_seconds": duration, "sampling_fps": fps,
              "requested_pairs": n, "condition_excluded": True}
    for kind, times in zip(("source", "generated"), clocks):
        # Only post-condition frames are eligible, even when native fps is low.
        candidates = times[1:]
        hi = np.minimum(np.searchsorted(candidates, requested), len(candidates) - 1)
        lo = np.maximum(hi - 1, 0)
        indices = np.where(abs(candidates[lo] - requested) <= abs(candidates[hi] - requested) + 1e-12,
                           lo, hi) + 1
        output[kind + "_indices"] = indices.tolist()
        output[kind + "_actual_times_seconds"] = times[indices].tolist()
        output[kind + "_max_sampling_error_seconds"] = float(abs(times[indices] - requested).max())
        output[kind + "_unique_frames"] = len(set(indices.tolist()))
    return output


def video_score(source, generated, alignment, name, source_masks=None):
    score = ssim if name == "ssim" else psnr if name == "psnr" else None
    if score is None:
        raise ValueError("unsupported_pixel_metric")
    values = [score(source[s], generated[g], None if source_masks is None else source_masks[s])
              for s, g in zip(alignment["source_indices"], alignment["generated_indices"])]
    return {"error": float(np.mean(values)), "evaluated_pairs": len(values),
            "positive_infinity_frames": sum(v == math.inf for v in values)}


def json_value(value):
    """Standard PSNR infinity in strict JSON, without inventing a finite cap."""
    return "+inf" if value == math.inf else value
