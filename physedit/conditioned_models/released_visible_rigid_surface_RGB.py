"""Registered conditional motion model and image objective."""
import hashlib, json, sys
from pathlib import Path
import cv2, numpy as np
from scipy.ndimage import spline_filter, map_coordinates
from scipy.optimize import minimize_scalar
from gravtrace.camera import Camera, quat_to_matrix
from scipy.spatial import ConvexHull
from gravtrace.camera import quat_to_matrix
from gravtrace.motion import torque_free
from physedit.motion_parameters import sliding_displacement
from .mesh_contact_observer_masked import raycast
KEYS = {'schema', 'video', 'video_sha256', 'camera', 'image_size', 'condition', 'local_vertices', 'frames', 'visibility_mask_files', 'times_s', 'integration_substep_s'}

def predict(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    assert p['schema'] == 'single_view_known_released_rigid_surface_RGB_v10'
    assert set(p['camera']) <= {'matrix_world', 'fx', 'fy', 'cx', 'cy'}
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    assert set(p['condition']) == {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'linear_drag_per_second', 'angular_damping', 'mass', 'local_vertices', 'principal_inertia', 'orientation_integration_step_s'}
    cam = Camera.from_dict(p['camera'], p['image_size'])
    C = np.asarray(p['camera']['matrix_world'])
    origin = np.asarray(p['condition']['position'])
    R0 = quat_to_matrix(p['condition']['quaternion_xyzw'])
    local = np.asarray(p['local_vertices'])
    verts = np.einsum('ij,kj->ik', local, R0)
    faces = ConvexHull(local).simplices
    masks = [np.load(f)['mask'] for f in p['visibility_mask_files']]
    cap = cv2.VideoCapture(p['video'])
    images = []
    for fr in p['frames']:
        cap.set(1, fr)
        (ok, im) = cap.read()
        assert ok
        images.append(im)
    cap.release()
    assert len(images) == len(p['times_s']) >= 2
    uv = cam.project(origin + verts)
    region = np.zeros(images[0].shape[:2], np.uint8)
    cv2.fillConvexPoly(region, cv2.convexHull(uv.astype(np.float32)).astype(int), 1)
    region = cv2.erode(region, np.ones((3, 3), np.uint8)).astype(bool) & masks[0]
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
    t = np.asarray(p['times_s'])
    local_points = np.einsum('ij,jk->ik', world - origin, R0)
    h = p['integration_substep_s']
    gamma = p['condition']['linear_drag_per_second']
    if gamma < 1e-09:
        A = t
        B = 0.5 * t * (t + h)
    else:
        decay = 1 / (1 + gamma * h)
        n = np.rint(t / h)
        power = decay ** n
        A = h * decay * (1 - power) / (1 - decay)
        B = h * h * decay / (1 - decay) * (n - decay * (1 - power) / (1 - decay))
    rotations = torque_free(t, R0, p['condition']['angular_velocity'], p['condition']['principal_inertia'], step=p['condition']['orientation_integration_step_s'], damping=p['condition']['angular_damping'])

    def poses(g):
        pos = origin + A[:, None] * p['condition']['velocity'] + B[:, None] * [0, 0, -g]
        return (pos, rotations)

    def evaluate(g, details=False):
        losses = []
        rms = []
        boxes = []
        visible_counts = []
        (positions, rotations) = poses(g)
        for (k, (pos, rot)) in enumerate(zip(positions, rotations)):
            v = cam.project(np.einsum('ij,kj->ik', local_points, rot) + pos)
            assert np.isfinite(v).all()
            visible = map_coordinates(masks[k].astype(float), [v[:, 1], v[:, 0]], order=0, mode='constant', cval=0) > 0.5
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
    grid = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 80.0]
    scores = {g: evaluate(g) for g in grid}
    for k in sorted(range(len(grid)), key=lambda k: scores[grid[k]])[:3]:
        f = minimize_scalar(evaluate, bounds=(grid[max(0, k - 1)], grid[min(len(grid) - 1, k + 1)]), method='bounded', options={'xatol': 1e-05, 'maxiter': 100})
        scores[float(f.x)] = float(f.fun)
    g = min(scores, key=scores.get)
    (losses, rms, boxes, visible_counts) = evaluate(g, True)
    status = 'ok'
    if g <= 0.101 or g >= 79.2:
        status = 'at_bound'
    elif max(rms) > 0.05:
        status = 'photometric_model_review_required'
    return dict(status=status, gravity=g, objective=scores[g], photo_RMS=rms, per_frame_loss=losses, predicted_boxes=boxes, condition_surface_local_points=local_points.tolist(), condition_surface_pixels=pixels.tolist(), registered_frames=len(t), surface_points=len(world), visible_points_per_frame=visible_counts, actual_mask_pixel_visibility_used=True, known_condition_velocity_not_fitted=True, source_future_states_read=False, target_truth_input=False, method='direct single-view released rigid-body surface RGB; known velocity, inertia and damping; gravity only')
