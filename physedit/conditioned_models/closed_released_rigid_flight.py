"""Registered conditional motion model and image objective."""
import json, sys, hashlib
from pathlib import Path
import numpy as np
import cv2
from scipy.optimize import least_squares, minimize_scalar
from gravtrace.camera import Camera, quat_to_matrix
from gravtrace.motion import ballistic, torque_free

def estimate(data):
    assert set(data) == {'schema', 'camera', 'image_size', 'times_s', 'known_condition', 'observed_boxes', 'edges_visible', 'integration_substep_s'}
    assert data['schema'] == 'single_view_known_condition_released_rigid_body_v9'
    assert set(data['camera']) <= {'matrix_world', 'fov_y', 'fx', 'fy', 'cx', 'cy', 'near', 'far', 'projection', 'type'}
    body = data['known_condition']
    assert set(body) == {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'linear_drag_per_second', 'angular_damping', 'mass', 'local_vertices', 'principal_inertia', 'orientation_integration_step_s'}
    assert np.isfinite(np.asarray(body['position'] + body['velocity'] + body['angular_velocity'])).all()
    t = np.asarray(data['times_s'], float)
    obs = np.asarray(data['observed_boxes'], float)
    visible = np.asarray(data['edges_visible'], bool)
    assert len(t) >= 2 and t[0] == 0 and np.all(np.diff(t) > 0)
    assert obs.shape == visible.shape == (len(t), 4) and np.isfinite(obs).all()
    assert visible[0].all() and np.all(visible.sum(axis=1) >= 2)
    cam = Camera.from_dict(data['camera'], data['image_size'])
    local = np.asarray(body['local_vertices'], float)
    R = quat_to_matrix(body['quaternion_xyzw'])
    rotations = torque_free(t, R, body['angular_velocity'], body['principal_inertia'], step=body['orientation_integration_step_s'], damping=body['angular_damping'])
    world_vertices = np.einsum('kij,cj->kci', rotations, local)
    (W, H) = data['image_size']
    viewport = np.asarray([[0, 0], [W, 0], [W, H], [0, H]], np.float32)

    def predict(g):
        h = data['integration_substep_s']
        gamma = body['linear_drag_per_second']
        if gamma < 1e-09:
            A = t
            B = 0.5 * t * (t + h)
        else:
            decay = 1 / (1 + gamma * h)
            n = np.rint(t / h)
            power = decay ** n
            A = h * decay * (1 - power) / (1 - decay)
            B = h * h * decay / (1 - decay) * (n - decay * (1 - power) / (1 - decay))
        p = np.asarray(body['position']) + A[:, None] * body['velocity'] + B[:, None] * [0, 0, -g]
        uv = cam.project(p[:, None, :] + world_vertices)
        boxes = []
        for points in uv:
            if np.all(points >= 0) and np.all(points <= [W, H]):
                boxes.append(np.r_[points.min(0), points.max(0)])
                continue
            hull = cv2.convexHull(np.asarray(points, np.float32))
            (area, clipped) = cv2.intersectConvexConvex(hull, viewport)
            if clipped is not None and area > 0:
                pts = clipped.reshape(-1, 2)
                boxes.append(np.r_[pts.min(0), pts.max(0)])
            else:
                boxes.append(np.clip(np.r_[points.min(0), points.max(0)], [0, 0, 0, 0], [W, H, W, H]))
        return np.asarray(boxes)
    initial = predict(1.0)[0]
    shift = obs[0] - initial

    def residual(x):
        r = predict(float(np.exp(x[0]))) + shift - obs
        return r[1:][visible[1:]]

    def objective(g):
        r = residual([np.log(g)])
        return float(np.mean(np.sqrt(1 + r * r) - 1))
    grid = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0]
    scores = {g: objective(g) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[grid[k]])[:3]:
        fit = minimize_scalar(objective, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-06})
        scores[float(fit.x)] = float(fit.fun)
    g = min(scores, key=scores.get)
    err = residual([np.log(g)])
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
    return dict(gravity=g, status=status, reason=reason, registered_frames=len(t), visible_edges=int(visible.sum()), clipped_edges=int((~visible).sum()), known_condition_velocity_fixed=True, rotation_model='known-condition torque-free Euler body with declared inertia and damping', residual_rms_px=float(np.sqrt(np.mean(err ** 2))), max_residual_px=float(np.max(np.abs(err))), relative_standard_error=sigma / g, condition_edge_offset_px=shift.tolist(), predicted_boxes=(predict(g) + shift).tolist(), source_target_or_future_read=False, uses_prior_fill=False)
