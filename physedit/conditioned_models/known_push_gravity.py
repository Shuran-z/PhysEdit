"""Registered conditional motion model and image objective."""
import json, hashlib, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
KEYS = {'times_s', 'distance_m', 'normal_translation_m', 'known_force_acceleration_mps2', 'known_effective_friction', 'known_initial_velocity', 'integration_substep_s'}

def validate(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    assert len(p['times_s']) == len(p['distance_m']) == len(p['normal_translation_m']) >= 6
    for k in ['times_s', 'distance_m', 'normal_translation_m', 'known_initial_velocity']:
        assert np.isfinite(p[k]).all()
    assert p['times_s'][0] == 0 and np.all(np.diff(p['times_s']) > 0) and (p['known_effective_friction'] > 0)

def predict(p):
    validate(p)
    t = np.asarray(p['times_s'])
    mu = p['known_effective_friction']
    h = p['integration_substep_s']
    v = p['known_initial_velocity']
    B = 0.5 * t * (t + h)
    observed = np.asarray(p['distance_m']) + mu * np.asarray(p['normal_translation_m'])

    def residual(x):
        return (v[0] + mu * v[2]) * t + (p['known_force_acceleration_mps2'] - mu * x[0]) * B - observed
    fits = [least_squares(residual, [seed], bounds=([0.1], [80.0]), loss='soft_l1', f_scale=0.00025, max_nfev=200, xtol=1e-11, ftol=1e-11, gtol=1e-11) for seed in [1.0, 4.0, 16.0, 50.0]]
    fit = min(fits, key=lambda r: r.cost)
    g = float(fit.x[0])
    r = residual(fit.x)
    rmse = float(np.sqrt(np.mean(r * r)))
    sensitivity = float(np.linalg.norm(mu * B))
    sigma = max(rmse, 5e-05) / sensitivity
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif rmse > 0.001:
        status = 'model_residual_review_required'
    elif sigma / g > 0.1:
        status = 'weak_image_response_review_required'
    return dict(status=status, gravity=g, curve_RMS_mm=rmse * 1000, parameter_standard_error=sigma, frames=len(t), method='single-view known fixed force and effective friction; image displacement, initial state at condition59', target_truth_input=False, future_source_states_read=False)
