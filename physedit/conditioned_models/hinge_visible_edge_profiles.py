"""Registered conditional motion model and image objective."""
import json, sys, hashlib
from pathlib import Path
import numpy as np, cv2
from scipy.spatial import ConvexHull
from scipy.ndimage import map_coordinates
from scipy.optimize import minimize_scalar
from gravtrace.camera import Camera, quat_to_matrix
from .known_floor_edge_rocking import condition, forecast

def estimate(p):
    assert set(p) == {'schema', 'video', 'video_sha256', 'camera', 'image_size', 'condition', 'local_vertices', 'frames', 'visibility_mask_files'}
    assert p['schema'] == 'single_view_known_floor_edge_surface_RGB_v8'
    condition(p['condition'])
    assert set(p['camera']) <= {'matrix_world', 'fx', 'fy', 'cx', 'cy'}
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    cam = Camera.from_dict(p['camera'], p['image_size'])
    c = p['condition']
    vertices = np.asarray(p['local_vertices'])
    R = quat_to_matrix(c['quaternion_xyzw'])
    origin = np.asarray(c['position'])
    uv = cam.project(vertices @ R.T + origin)
    hull = ConvexHull(uv).vertices
    cap = cv2.VideoCapture(p['video'])
    images = []
    masks = [np.load(x)['mask'].astype(float) for x in p['visibility_mask_files']]
    for fr in p['frames']:
        cap.set(1, fr)
        (ok, im) = cap.read()
        assert ok
        im = im.astype(float) / 255
        images.append(cv2.GaussianBlur(im[:, :, 0] - im[:, :, 2], (0, 0), 0.7))
    cap.release()
    offsets = np.arange(-3.0, 3.01, 0.5)
    local = []
    edge_ids = []
    neighbors = []
    for (e, (a, b)) in enumerate(zip(hull, np.roll(hull, -1))):
        length = np.linalg.norm(uv[b] - uv[a])
        count = int(length // 6)
        if count < 3:
            continue
        for t in np.linspace(0.03, 0.97, count):
            local.append((1 - t) * vertices[a] + t * vertices[b])
            neighbors.append((vertices[a], vertices[b]))
            edge_ids.append(e)
    local = np.asarray(local)
    neighbors = np.asarray(neighbors)

    def profile(k, pos, rot):
        centers = cam.project(local @ rot.T + pos)
        ends = cam.project(np.einsum('nij,kj->nik', neighbors, rot) + pos)
        tangent = ends[:, 1] - ends[:, 0]
        normal = np.column_stack([-tangent[:, 1], tangent[:, 0]]) / np.linalg.norm(tangent, axis=1)[:, None]
        points = centers[:, None, :] + normal[:, None, :] * offsets[None, :, None]
        raw = map_coordinates(images[k], [points[:, :, 1], points[:, :, 0]], order=3, mode='nearest')
        raw -= raw.mean(axis=1, keepdims=True)
        contrast = np.linalg.norm(raw, axis=1)
        normalized = raw / np.maximum(contrast[:, None], 0.005)
        maskvalues = map_coordinates(masks[k], [points[:, :, 1], points[:, :, 0]], order=0, mode='constant', cval=0)
        return (normalized, contrast, centers, maskvalues)
    (ref, contrast, centers, membership) = profile(0, origin, R)
    valid = (contrast > 0.06) & (membership.max(axis=1) > 0.5) & (membership.min(axis=1) < 0.5)
    assert valid.sum() >= 24, 'insufficient_actual_condition_edge_profiles'
    selected = np.flatnonzero(valid)
    blocks = (centers[selected] // 16).astype(int)

    def residual(g):
        (positions, rotations) = forecast(c, g)
        parts = []
        for k in range(1, len(p['frames'])):
            (z, con, _, membership) = profile(k, positions[k], rotations[k])
            delta = z[selected] - ref[selected]
            parts.append(delta)
        return np.asarray(parts)

    def loss(g):
        r = residual(g)
        return float(np.mean(0.1 ** 2 * (np.sqrt(1 + (r / 0.1) ** 2) - 1)))
    grid = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0]
    scores = {g: loss(g) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[grid[k]])[:3]:
        fit = minimize_scalar(loss, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-05})
        scores[float(fit.x)] = float(fit.fun)
    g = min(scores, key=scores.get)
    r = residual(g)
    step = max(0.001, 0.001 * g)
    jac = (residual(g + step) - residual(g - step)) / (2 * step)
    groups = {}
    for (b, val, j) in zip(blocks, np.moveaxis(r, 1, 0), np.moveaxis(jac, 1, 0)):
        key = tuple(b)
        groups[key] = groups.get(key, 0.0) + float(np.sum(val * j))
    bread = float(np.sum(jac * jac))
    G = len(groups)
    sigma = float(np.sqrt(G / max(G - 1, 1) * sum((v * v for v in groups.values()))) / max(bread, 1e-20))
    status = 'ok'
    if not 0.101 < g < 79.2:
        status = 'at_bound'
    elif G < 8 or sigma / g > 0.1:
        status = 'image_precision_review_required'
    elif np.sqrt(np.mean(r * r)) > 0.15:
        status = 'edge_profile_mismatch'
    (pos, rot) = forecast(c, g)
    boxes = [cam.project_box(vertices @ rr.T + pp).tolist() for (pp, rr) in zip(pos, rot)]
    return dict(status=status, gravity=g, relative_standard_error=sigma / g, cluster_standard_error=sigma, spatial_blocks_16px=G, condition_edge_profiles=int(valid.sum()), profile_normalized_RMS=float(np.sqrt(np.mean(r * r))), predicted_boxes=boxes, condition_edge_local_points=local[selected].tolist(), frames=p['frames'], all_registered_frames_and_points_retained=True, target_truth_or_future_source_read=False, known_condition_velocity_fixed=True, method='known-condition hinge; actual normalized chromatic edge profiles, gravity only')
