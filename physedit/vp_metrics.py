"""V/P diagnostics, with versioned full-reference pixel metrics.

Source SHA256: 9a7d4766bbaf083181c84e40fff6155b7cc551b2394cb0798c7500c3692765b7.
Source SHA applies to the original motion/visual diagnostics below.
RGB pixel metrics now use the separately registered v2 implementation.
"""

from __future__ import annotations
import math
import cv2
import numpy as np
from .pixel_metrics import psnr, ssim


def resize_like(frame: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if frame.shape[:2] == reference.shape[:2]:
        return frame
    return cv2.resize(
        frame, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_AREA
    )


def estimate_homography(left: np.ndarray, right: np.ndarray) -> np.ndarray | None:
    gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
    detector = cv2.ORB_create(nfeatures=1500, fastThreshold=7)
    key_l, des_l = detector.detectAndCompute(gray_l, None)
    key_r, des_r = detector.detectAndCompute(gray_r, None)
    if des_l is None or des_r is None or len(key_l) < 8 or len(key_r) < 8:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des_l, des_r, k=2)
    good = [a for a, b in matches if a.distance < 0.75 * b.distance]
    if len(good) < 8:
        return None
    src = np.float32([key_l[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([key_r[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    homography, _ = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    return homography


def camera_motion_diagnostics(
    frames: list[np.ndarray], start: int, minimum_coverage: float = 0.5
) -> dict:
    base = frames[start]
    height, width = base.shape[:2]
    corners = np.float32(
        [[[0, 0]], [[width - 1, 0]], [[width - 1, height - 1]], [[0, height - 1]]]
    )
    values = []
    total = len(frames) - start - 1
    for frame in frames[start + 1 :]:
        homography = estimate_homography(base, resize_like(frame, base))
        if homography is None or not np.isfinite(homography).all():
            continue
        value = np.mean(
            np.linalg.norm(
                cv2.perspectiveTransform(corners, homography) - corners, axis=2
            )
        ) / math.hypot(width, height)
        if np.isfinite(value):
            values.append(float(value))
    coverage = len(values) / total if total else 0.0
    return {
        "error": (
            float(np.median(values))
            if values and coverage >= minimum_coverage
            else None
        ),
        "coverage": coverage,
        "valid_pairs": len(values),
        "total_pairs": total,
        "minimum_coverage": minimum_coverage,
    }


def background_flicker_diagnostics(
    frames: list[np.ndarray], masks: list[np.ndarray], minimum_coverage: float = 0.8
) -> dict:
    values = []
    total = max(0, len(frames) - 1)
    kernel = np.ones((15, 15), np.uint8)
    for index in range(total):
        if (
            index + 1 >= len(masks)
            or min(masks[index].sum(), masks[index + 1].sum()) < 10
        ):
            continue
        left = frames[index]
        right = resize_like(frames[index + 1], left)
        h, w = left.shape[:2]
        homography = estimate_homography(right, left)
        if homography is None or not np.isfinite(homography).all():
            continue
        right = cv2.warpPerspective(right, homography, (w, h))
        right_mask = cv2.warpPerspective(
            masks[index + 1].astype(np.uint8),
            homography,
            (w, h),
            flags=cv2.INTER_NEAREST,
        )
        warp_valid = cv2.warpPerspective(
            np.ones((h, w), np.uint8), homography, (w, h), flags=cv2.INTER_NEAREST
        ).astype(bool)
        foreground = np.logical_or(masks[index], right_mask).astype(np.uint8)
        valid = warp_valid & ~cv2.dilate(foreground, kernel).astype(bool)
        if valid.sum() <= 100:
            continue
        residual = (
            cv2.absdiff(
                cv2.cvtColor(left, cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(right, cv2.COLOR_BGR2GRAY),
            )
            / 255.0
        )
        values.append(float(residual[valid].mean()))
    coverage = len(values) / total if total else 0.0
    return {
        "error": (
            float(np.mean(values)) if values and coverage >= minimum_coverage else None
        ),
        "coverage": coverage,
        "valid_pairs": len(values),
        "total_pairs": total,
        "minimum_coverage": minimum_coverage,
        "foreground_warped_with_image": True,
        "padding_excluded": True,
        "percentile_fallback": False,
    }


def normalized_shape(mask: np.ndarray, size: int = 128) -> np.ndarray | None:
    ys, xs = np.where(mask)
    if len(xs) < 10:
        return None
    crop = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].astype(np.uint8)
    scale = min((size - 8) / crop.shape[1], (size - 8) / crop.shape[0])
    resized = cv2.resize(
        crop,
        (max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale))),
        interpolation=cv2.INTER_NEAREST,
    ).astype(bool)
    canvas = np.zeros((size, size), dtype=bool)
    y0 = (size - resized.shape[0]) // 2
    x0 = (size - resized.shape[1]) // 2
    canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
    return canvas


def silhouette_structure_error(masks: list[np.ndarray], start: int) -> float:
    if start >= len(masks):
        return math.nan
    reference = normalized_shape(masks[start])
    if reference is None:
        return math.nan
    errors = []
    for mask in masks[start + 1 :]:
        current = normalized_shape(mask)
        if current is None:
            continue
        union = np.logical_or(reference, current).sum()
        if union:
            errors.append(1.0 - float(np.logical_and(reference, current).sum() / union))
    return float(np.mean(errors)) if errors else math.nan


def motion_region(masks: list[np.ndarray], start: int) -> np.ndarray | None:
    if start >= len(masks):
        return None
    base = masks[start]
    region = np.zeros_like(base, dtype=bool)
    for mask in masks[start + 1 :]:
        if mask.shape != base.shape:
            mask = cv2.resize(
                mask.astype(np.uint8),
                (base.shape[1], base.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
        region |= np.logical_xor(base, mask)
    return region


def motion_region_iou(
    source: list[np.ndarray],
    generated: list[np.ndarray],
    source_start: int,
    generated_start: int,
) -> float:
    src = motion_region(source, source_start)
    gen = motion_region(generated, generated_start)
    if src is None or gen is None:
        return math.nan
    if gen.shape != src.shape:
        gen = cv2.resize(
            gen.astype(np.uint8),
            (src.shape[1], src.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
    union = np.logical_or(src, gen).sum()
    return float(np.logical_and(src, gen).sum() / union) if union else 1.0


def centroid_track(masks: list[np.ndarray], start: int) -> np.ndarray:
    points = []
    for mask in masks[start:]:
        ys, xs = np.where(mask)
        if len(xs) < 10:
            points.append((math.nan, math.nan))
        else:
            points.append((float(xs.mean()), float(ys.mean())))
    return np.asarray(points, dtype=np.float64).reshape(-1, 2)


def interpolate_track(track: np.ndarray, count: int) -> np.ndarray | None:
    if len(track) < 3:
        return None
    valid = np.isfinite(track).all(axis=1)
    if valid.sum() < 3:
        return None
    old_t = np.linspace(0.0, 1.0, len(track))[valid]
    new_t = np.linspace(0.0, 1.0, count)
    return np.column_stack(
        [
            np.interp(new_t, old_t, track[valid, 0]),
            np.interp(new_t, old_t, track[valid, 1]),
        ]
    )


def trajectory_error(
    source: list[np.ndarray],
    generated: list[np.ndarray],
    source_start: int,
    generated_start: int,
) -> float:
    src = interpolate_track(centroid_track(source, source_start), 32)
    gen = interpolate_track(centroid_track(generated, generated_start), 32)
    if src is None or gen is None:
        return math.nan
    src -= src[0]
    gen -= gen[0]
    height, width = source[0].shape
    gen[:, 0] *= width / generated[0].shape[1]
    gen[:, 1] *= height / generated[0].shape[0]
    return float(np.mean(np.linalg.norm(src - gen, axis=1)) / math.hypot(width, height))
