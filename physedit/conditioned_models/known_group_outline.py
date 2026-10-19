"""Registered conditional motion model and image objective."""
import json
import hashlib
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
from gravtrace.camera import Camera
from .known_forced_group_1d import KEYS as GROUP_KEYS, displacement
KEYS = {'schema', 'camera', 'image_size', 'origin', 'world_vertices', 'axis', 'known_group_condition', 'times_s', 'frames', 'observed_boxes'}

def predict(p):
    assert set(p) == KEYS and p['schema'] == 'known_group_time_zero_outline_v225'
    assert set(p['known_group_condition']) == GROUP_KEYS
    n = len(p['frames'])
    assert p['frames'] == list(range(n)) and n >= 4
    assert len(p['times_s']) == n and p['times_s'][0] == 0
    assert len(p['known_group_condition']['world_force_updates_from_config']) == n
    assert np.allclose(p['times_s'], np.arange(n) * p['known_group_condition']['step_s'] * p['known_group_condition']['steps_per_observation'], atol=1e-12, rtol=0)
    obs = np.asarray(p['observed_boxes'], float)
    assert obs.shape == (n, 4) and np.isfinite(obs).all()
    cam = Camera.from_dict(p['camera'], p['image_size'])
    vertices = np.asarray(p['world_vertices'])
    (origin, axis) = (np.asarray(p['origin']), np.asarray(p['axis']))
    L = np.linalg.cholesky(np.eye(n - 1) + np.ones((n - 1, n - 1)))
    W = np.linalg.inv(L)

    def projection(g):
        distances = displacement(p['known_group_condition'], g)
        return cam.project_box(origin + distances[:, None, None] * axis + vertices)

    def residual(g):
        boxes = projection(g)
        raw = boxes - boxes[0] - (obs - obs[0])
        return (raw, (W @ raw[1:]).ravel())

    def objective(g):
        return float(np.sum(residual(g)[1] ** 2))
    grid = np.linspace(0.1, 80, 321)
    costs = np.asarray([objective(g) for g in grid])
    fits = []
    for k in np.argsort(costs)[:5]:
        fits.append(minimize_scalar(objective, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-07}))
    fit = min(fits, key=lambda f: f.fun)
    g = float(fit.x)
    (raw, white) = residual(g)
    (rms, maximum) = (float(np.sqrt(np.mean(raw[1:] ** 2))), float(np.abs(raw[1:]).max()))
    eps = max(0.001, 0.001 * g)
    derivative = (residual(g + eps)[1] - residual(max(0.1, g - eps))[1]) / (g + eps - max(0.1, g - eps))
    sigma_px = max(1.0, float(np.sqrt(np.mean(white ** 2))))
    norm = float(np.linalg.norm(derivative))
    se = sigma_px / norm if norm > 1e-12 else float('inf')
    relative = se / g
    refined = np.linspace(max(0.1, g - 5 * se), min(80.0, g + 5 * se), 201) if np.isfinite(se) else np.asarray([g])
    confidence_grid = np.unique(np.concatenate([grid, refined, [g]]))
    confidence_costs = np.asarray([objective(value) for value in confidence_grid])
    compatible = confidence_costs <= fit.fun + 3.841458820694124 * sigma_px ** 2
    support = confidence_grid[compatible]
    clipped = bool(len(support) and (compatible[0] or compatible[-1]))
    disconnected = bool(np.sum(np.diff(np.r_[False, compatible, False].astype(int)) == 1) > 1)
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif rms > 2 or maximum > 4:
        status = 'geometry_image_model_review_required'
    elif relative > 0.1 or clipped or disconnected or (not len(support)):
        status = 'image_precision_review_required'
    return dict(status=status, gravity=g, residual_RMS_px=rms, maximum_residual_px=maximum, condition_correlated_standard_error=se if np.isfinite(se) else None, relative_standard_error=relative if np.isfinite(relative) else None, integer_pixel_floor=1.0, global_confidence_interval_grid=support.tolist(), global_interval_clipped=clipped, global_interval_disconnected=disconnected, predicted_boxes=projection(g).tolist(), registered_frames=n, known_condition_fixed=True, source_truth_or_future_states_read=False, new_prior_fill=False, method='single-view known driven upper-stack group; g only; shared condition noise')
