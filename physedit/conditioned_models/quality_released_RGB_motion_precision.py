import json, sys, hashlib
from pathlib import Path
import cv2, numpy as np
from scipy.ndimage import spline_filter, map_coordinates
from gravtrace.camera import Camera, quat_to_matrix
from gravtrace.motion import torque_free

def audit(input_path, prediction_path, output_path):
    source = Path(input_path)
    prediction = Path(prediction_path)
    output = Path(output_path)
    p = json.load(open(source))
    r = json.load(open(prediction))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == r['closed_input_sha256']
    assert hashlib.sha256(Path(p['video']).read_bytes()).hexdigest() == p['video_sha256']
    cam = Camera.from_dict(p['camera'], p['image_size'])
    R0 = quat_to_matrix(p['condition']['quaternion_xyzw'])
    local = np.asarray(r['condition_surface_local_points'])
    pixels = np.asarray(r['condition_surface_pixels'])
    cap = cv2.VideoCapture(p['video'])
    filtered = []
    for fr in p['frames']:
        cap.set(1, fr)
        (ok, im) = cap.read()
        assert ok
        filtered.append(np.stack([spline_filter(cv2.GaussianBlur(im.astype(float) / 255, (0, 0), 1.0)[:, :, ch], order=3) for ch in range(3)], 2))
    cap.release()

    def sample(im, uv):
        return np.stack([map_coordinates(im[:, :, ch], [uv[:, 1], uv[:, 0]], order=3, mode='nearest', prefilter=False) for ch in range(3)], 1)
    reference = sample(filtered[0], pixels)
    t = np.asarray(p['times_s'])
    h = p['integration_substep_s']
    gamma = p['condition']['linear_drag_per_second']
    decay = 1 / (1 + gamma * h)
    n = np.rint(t / h)
    power = decay ** n
    A = h * decay * (1 - power) / (1 - decay)
    B = h * h * decay / (1 - decay) * (n - decay * (1 - power) / (1 - decay))
    g = r['gravity']
    step = max(0.001, g * 0.001)
    parts = []
    rotations = torque_free(t, R0, p['condition']['angular_velocity'], p['condition']['principal_inertia'], step=p['condition']['orientation_integration_step_s'], damping=p['condition']['angular_damping'])
    for k in range(1, len(t)):
        mask = np.load(p['visibility_mask_files'][k])['mask']
        records = []
        for candidate in [g - step, g, g + step]:
            pos = np.asarray(p['condition']['position']) + A[k] * np.asarray(p['condition']['velocity']) + B[k] * np.asarray([0, 0, -candidate])
            uv = cam.project(local @ rotations[k].T + pos)
            visible = map_coordinates(mask.astype(float), [uv[:, 1], uv[:, 0]], order=0, mode='constant', cval=0) > 0.5
            delta = sample(filtered[k], uv) - reference
            delta -= np.median(delta)
            records.append((visible, delta))
        valid = records[0][0] & records[1][0] & records[2][0]
        residual = records[1][1][valid]
        derivative = (records[2][1][valid] - records[0][1][valid]) / (2 * step)
        block = (pixels[valid] // 16).astype(int)
        parts.extend(((tuple(b), v, j) for (b, v, j) in zip(block, residual, derivative)))
    groups = {}
    for (block, value, jac) in parts:
        groups[block] = groups.get(block, 0.0) + float(np.sum(value * jac))
    bread = sum((float(np.sum(j * j)) for (_, _, j) in parts))
    G = len(groups)
    sigma = float(np.sqrt(G / max(G - 1, 1) * sum((v * v for v in groups.values()))) / max(bread, 1e-20))
    relative = sigma / g
    report = dict(status='image_precision_pass' if G >= 8 and relative <= 0.1 else 'image_precision_review_required', spatial_blocks_16px=G, visible_surface_samples=len(parts), gravity=g, cluster_standard_error=sigma, relative_standard_error=relative, same_actual_frames=True, reference_gravity_or_future_source_read=False, registered_image_gate_relativeSE=0.1, prediction_sha256=hashlib.sha256(prediction.read_bytes()).hexdigest())
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
