"""Registered conditional motion model and image objective."""
import json, sys, hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from gravtrace.camera import Camera
from .known_floor_edge_rocking import forecast, condition

def estimate(p):
    assert set(p) == {'schema', 'camera', 'image_size', 'condition', 'local_vertices', 'observed_boxes'}
    assert p['schema'] == 'single_view_known_floor_edge_gravity_v2'
    assert set(p['camera']) <= {'matrix_world', 'fx', 'fy', 'cx', 'cy'}
    condition(p['condition'])
    cam = Camera.from_dict(p['camera'], p['image_size'])
    vertices = np.asarray(p['local_vertices'], float)
    obs = np.asarray(p['observed_boxes'], float)
    assert obs.shape == (len(p['condition']['times_s']), 4) and np.isfinite(obs).all()

    def project(g):
        (pos, rot) = forecast(p['condition'], g)
        world = pos[:, None, :] + np.einsum('kij,cj->kci', rot, vertices)
        return cam.project_box(world)
    first = project(1.0)[0]

    def residual(x):
        r = project(float(np.exp(x[0]))) - first - (obs - obs[0])
        return r[1:].ravel()
    fits = [least_squares(residual, [np.log(g)], bounds=([np.log(0.1)], [np.log(80.0)]), loss='soft_l1', f_scale=1.0, xtol=1e-08, gtol=1e-08, ftol=1e-08, max_nfev=120) for g in [1.0, 4.0, 16.0, 50.0]]
    fit = min(fits, key=lambda r: r.cost)
    g = float(np.exp(fit.x[0]))
    r = residual(fit.x)
    pred = project(g)
    jac = (project(g * 1.001) - project(g * 0.999)) / (g * 0.002)
    noise = max(0.25, float(np.sqrt(np.mean(r * r))))
    relative_se = noise / max(np.linalg.norm(jac[1:]), 1e-12) / g
    status = 'ok'
    reason = None
    if not 0.101 < g < 79.2:
        status = 'at_bound'
        reason = 'registered gravity bounds'
    elif relative_se > 0.1:
        status = 'unidentifiable'
        reason = 'insufficient single-view gravity response'
    elif np.sqrt(np.mean(r * r)) > 2 or abs(r).max() > 4:
        status = 'observation_mismatch'
        reason = 'image residual gate'
    return dict(gravity=g, status=status, reason=reason, frames=len(obs), residual_rms_px=float(np.sqrt(np.mean(r * r))), max_residual_px=float(abs(r).max()), relative_standard_error=float(relative_se), predicted_boxes=(pred + obs[0] - first).tolist(), source_target_or_future_read=False, prior_fill=False, known_condition_velocity_and_angular_velocity=True, method='known floor-edge rigid rotation with supported normal micro-bounce; gravity-only image displacement')
