"""Registered conditional motion model and image objective."""
import json, hashlib, sys
from pathlib import Path
import cv2, numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.spatial import ConvexHull
import itertools
from gravtrace.camera import Camera
from .isolated_stopping_gravity import displacement
KEYS = {'camera', 'image_size', 'times_s', 'origin', 'world_vertices', 'axis', 'known_initial_speed_mps', 'known_effective_friction', 'known_damping_per_second', 'integration_substep_s', 'masks'}

def predict(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    assert len(p['times_s']) == len(p['masks']) >= 4
    masks = []
    boxes = []
    for r in p['masks']:
        b = Path(r['path']).read_bytes()
        assert hashlib.sha256(b).hexdigest() == r['sha256']
        mask = np.load(r['path'])['mask']
        assert mask.shape == tuple(p['image_size'][::-1]) and mask.any()
        masks.append(mask.astype(np.float32))
        (y, x) = np.where(mask)
        boxes.append([float(x.min()), float(y.min()), float(x.max() + 1), float(y.max() + 1)])
    cam = Camera.from_dict(p['camera'], p['image_size'])
    origin = np.asarray(p['origin'])
    vertices = np.asarray(p['world_vertices'])
    vertices = vertices[ConvexHull(vertices).vertices]
    axis = np.asarray(p['axis'])
    (W, H) = p['image_size']
    dyn = {k: p[k] for k in ['times_s', 'known_initial_speed_mps', 'known_effective_friction', 'known_damping_per_second', 'integration_substep_s']}
    ext = []
    radius = float(np.linalg.norm(vertices, axis=1).max())
    envelope = np.asarray(list(itertools.product([-radius, radius], repeat=3)))
    for g in [0.1, 80.0]:
        for d in displacement(dyn, g):
            ext.append(cam.project(origin + envelope + axis * d))
    ext = np.concatenate(ext)
    assert np.isfinite(ext).all()
    lo = np.floor(ext.min(0) - 5).astype(int)
    hi = np.ceil(ext.max(0) + 5).astype(int)
    (xmin, ymin) = np.maximum(lo, [0, 0])
    (xmax, ymax) = np.minimum(hi, [W, H])
    assert xmax > xmin and ymax > ymin
    actual = [m[ymin:ymax, xmin:xmax] for m in masks]
    actual_sums = [float((m * m).sum()) for m in actual]

    def render(d, shift, yaw=0.0):
        (c, ss) = (np.cos(yaw), np.sin(yaw))
        R = np.array([[c, -ss, 0], [ss, c, 0], [0, 0, 1.0]])
        uv = cam.project(origin + vertices @ R.T + axis * d) + shift - [xmin, ymin]
        image = np.zeros((ymax - ymin, xmax - xmin), np.uint8)
        if np.isfinite(uv).all():
            hull = cv2.convexHull(np.clip(uv, -1000000.0, 1000000.0).astype(np.float32))
            cv2.fillConvexPoly(image, np.rint(hull * 256).astype(np.int32), 255, lineType=cv2.LINE_AA, shift=8)
        return image.astype(np.float32) / 255.0

    def dice(a, b, bsum):
        den = float((a * a).sum()) + bsum
        return 1.0 if den == 0 else 1 - 2 * float((a * b).sum()) / den
    align = minimize(lambda shift: dice(render(0.0, shift), actual[0], actual_sums[0]), [0.0, 0.0], method='Powell', bounds=[(-2, 2), (-2, 2)], options={'xtol': 0.005, 'ftol': 1e-09})
    shift = align.x
    profile = {}

    def per_frame(g):
        g = float(g)
        if g in profile:
            return profile[g][0]
        losses = [dice(render(0.0, shift), actual[0], actual_sums[0])]
        angles = [0.0]
        for (d, m, ms) in zip(displacement(dyn, g)[1:], actual[1:], actual_sums[1:]):
            angle_grid = [-0.35, -0.2, -0.1, 0.0, 0.1, 0.2, 0.35]
            values = [dice(render(d, shift, a), m, ms) for a in angle_grid]
            k = int(np.argmin(values))
            (lo, hi) = (angle_grid[max(0, k - 1)], angle_grid[min(len(angle_grid) - 1, k + 1)])
            fit = minimize_scalar(lambda a: dice(render(d, shift, float(a)), m, ms), bounds=(lo, hi), method='bounded', options={'xatol': 0.0003, 'maxiter': 40})
            (angle, loss) = (float(fit.x), float(fit.fun)) if fit.fun < values[k] else (angle_grid[k], values[k])
            angles.append(angle)
            losses.append(loss)
        profile[g] = (losses, angles)
        return losses

    def cost(g):
        return float(np.mean(per_frame(g)[1:]))
    grid = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0]
    scores = {g: cost(g) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[grid[k]])[:3]:
        fit = minimize_scalar(cost, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-06, 'maxiter': 80})
        scores[float(fit.x)] = float(fit.fun)
    g = min(scores, key=scores.get)
    distances = displacement(dyn, g)
    angles = profile[g][1]
    predicted = []
    for (d, a) in zip(distances, angles):
        (c, ss) = (np.cos(a), np.sin(a))
        R = np.array([[c, -ss, 0], [ss, c, 0], [0, 0, 1.0]])
        predicted.append((cam.project_box(origin + vertices @ R.T + axis * d) + np.tile(shift, 2)).tolist())
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif scores[g] > 0.2:
        status = 'mask_geometry_review_required'
    elif max(scores.values()) - min(scores.values()) < 1e-05:
        status = 'unidentifiable_mask_motion'
    return dict(status=status, gravity=float(g), objective=scores[g], condition_only_alignment_px=shift.tolist(), mean_dice_loss=scores[g], per_frame_dice_loss=per_frame(g), image_response_range=max(scores.values()) - min(scores.values()), predicted_boxes=predicted, observed_boxes=boxes, predicted_distance_m=distances.tolist(), registered_frames=len(masks), physical_stop_retained=True, no_velocity_reversal=True, fitted_image_yaw_rad=angles, orientation_is_RGB_nuisance_not_physics_forecast=True, source_future_states_read=False, target_truth_input=False, method='known isolated centre dynamics and stopping; yaw inferred only from each actual mask; single camera')
