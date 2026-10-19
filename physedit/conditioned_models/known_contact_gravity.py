"""Registered conditional motion model and image objective."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from gravtrace.camera import Camera
from physedit.motion_parameters import sliding_displacement

def estimate(data):
    assert set(data) == {'camera', 'image_size', 'times_s', 'initial_time_s', 'initial_position', 'world_corners', 'downhill_direction', 'slope_angle_deg', 'known_effective_friction', 'drag_per_second', 'boxes_xyxy'}
    cam = Camera.from_dict(data['camera'], data['image_size'])
    t = np.asarray(data['times_s']) - data['initial_time_s']
    observed = np.asarray(data['boxes_xyxy'])
    origin = np.asarray(data['initial_position'])
    corners = np.asarray(data['world_corners'])
    direction = np.asarray(data['downhill_direction'])
    theta = np.deg2rad(data['slope_angle_deg'])
    mu = data['known_effective_friction']
    coefficient = float(np.sin(theta) - mu * np.cos(theta))
    assert coefficient > 0.03
    assert t.min() >= 0 and np.all(np.diff(t) > 0) and (len(t) >= 6)

    def project(x):
        g = np.exp(x[0])
        speed = x[1]
        distance = sliding_displacement(t, speed, g * coefficient, data['drag_per_second'])
        return cam.project_box((origin + distance[:, None] * direction)[:, None, :] + corners)

    def residual(x):
        boxes = project(x)
        if not np.isfinite(boxes).all():
            return np.full(observed.size, 1000000.0)
        diff = boxes - observed
        return (diff - diff.mean(axis=0)).ravel()
    fits = [least_squares(residual, [np.log(seed), 0.1], bounds=([np.log(0.1), 0.0], [np.log(80.0), 8.0]), max_nfev=400, xtol=1e-10, ftol=1e-10, gtol=1e-10) for seed in [1.0, 4.0, 16.0, 50.0]]
    fit = min(fits, key=lambda r: r.cost)
    g = float(np.exp(fit.x[0]))
    boxes = project(fit.x)
    response = project(fit.x + np.array([np.log(1.1), 0])) - boxes
    return dict(status='ok' if fit.success and 0.101 < g < 79.2 else 'at_bound', gravity=g, speed_at_condition_mps=float(fit.x[1]), cost=float(fit.cost), frames=len(t), residual_RMS_px=float(np.sqrt(np.mean(fit.fun ** 2))), ten_percent_gravity_response_RMS_px=float(np.sqrt(np.mean(response ** 2))), predicted_boxes=boxes.tolist(), initial_speed_fitted=True, known_non_target_friction=True, target_or_future_source_read=False, method='single-view known-contact coefficient, known incline, gravity and launch-speed fit')
