"""Registered conditional motion model and image objective."""
import json, hashlib, sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
KEYS = {'times_s', 'distance_m', 'known_initial_speed_mps', 'known_effective_friction', 'known_damping_per_second', 'integration_substep_s'}

def validate(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    assert len(p['times_s']) == len(p['distance_m']) >= 4
    assert np.isfinite(p['distance_m']).all() and np.isfinite(p['times_s']).all() and (p['times_s'][0] == 0)
    assert p['known_initial_speed_mps'] > 0.03 and p['known_effective_friction'] > 0

def displacement(p, g):
    t = np.asarray(p['times_s'])
    v = p['known_initial_speed_mps']
    mu = p['known_effective_friction']
    gamma = p['known_damping_per_second']
    h = p['integration_substep_s']
    a = -mu * g
    n = np.rint(t / h)
    if gamma < 1e-12:
        n = np.minimum(n, np.floor(v / (-a * h)))
        tt = n * h
        return v * tt + 0.5 * a * tt * (tt + h)
    ratio = 1 - gamma * h
    assert 0 < ratio < 1
    stop = max(0, np.floor(np.log(-a / gamma / (v - a / gamma)) / np.log(ratio)))
    n = np.minimum(n, stop)
    tt = n * h
    A = h * ratio * -np.expm1(n * np.log(ratio)) / (1 - ratio)
    B = (tt - A) / gamma
    return v * A + a * B

def predict(p):
    validate(p)
    obs = np.asarray(p['distance_m'])

    def residual(g):
        return displacement(p, g) - obs

    def cost(g):
        rr = residual(g) / 0.00025
        return float(np.mean(0.00025 ** 2 * (np.sqrt(1 + rr * rr) - 1)))
    grid = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0]
    scores = {g: cost(g) for g in grid}
    for j in sorted(range(len(grid)), key=lambda j: scores[grid[j]])[:3]:
        (lo, hi) = (grid[max(0, j - 1)], grid[min(len(grid) - 1, j + 1)])
        fit = minimize_scalar(cost, bounds=(lo, hi), method='bounded', options={'xatol': 1e-09, 'maxiter': 150})
        scores[float(fit.x)] = float(fit.fun)
    g = min(scores, key=scores.get)
    rr = residual(g)
    rmse = float(np.sqrt(np.mean(rr * rr)))
    eps = max(0.0001, g * 0.0001)
    jac = (residual(g + eps) - residual(max(0.1, g - eps))) / (g + eps - max(0.1, g - eps))
    norm = float(np.linalg.norm(jac))
    sigma = max(rmse, 5e-05) / norm if norm > 1e-12 else float('inf')
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif rmse > 0.001:
        status = 'model_residual_review_required'
    elif sigma / g > 0.1:
        status = 'weak_image_response_review_required'
    return dict(status=status, gravity=float(g), curve_RMS_mm=rmse * 1000, parameter_standard_error=sigma if np.isfinite(sigma) else None, predicted_distance_m=displacement(p, g).tolist(), registered_frames=len(obs), physical_stop_retained=True, no_velocity_reversal=True, known_condition_speed_and_static_contact_friction=True, target_truth_input=False, future_source_states_read=False)
