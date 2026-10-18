"""Registered conditional motion model and image objective."""
import json, hashlib, sys
from pathlib import Path
import cv2, numpy as np
from scipy.spatial import ConvexHull
from scipy.ndimage import distance_transform_edt, map_coordinates
from scipy.optimize import minimize_scalar, brentq
from gravtrace.camera import Camera, quat_to_matrix
from gravtrace.motion import ballistic, torque_free
from .mesh_contact_observer_masked import raycast
KEYS = {'schema', 'camera', 'image_size', 'known_condition', 'times_s', 'frames', 'video', 'video_sha256', 'visibility_mask_files', 'integration_substep_s'}
BODY = {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'linear_drag_per_second', 'angular_damping', 'mass', 'local_vertices', 'principal_inertia', 'orientation_integration_step_s'}

def predict(p):
    assert set(p) == KEYS and p['schema'] == 'known_rigid_foreground_RGB_v329', 'target_or_future_alias'
    assert set(p['known_condition']) == BODY and p['frames'] == list(range(len(p['times_s']))) and (len(p['frames']) >= 4)
    assert p['times_s'][0] == 0 and np.all(np.diff(p['times_s']) > 0)
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    cap = cv2.VideoCapture(p['video'])
    ims = []
    for k in p['frames']:
        (ok, im) = cap.read()
        assert ok
        ims.append(im)
    assert not cap.read()[0]
    cap.release()
    masks = [np.load(f)['mask'].astype(bool) for f in p['visibility_mask_files']]
    assert len(masks) == len(ims)
    distances = [distance_transform_edt(m) for m in masks]
    cam = Camera.from_dict(p['camera'], p['image_size'])
    C = np.asarray(p['camera']['matrix_world'])
    body = p['known_condition']
    origin = np.asarray(body['position'])
    R = quat_to_matrix(body['quaternion_xyzw'])
    local = np.asarray(body['local_vertices'])
    vertices = np.einsum('ij,kj->ik', local, R)
    faces = ConvexHull(local).simplices
    (ys, xs) = np.where(distances[0] >= 4.0)
    pixels = np.column_stack([xs, ys]).astype(float)
    assert len(pixels) >= 24, 'insufficient_current_interior_points'
    rays = np.column_stack([(pixels[:, 0] / cam.width - cam.cx) / cam.fx, (cam.cy - pixels[:, 1] / cam.height) / cam.fy, -np.ones(len(pixels))]) @ C[:3, :3].T
    (world, valid) = raycast(C[:3, 3], rays, (origin + vertices)[faces])
    world = world[valid]
    pixels = pixels[valid]
    assert len(world) >= 24
    filtered = [cv2.GaussianBlur(im.astype(float) / 255 * m[:, :, None], (0, 0), 0.6) / np.maximum(cv2.GaussianBlur(m.astype(float), (0, 0), 0.6)[:, :, None], 1e-12) for (im, m) in zip(ims, masks)]

    def sample(a, uv):
        return np.column_stack([map_coordinates(a[:, :, c], [uv[:, 1], uv[:, 0]], order=1, mode='nearest', prefilter=False) for c in range(3)])
    ref = sample(filtered[0], pixels)
    t = np.asarray(p['times_s'])
    local_points = np.einsum('ij,jk->ik', world - origin, R)
    rotations = torque_free(t, R, body['angular_velocity'], body['principal_inertia'], step=body['orientation_integration_step_s'], damping=body['angular_damping'])
    h = p['integration_substep_s']
    gamma = body['linear_drag_per_second']
    decay = 1 / (1 + gamma * h)
    n = np.rint(t / h)
    power = decay ** n
    A = h * decay * (1 - power) / (1 - decay)
    B = h * h * decay / (1 - decay) * (n - decay * (1 - power) / (1 - decay))
    W = np.linalg.inv(np.linalg.cholesky(np.eye(len(ims) - 1) + np.ones((len(ims) - 1, len(ims) - 1))))

    def evaluate(g, details=False):
        positions = origin + A[:, None] * body['velocity'] + B[:, None] * [0, 0, -g]
        uvs = [cam.project(np.einsum('ij,kj->ik', local_points, rotations[k]) + positions[k]) for k in range(1, len(t))]
        raw = []
        vis = []
        for (k, uv) in enumerate(uvs, 1):
            delta = sample(filtered[k], uv) - ref
            delta -= delta.mean(axis=0)
            raw.append(delta)
            vis.append(float(np.mean(map_coordinates(distances[k], [uv[:, 1], uv[:, 0]], order=1, mode='constant', cval=0) >= 4.0)))
        white = np.einsum('ij,jpc->ipc', W, np.array(raw))
        value = float(np.sum(white * white))
        return (white, np.array(raw), vis, uvs) if details else value
    grid = np.array([0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0])
    scores = {float(g): evaluate(g) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[float(grid[k])])[:3]:
        f = minimize_scalar(evaluate, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-07})
        scores[float(f.x)] = float(f.fun)
    g = min(scores, key=scores.get)
    (white, raw, visibility, uvs) = evaluate(g, True)
    eps = 0.001
    J = ((evaluate(g + eps, True)[0] - evaluate(g - eps, True)[0]) / (2 * eps)).ravel()
    rr = white.ravel()
    H = float(J @ J)
    assert H > 1e-12, 'unidentifiable_image_derivative'
    sigma = max(0.015, float(1.4826 * np.median(np.abs(rr - np.median(rr)))))
    N = len(world)
    blocks = {}
    for (k, (u, v)) in enumerate(pixels):
        blocks.setdefault((int(u) // 4, int(v) // 4), []).extend([a * N * 3 + 3 * k + c for a in range(len(ims) - 1) for c in range(3)])
    assert len(blocks) >= 6, 'insufficient_independent_spatial_blocks'
    cluster = np.array([J[ii] @ rr[ii] for ii in blocks.values()])
    variance = 4 * sigma * sigma / H + float(cluster @ cluster) / (H * H) * len(blocks) / (len(blocks) - 1)
    se = float(np.sqrt(variance))
    limit = scores[g] + 3.841458820694124 * variance * H
    gg = np.unique(np.r_[np.linspace(0.1, 80, 161), np.linspace(max(0.1, g - 5 * se), min(80, g + 5 * se), 101), g])
    profile = [dict(gravity=float(x), objective=evaluate(x)) for x in gg]
    compatible = np.array([x['objective'] <= limit for x in profile])
    clipped = bool(compatible[0] or compatible[-1])
    disconnected = int(np.sum(np.diff(np.r_[False, compatible, False].astype(int)) == 1)) > 1
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif np.sqrt(np.mean(raw ** 2)) > 0.05 or min(visibility) < 0.8:
        status = 'actual_surface_or_identity_review_required'
    elif se / g > 0.1:
        status = 'image_precision_review_required'
    if clipped or disconnected:
        status = 'global_image_profile_review_required'
    return dict(status=status, gravity=float(g), relative_standard_error=se / g, gravity_standard_error=se, photo_RMS=float(np.sqrt(np.mean(raw ** 2))), visibility_fraction=visibility, condition_points=N, independent_4px_blocks=len(blocks), profile=profile, profile_clipped=clipped, profile_disconnected=disconnected, condition_pixels=pixels.tolist(), projected_pixels=[a.tolist() for a in uvs], known_motion_unchanged=True, known_velocity_fixed=True, SAM_weights_unchanged=True, brightness_mean_matches_LS=True, foreground_normalized_gaussian=True, bilinear=True, fixed_margin_px=4.0, RGB_noise_floor=0.015, initial_state_only=True, target_gravity_input=False, future_source_pose_input=False, prior_fill=False)
