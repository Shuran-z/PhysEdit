"""Registered conditional motion model and image objective."""
import hashlib, json, sys
from pathlib import Path
import cv2, numpy as np
from scipy.ndimage import spline_filter, map_coordinates
from scipy.optimize import minimize_scalar
from gravtrace.camera import Camera, quat_to_matrix
from scipy.spatial import ConvexHull
from .known_forced_piecewise_floor import forecast, condition, BASE_KEYS, KEYS as CONDITION_KEYS
from physedit.motion_parameters import sliding_displacement
from .mesh_contact_observer_masked import raycast
KEYS = {'schema', 'video', 'video_sha256', 'camera', 'image_size', 'condition', 'local_vertices', 'frames', 'visibility_mask_files'}

def predict(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    assert p['schema'] == 'single_view_known_forced_floor_surface_RGB_v147'
    assert set(p['camera']) <= {'matrix_world', 'fx', 'fy', 'cx', 'cy'}
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    assert set(p['condition']) == CONDITION_KEYS, 'unexpected_condition_alias'
    assert all((set(a) == {'time_s', 'force_world_N'} for a in p['condition']['world_force_updates'])), 'unexpected_control_alias'
    condition({k: p['condition'][k] for k in BASE_KEYS})
    cam = Camera.from_dict(p['camera'], p['image_size'])
    C = np.asarray(p['camera']['matrix_world'])
    origin = np.asarray(p['condition']['position'])
    R0 = quat_to_matrix(p['condition']['quaternion_xyzw'])
    local = np.asarray(p['local_vertices'])
    verts = np.einsum('ij,kj->ik', local, R0)
    faces = ConvexHull(local).simplices
    masks = [np.load(f)['mask'] for f in p['visibility_mask_files']]
    mask_distances = [cv2.distanceTransform(np.asarray(m, np.uint8), cv2.DIST_L2, 5) for m in masks]
    cap = cv2.VideoCapture(p['video'])
    images = []
    for fr in p['frames']:
        cap.set(1, fr)
        (ok, im) = cap.read()
        assert ok
        images.append(im)
    cap.release()
    assert len(images) == len(p['condition']['times_s']) >= 4
    uv = cam.project(origin + verts)
    region = np.zeros(images[0].shape[:2], np.uint8)
    cv2.fillConvexPoly(region, cv2.convexHull(uv.astype(np.float32)).astype(int), 1)
    region = cv2.erode(region, np.ones((11, 11), np.uint8)).astype(bool) & (mask_distances[0] >= 5.0)
    gray = cv2.cvtColor(images[0], cv2.COLOR_BGR2GRAY)
    mag = np.hypot(cv2.Sobel(gray, cv2.CV_64F, 1, 0), cv2.Sobel(gray, cv2.CV_64F, 0, 1))
    (ys, xs) = np.where(region & (mag > 8))
    order = np.argsort(-mag[ys, xs], kind='stable')
    chosen = []
    cells = set()
    for i in order:
        cell = (int(xs[i]) // 2, int(ys[i]) // 2)
        if cell not in cells:
            chosen.append([xs[i], ys[i]])
            cells.add(cell)
        if len(chosen) >= 350:
            break
    pixels = np.asarray(chosen, float)
    assert len(pixels) >= 24, 'condition_texture_insufficient'
    rays = np.column_stack([(pixels[:, 0] / cam.width - cam.cx) / cam.fx, (cam.cy - pixels[:, 1] / cam.height) / cam.fy, -np.ones(len(pixels))]) @ C[:3, :3].T
    (world, valid) = raycast(C[:3, 3], rays, (origin + verts)[faces])
    pixels = pixels[valid]
    world = world[valid]
    assert len(world) >= 24
    filtered = [np.stack([spline_filter(cv2.GaussianBlur(im.astype(float) / 255, (0, 0), 1.0)[:, :, ch], order=3) for ch in range(3)], 2) for im in images]

    def sample(im, uv):
        return np.stack([map_coordinates(im[:, :, ch], [uv[:, 1], uv[:, 0]], order=3, mode='nearest', prefilter=False) for ch in range(3)], 1)
    ref = sample(filtered[0], pixels)
    t = np.asarray(p['condition']['times_s'])
    local_points = np.einsum('ij,jk->ik', world - origin, R0)
    pose_cache = {}
    domain_failures = {}

    def poses(g):
        if g not in pose_cache:
            try:
                pose_cache[g] = forecast(p['condition'], g)
            except (AssertionError, RuntimeError, ValueError) as e:
                pose_cache[g] = None
                domain_failures[g] = dict(type=type(e).__name__, reason=str(e))
        return pose_cache[g]

    def evaluate(g, details=False):
        losses = []
        rms = []
        boxes = []
        visible_counts = []
        result = poses(g)
        if result is None:
            return ([1.0] * len(t), [1.0] * len(t), [], [0] * len(t)) if details else 1.0
        (positions, rotations) = result
        for (k, (pos, rot)) in enumerate(zip(positions, rotations)):
            v = cam.project(np.einsum('ij,kj->ik', local_points, rot) + pos)
            assert np.isfinite(v).all()
            visible = map_coordinates(mask_distances[k], [v[:, 1], v[:, 0]], order=1, mode='constant', cval=0) >= 5.0
            visible_counts.append(int(visible.sum()))
            if visible.sum() < max(24, len(world) // 2):
                losses.append(1.0)
                rms.append(1.0)
                if details:
                    boxes.append(cam.project_box(np.einsum('ij,kj->ik', local, rot) + pos).tolist())
                continue
            delta = sample(filtered[k], v)[visible] - ref[visible]
            delta -= np.median(delta)
            losses.append(float(np.mean(0.04 ** 2 * (np.sqrt(1 + (delta / 0.04) ** 2) - 1))))
            rms.append(float(np.sqrt(np.mean(delta ** 2))))
            if details:
                boxes.append(cam.project_box(np.einsum('ij,kj->ik', local, rot) + pos).tolist())
        return (losses, rms, boxes, visible_counts) if details else float(np.mean(losses[1:]))
    grid = np.linspace(0.1, 80.0, 161).tolist()
    grid_details = {g: evaluate(g, True) for g in grid}
    minimum = max(24, len(world) // 2)
    supported = [g for g in grid if all((n >= minimum for n in grid_details[g][3]))]
    if not supported:
        return dict(status='insufficient_visible_surface_support', gravity=None, registered_frames=len(t), surface_points=len(world), minimum_visible_points_per_frame=minimum, visible_points_by_trial={str(g): grid_details[g][3] for g in grid}, optimization_started=False, all_registered_frames_retained=True, source_future_states_read=False, target_truth_input=False)
    scores = {g: float(np.mean(grid_details[g][0][1:])) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[grid[k]])[:5]:
        f = minimize_scalar(evaluate, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-05, 'maxiter': 100})
        scores[float(f.x)] = float(f.fun)
    g = min(scores, key=scores.get)
    (losses, rms, boxes, visible_counts) = evaluate(g, True)
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif max(rms) > 0.05:
        status = 'photometric_model_review_required'
    return dict(status=status, gravity=g, objective=scores[g], photo_RMS=rms, per_frame_loss=losses, predicted_boxes=boxes, condition_surface_local_points=local_points.tolist(), condition_surface_pixels=pixels.tolist(), registered_frames=len(t), surface_points=len(world), visible_points_per_frame=visible_counts, actual_mask_pixel_visibility_used=True, known_condition_velocity_not_fitted=True, source_future_states_read=False, target_truth_input=False, method='direct single-view known force and floor surface RGB, original actual mask visibility; gravity only', model_domain_failures=domain_failures)
