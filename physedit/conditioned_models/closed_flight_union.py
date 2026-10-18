"""Registered conditional motion model and image objective."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from gravtrace.camera import Camera, quat_to_matrix
from gravtrace.motion import ballistic, torque_free

def estimate(data):
    assert set(data) == {'schema', 'camera', 'image_size', 'times_s', 'known_condition_bodies', 'observed_boxes'}
    t = np.asarray(data['times_s'], float)
    obs = np.asarray(data['observed_boxes'], float)
    assert t[0] == 0 and obs.shape == (len(t), 4)
    cam = Camera.from_dict(data['camera'], data['image_size'])
    rotations = []
    for b in data['known_condition_bodies']:
        assert set(b) == {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'inertia', 'local_vertices'}
        local = np.asarray(b['local_vertices'], float)
        R = torque_free(t, quat_to_matrix(b['quaternion_xyzw']), b['angular_velocity'], b['inertia'])
        rotations.append(np.einsum('kij,cj->kci', R, local))

    def points(g):
        return np.concatenate([ballistic(t, b['position'], b['velocity'], g, [0, 0, -1])[:, None, :] + rot for (b, rot) in zip(data['known_condition_bodies'], rotations)], axis=1)

    def predict(g):
        return cam.project_box(points(g))

    def residual(x):
        boxes = predict(float(np.exp(x[0])))
        return (boxes - boxes[0] - (obs - obs[0]))[1:].ravel()
    fits = [least_squares(residual, [np.log(seed)], bounds=([np.log(0.1)], [np.log(80.0)]), loss='soft_l1', f_scale=1.0, xtol=1e-10, ftol=1e-10, gtol=1e-10, max_nfev=200) for seed in [1.0, 4.0, 16.0, 50.0]]
    best = min(fits, key=lambda x: x.cost)
    g = float(np.exp(best.x[0]))
    boxes = predict(g)
    return dict(gravity=g, status='ok' if 0.101 < g < 79.2 else 'at_bound', cost=float(best.cost), frames=len(t), bodies=len(rotations), residual_rms_px=float(np.sqrt(np.mean(residual(best.x) ** 2))), ten_percent_gravity_response_px=float(np.sqrt(np.mean((predict(g * 1.1) - boxes) ** 2))), predicted_boxes=boxes.tolist(), method='known-condition independent free bodies; union image-box displacement', target_or_future_source_read=False)
