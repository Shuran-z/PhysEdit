"""Registered conditional motion model and image objective."""
from pathlib import Path
import json, hashlib, itertools
import cv2, numpy as np
from scipy.spatial import ConvexHull
from scipy.optimize import minimize
from gravtrace.camera import Camera, quat_to_matrix

def photo(job):
    p = job['payload']
    known = job['known_image_geometry']
    initial = {i['name']: i for i in p['initial']}
    names = [s['name'] for s in p['specs'] if not s['fixed']]
    roles = ['t02v2_striker_eraser', 't02v2_gate_book']
    (W, H) = known['image_size']
    cam = Camera.from_dict(known['camera'], [W, H])
    C = np.asarray(known['camera']['matrix_world'])
    SS = 2
    (h, w) = (H * SS, W * SS)
    geometry = known['geometry']
    for row in geometry:
        row['vertices'] = np.asarray(row['vertices'])
        row['faces'] = np.asarray(row['faces'])
    masks = []
    for row in job['observed_masks']:
        masks.append([np.load(x['path'])['mask'].astype(np.float32) if x is not None else None for x in row])
    assert all((m is not None and m.sum() >= 8 for m in masks[0]))

    def render(rows, shift):
        zbuf = np.full((h, w), np.inf, np.float32)
        labels = np.full((h, w), -2, np.int8)
        for g in geometry:
            if g['name'] in names:
                st = rows[names.index(g['name'])]
                q = st[3:] / np.linalg.norm(st[3:])
                position = st[:3]
                rot = quat_to_matrix([*q[1:], q[0]])
            else:
                i = initial[g['name']]
                position = np.asarray(i['position'])
                rot = quat_to_matrix(i['quaternion_xyzw'])
            world = position + g['vertices'] @ rot.T
            uv = (cam.project(world) + shift) * SS
            z = -((world - C[:3, 3]) @ C[:3, :3])[:, 2]
            for face in g['faces']:
                points = uv[face]
                zz = z[face]
                if not np.isfinite(points).all() or np.min(zz) <= 1e-05:
                    continue
                lo = np.maximum(0, np.floor(points.min(0) - 1).astype(int))
                hi = np.minimum([w, h], np.ceil(points.max(0) + 1).astype(int))
                (x0, y0) = lo
                (x1, y1) = hi
                if x0 >= x1 or y0 >= y1:
                    continue
                (ax, ay) = points[0]
                (bx, by) = points[1]
                (cx, cy) = points[2]
                den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(den) < 1e-09:
                    continue
                (Y, X) = np.mgrid[y0:y1, x0:x1]
                X = X + 0.5
                Y = Y + 0.5
                a = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
                b = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
                cc = 1 - a - b
                inside = (a >= 0) & (b >= 0) & (cc >= 0)
                invz = a / zz[0] + b / zz[1] + cc / zz[2]
                depth = np.divide(1.0, invz, out=np.full_like(invz, np.inf), where=invz > 0)
                view = zbuf[y0:y1, x0:x1]
                closer = inside & (depth < view)
                view[closer] = depth[closer]
                labels[y0:y1, x0:x1][closer] = g['label']
        return [cv2.resize((labels == index).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA) for index in range(2)]

    def dice(a, b):
        den = float(np.sum(a * a) + np.sum(b * b))
        return 0.0 if den == 0 else 1.0 - 2.0 * float(np.sum(a * b)) / den
    condition = np.asarray([[*initial[name]['position'], initial[name]['quaternion_xyzw'][3], *initial[name]['quaternion_xyzw'][:3]] for name in names])
    align = Path(job['observation_output']) / 'condition_alignment.json'
    if align.exists():
        shift = np.asarray(json.load(open(align))['image_shift_px'])
    else:
        fit = minimize(lambda s: float(np.mean([dice(a, b) for (a, b) in zip(render(condition, s)[1:], masks[0][1:])])), [0.0, 0.0], method='Powell', bounds=[(-2, 2), (-2, 2)], options=dict(xtol=0.02, ftol=1e-06, maxiter=15))
        shift = fit.x
        align.write_text(json.dumps(dict(condition_frame_only=job['frames'][0], image_shift_px=shift.tolist(), objective=float(fit.fun), parameter_truth_input=False), indent=2))

    def cost(poses, early=False):
        poses = np.asarray(poses)
        assert poses.shape == (len(job['frames']), len(names), 7)
        loss = []
        for k in range(1, min(5, len(job['frames'])) if early else len(job['frames'])):
            pred = render(poses[k], shift)
            for (a, b) in zip(pred[1:], masks[k][1:]):
                if b is not None:
                    loss.append(dice(a, b))
        return float(np.mean(loss))
    return cost
