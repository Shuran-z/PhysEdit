"""Registered conditional motion model and image objective."""
import json, hashlib, sys
from pathlib import Path
import cv2, numpy as np
from scipy.ndimage import spline_filter, map_coordinates, distance_transform_edt
from scipy.optimize import least_squares
from gravtrace.camera import Camera, quat_to_matrix
from .known_support_impulse_interval import KEYS as MK, coefficients, distance
KEYS = {'schema', 'camera', 'image_size', 'origin', 'quaternion_xyzw', 'box_size', 'primary_axis', 'secondary_axis', 'weighted_direction', 'known_interval', 'normal_condition', 'known_scheduled_velocity_reset', 'frames', 'video', 'video_sha256', 'visibility_mask_files'}

def predict(p):
    assert set(p) == KEYS and p['schema'] == 'known_control_boundary_RGB_v294' and (p['frames'] == [0, 1, 2, 3])
    assert set(p['known_interval']) == MK
    assert set(p['normal_condition']) == {'clearance_m', 'plane_normal', 'known_reset_normal_velocity', 'normal_gravity_coefficient'}
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    cap = cv2.VideoCapture(p['video'])
    ims = []
    for _ in range(4):
        (ok, im) = cap.read()
        assert ok
        ims.append(im)
    assert not cap.read()[0]
    cap.release()
    masks = [np.load(f)['mask'].astype(bool) for f in p['visibility_mask_files']]
    assert len(masks) == 4 and all((x.sum() >= 24 for x in masks))
    cam = Camera.from_dict(p['camera'], p['image_size'])
    C = np.asarray(p['camera']['matrix_world'])
    R = quat_to_matrix(p['quaternion_xyzw'])
    origin = np.asarray(p['origin'])
    half = np.asarray(p['box_size']) / 2
    (ys, xs) = np.where(distance_transform_edt(masks[0]) >= 4.0)
    pixels = np.column_stack([xs, ys]).astype(float)
    rays = np.column_stack([(pixels[:, 0] / cam.width - cam.cx) / cam.fx, (cam.cy - pixels[:, 1] / cam.height) / cam.fy, -np.ones(len(pixels))]) @ C[:3, :3].T
    lo = (C[:3, 3] - origin) @ R
    lr = rays @ R
    with np.errstate(divide='ignore', invalid='ignore'):
        t0 = (-half - lo) / lr
        t1 = (half - lo) / lr
        near = np.max(np.minimum(t0, t1), axis=1)
        far = np.min(np.maximum(t0, t1), axis=1)
    valid = (far >= np.maximum(near, 0)) & np.isfinite(near)
    pixels = pixels[valid]
    world = C[:3, 3] + rays[valid] * near[valid, None]
    assert len(world) >= 24
    filt = [cv2.GaussianBlur(im.astype(float) / 255 * mask[:, :, None], (0, 0), 0.6) / np.maximum(cv2.GaussianBlur(mask.astype(float), (0, 0), 0.6)[:, :, None], 1e-12) for (im, mask) in zip(ims, masks)]

    def sample(im, uv):
        return np.column_stack([map_coordinates(im[:, :, ch], [uv[:, 1], uv[:, 0]], order=1, mode='nearest', prefilter=False) for ch in range(3)])
    ref = sample(filt[0], pixels)
    primary = np.asarray(p['primary_axis'])
    down = np.asarray(p['secondary_axis'])
    w = np.asarray(p['weighted_direction'])
    normal = p['normal_condition']
    n = np.asarray(normal['plane_normal'])
    model = p['known_interval']
    dt = model['integration_substep_s'] * model['steps_per_observation']
    W = np.linalg.inv(np.linalg.cholesky(np.eye(3) + np.ones((3, 3))))
    wdown = float(w @ down)
    wn = float(w @ n)
    coeff = [coefficients(dict(model, steps_per_observation=k * model['steps_per_observation'])) for k in [1, 2, 3]]
    assert abs(float(w @ primary) - 1) < 1e-09 and abs(float(np.asarray(p['known_scheduled_velocity_reset']) @ w) - model['known_weighted_velocity']) < 1e-09

    def shifts(z):
        g = z[0]
        out = []
        for (k, (A, B)) in enumerate(coeff):
            dn = max(-normal['clearance_m'], A * normal['known_reset_normal_velocity'] - B * normal['normal_gravity_coefficient'] * g)
            q = A * model['known_weighted_velocity'] + B * (model['known_weighted_force'] / model['mass'] - model['weighted_gravity_coefficient'] * g)
            dx = z[k + 1]
            dy = q - wdown * dx - wn * dn
            out.append(dx * down + dy * primary + dn * n)
        return np.array(out)

    def rawres(z):
        out = []
        for (k, shift) in enumerate(shifts(z)):
            uv = cam.project(world + shift)
            raw = sample(filt[k + 1], uv) - ref
            raw -= np.mean(raw, axis=0)
            out.append(raw)
        return np.array(out)

    def residual(z):
        return np.einsum('ij,jpc->ipc', W, rawres(z)).ravel()

    def jac(z):
        eps = [0.001, 1e-05, 1e-05, 1e-05]
        return np.column_stack([(residual(np.asarray(z) + np.eye(4)[j] * eps[j]) - residual(np.asarray(z) - np.eye(4)[j] * eps[j])) / (2 * eps[j]) for j in range(4)])
    upper = 80.0
    lower = [0.1, -0.03, -0.03, -0.03]
    high = [upper, 0.03, 0.03, 0.03]
    fits = []
    for g in np.linspace(0.5, upper - 0.2, 6):
        f = least_squares(residual, [g, 0, 0, 0], jac=jac, bounds=(lower, high), x_scale=[10, 0.01, 0.01, 0.01], max_nfev=150, ftol=1e-10, xtol=1e-10, gtol=1e-10)
        fits.append(f)
    fit = min(fits, key=lambda f: np.sum(residual(f.x) ** 2))
    z = fit.x
    raw = rawres(z)
    white = residual(z)
    J = jac(z)
    H = J.T @ J
    assert np.linalg.cond(H) < 10000000000.0 and np.isfinite(H).all(), 'condition_image_unidentifiable'
    Hi = np.linalg.inv(H)
    sigma = max(0.015, float(1.4826 * np.median(np.abs(white - np.median(white)))))
    cov = 4 * sigma * sigma * Hi
    blocks = {}
    N = len(world)
    for (k, (u, v)) in enumerate(pixels):
        idx = [t * N * 3 + 3 * k + c for t in range(3) for c in range(3)]
        blocks.setdefault((int(u) // 4, int(v) // 4), []).extend(idx)
    assert len(blocks) >= 6
    scores = np.array([J[index].T @ white[index] for index in blocks.values()])
    cov += Hi @ (scores.T @ scores) @ Hi * len(blocks) / (len(blocks) - 4)
    se = float(np.sqrt(max(0.0, cov[0, 0])))
    g = float(z[0])
    rms = float(np.sqrt(np.mean(raw ** 2)))
    visible = []
    for (k, shift) in enumerate(shifts(z)):
        uv = cam.project(world + shift)
        inside = map_coordinates(distance_transform_edt(masks[k + 1]), [uv[:, 1], uv[:, 0]], order=1, mode='constant', cval=0) >= 4.0
        visible.append(float(np.mean(inside)))
    status = 'ok'
    if g <= 0.101 or g >= upper - 0.001 or np.min(np.diff(np.r_[0.0, shifts(z)[:, 1]])) < 0:
        status = 'kinetic_contact_regime_not_identified'
    elif rms > 0.05 or min(visible) < 0.8:
        status = 'condition_surface_RGB_or_identity_review_required'
    elif se / g > 0.1:
        status = 'image_precision_review_required'
    profile = []
    variance_factor = max(4.0, se * se / (sigma * sigma * Hi[0, 0]))
    limit = float(np.sum(white ** 2)) + 3.841458820694124 * sigma * sigma * variance_factor
    grid = np.unique(np.r_[np.linspace(0.1, upper, 49), g, np.linspace(max(0.1, g - 5 * se), min(upper, g + 5 * se), 61)])
    for value in grid:

        def r(dx):
            return residual(np.r_[value, dx])
        f = least_squares(r, z[1:], bounds=([-0.03] * 3, [0.03] * 3), x_scale=[0.01] * 3, max_nfev=50, ftol=1e-08, xtol=1e-08, gtol=1e-08)
        cost = float(np.sum(r(f.x) ** 2))
        feasible = bool(np.min(np.diff(np.r_[0.0, shifts(np.r_[value, f.x])[:, 1]])) >= 0)
        profile.append(dict(gravity=float(value), objective=cost, positive_primary_increments=feasible, compatible=bool(cost <= limit and feasible)))
    comp = np.array([r['compatible'] for r in profile])
    support = [r['gravity'] for r in profile if r['compatible']]
    clipped = bool(comp[0] or comp[-1])
    disconnected = bool(np.sum(np.diff(np.r_[False, comp, False].astype(int)) == 1) > 1)
    if clipped or disconnected or (not support):
        status = 'global_image_profile_review_required'
    return dict(status=status, gravity=g, gravity_standard_error=se, relative_standard_error=se / g, photo_RMS=rms, RGB_noise_floor=0.015, condition_surface_points=N, independent_4px_blocks=len(blocks), future_actual_mask_visibility_fraction=visible, observed_down_nuisance=z[1:].tolist(), predicted_shifts=shifts(z).tolist(), actual_image_condition_pixels=pixels.tolist(), projected_future_pixels=[cam.project(world + x).tolist() for x in shifts(z)], global_profile=profile, global_confidence_support=support, global_profile_disconnected=disconnected, global_profile_clipped=clipped, known_reset_and_control=True, brightness_elimination_matches_squared_error=True, foreground_normalized_blur=True, stencil_safe_margin_px=4.0, interpolation='bilinear_no_prefilter', unknown_gravity_not_in_input=True, future_source_pose_input=False, prior_fill=False, physical_horizon_s=3 * dt, frames=[0, 1, 2, 3])
