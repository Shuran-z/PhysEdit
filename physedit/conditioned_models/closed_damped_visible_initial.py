"""Registered conditional motion model and image objective."""
import json, sys, hashlib
from pathlib import Path
import numpy as np
import cv2
from scipy.optimize import least_squares
from gravtrace.camera import Camera, quat_to_matrix
from gravtrace.motion import ballistic

def estimate(data):
    assert set(data) == {'schema', 'camera', 'image_size', 'times_s', 'known_condition', 'observed_boxes', 'edges_visible'}
    assert data['schema'] == 'single_view_known_condition_damped_low_spin_v1'
    assert set(data['camera']) <= {'matrix_world', 'fov_y', 'fx', 'fy', 'cx', 'cy', 'near', 'far', 'projection', 'type'}
    body = data['known_condition']
    assert set(body) == {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'linear_drag_per_second', 'angular_damping', 'mass', 'local_vertices'}
    assert np.isfinite(np.asarray(body['position'] + body['velocity'] + body['angular_velocity'])).all()
    t = np.asarray(data['times_s'], float)
    obs = np.asarray(data['observed_boxes'], float)
    visible = np.asarray(data['edges_visible'], bool)
    assert len(t) >= 4 and t[0] == 0 and np.all(np.diff(t) > 0)
    assert obs.shape == visible.shape == (len(t), 4) and np.isfinite(obs).all()
    assert visible[0, 2:].all() and np.all(visible.sum(axis=1) >= 2)
    cam = Camera.from_dict(data['camera'], data['image_size'])
    local = np.asarray(body['local_vertices'], float)
    R = quat_to_matrix(body['quaternion_xyzw'])
    local = np.einsum('ij,kj->ik', local, R)
    (W, H) = data['image_size']
    viewport = np.asarray([[0, 0], [W, 0], [W, H], [0, H]], np.float32)

    def predict(g):
        p = ballistic(t, body['position'], body['velocity'], g, [0, 0, -1], body['linear_drag_per_second'])
        uv = cam.project(p[:, None, :] + local)
        boxes = []
        for points in uv:
            hull = cv2.convexHull(np.asarray(points, np.float32))
            (area, clipped) = cv2.intersectConvexConvex(hull, viewport)
            if clipped is not None and area > 0:
                pts = clipped.reshape(-1, 2)
                boxes.append(np.r_[pts.min(0), pts.max(0)])
            else:
                boxes.append(np.clip(np.r_[points.min(0), points.max(0)], [0, 0, 0, 0], [W, H, W, H]))
        return np.asarray(boxes)
    initial = predict(1.0)[0]
    shift = np.tile(obs[0, 2:] - initial[2:], 2)

    def residual(x):
        r = predict(float(np.exp(x[0]))) + shift - obs
        return r[1:][visible[1:]]
    fits = [least_squares(residual, [np.log(seed)], bounds=([np.log(0.1)], [np.log(80.0)]), loss='soft_l1', f_scale=1.0, diff_step=0.001, xtol=1e-08, ftol=1e-08, gtol=1e-08, max_nfev=160) for seed in [1.0, 4.0, 16.0, 50.0]]
    fit = min(fits, key=lambda r: r.cost)
    g = float(np.exp(fit.x[0]))
    err = residual(fit.x)
    sensitivity = (predict(g * 1.001) - predict(g * 0.999)) / (0.002 * g)
    derivative = sensitivity[1:][visible[1:]]
    sigma = max(0.25, float(np.sqrt(np.mean(err ** 2)))) / max(float(np.linalg.norm(derivative)), 1e-12)
    status = 'ok'
    reason = None
    if not 0.101 < g < 79.2:
        status = 'at_bound'
        reason = 'registered gravity boundary'
    elif sigma / g > 0.1:
        status = 'unidentifiable'
        reason = 'image response insufficient for registered precision'
    elif np.sqrt(np.mean(err ** 2)) > 2 or np.max(np.abs(err)) > 4:
        status = 'observation_mismatch'
        reason = 'visible-edge image residual gate'
    return dict(gravity=g, status=status, reason=reason, registered_frames=len(t), visible_edges=int(visible.sum()), clipped_edges=int((~visible).sum()), known_condition_velocity_fixed=True, rotation_model='source-qualified low-spin constant-orientation approximation', residual_rms_px=float(np.sqrt(np.mean(err ** 2))), max_residual_px=float(np.max(np.abs(err))), relative_standard_error=sigma / g, condition_edge_offset_px=shift.tolist(), predicted_boxes=(predict(g) + shift).tolist(), source_target_or_future_read=False, uses_prior_fill=False)
