"""Registered conditional motion model and image objective."""
from pathlib import Path
import numpy as np, cv2
from scipy.ndimage import spline_filter, map_coordinates
from scipy.optimize import least_squares
from gravtrace.camera import Camera

def read_obj(path):
    vertices = []
    triangles = []
    for l in Path(path).read_text().splitlines():
        if l.startswith('v '):
            vertices.append([float(x) for x in l.split()[1:4]])
        elif l.startswith('f '):
            f = [int(x.split('/')[0]) for x in l.split()[1:]]
            f = [x - 1 if x > 0 else len(vertices) + x for x in f]
            triangles.extend([[f[0], f[i], f[i + 1]] for i in range(1, len(f) - 1)])
    return (np.asarray(vertices, float), np.asarray(triangles, int))

def raycast(origin, rays, triangles):
    a = triangles[:, 0]
    e1 = triangles[:, 1] - a
    e2 = triangles[:, 2] - a
    out = []
    valid = []
    for ray in rays:
        h = np.cross(ray, e2)
        det = np.sum(e1 * h, axis=1)
        ok = abs(det) > 1e-12
        inv = np.zeros(len(det))
        inv[ok] = 1 / det[ok]
        s = origin - a
        u = np.sum(s * h, axis=1) * inv
        q = np.cross(s, e1)
        v = q @ ray * inv
        t = np.sum(e2 * q, axis=1) * inv
        ok &= (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        distance = np.min(t[ok]) if ok.any() else np.nan
        out.append(origin + distance * ray)
        valid.append(bool(ok.any()))
    return (np.asarray(out), np.asarray(valid))

def observe(camera_dict, image_size, initial_position, world_vertices, faces, axis, images, secondary_axis=None, visibility_masks=None):
    camera = Camera.from_dict(camera_dict, image_size)
    C = np.asarray(camera_dict['matrix_world'])
    origin = np.asarray(initial_position, float)
    vertices = origin + np.asarray(world_vertices)
    uv = camera.project(vertices)
    mask = np.zeros(images[0].shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(uv.astype(np.float32)).astype(np.int32), 1)
    gray = cv2.cvtColor(images[0], cv2.COLOR_BGR2GRAY)
    mag = np.hypot(cv2.Sobel(gray, cv2.CV_64F, 1, 0), cv2.Sobel(gray, cv2.CV_64F, 0, 1))
    margin = min(3, max(1, int(cv2.distanceTransform(mask, cv2.DIST_L2, 5).max() / 3)))
    region = cv2.erode(mask, np.ones((2 * margin + 1, 2 * margin + 1), np.uint8)).astype(bool)
    region = region if visibility_masks is None else region & visibility_masks[0]
    (ys, xs) = np.where(region & (mag > 8))
    order = np.argsort(-mag[ys, xs], kind='stable')
    chosen = []
    used = set()
    for i in order:
        cell = (int(xs[i]) // 2, int(ys[i]) // 2)
        if cell not in used:
            chosen.append([xs[i], ys[i]])
            used.add(cell)
        if len(chosen) >= 350:
            break
    pixels = np.asarray(chosen, float)
    if len(pixels) < 24:
        raise ValueError('condition_texture_insufficient')
    rays = np.column_stack([(pixels[:, 0] / camera.width - camera.cx) / camera.fx, (camera.cy - pixels[:, 1] / camera.height) / camera.fy, -np.ones(len(pixels))]) @ C[:3, :3].T
    (world, valid) = raycast(C[:3, 3], rays, vertices[faces])
    pixels = pixels[valid]
    world = world[valid]
    rel = world - origin
    if len(world) < 24:
        raise ValueError('condition_surface_insufficient')
    frames = [np.stack([spline_filter(cv2.GaussianBlur(im.astype(float) / 255, (0, 0), 1.0)[:, :, ch], order=3) for ch in range(3)], axis=2) for im in images]
    sample = lambda im, points: np.stack([map_coordinates(im[:, :, ch], [points[:, 1], points[:, 0]], order=3, mode='nearest', prefilter=False) for ch in range(3)], axis=1)
    reference = sample(frames[0], pixels)
    axis = np.asarray(axis)
    perp = np.cross([0, 0, 1], axis) if secondary_axis is None else np.asarray(secondary_axis, float)
    params = [[0.0, 0.0, 0.0]]
    rmse = [0.0]
    condition_box = np.r_[uv.min(0), uv.max(0)]
    (x, y, u, v) = np.rint(condition_box).astype(int)
    (w, h) = image_size
    x = max(0, x)
    y = max(0, y)
    u = min(w, u)
    v = min(h, v)
    template = images[0][y:v, x:u]
    coarse_boxes = []
    scores = []
    direction = camera.project(origin + axis * 0.1) - camera.project(origin)
    direction /= np.linalg.norm(direction)
    last_progress = 0.0
    last_pose = np.zeros(3)
    statuses = []
    visible_counts = []
    for (k, image) in enumerate(images):
        corr = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        (rows, columns) = np.indices(corr.shape)
        dx = columns - x
        dy = rows - y
        deviation = abs(dx * direction[1] - dy * direction[0])
        progress = dx * direction[0] + dy * direction[1]
        corr[(deviation > max(4.0, 0.15 * template.shape[0])) | (progress < last_progress - 2.5)] = -2.0
        (_, score, _, (xx, yy)) = cv2.minMaxLoc(corr)
        coarse_boxes.append([int(z) for z in [xx, yy, xx + u - x, yy + v - y]])
        scores.append(float(score))
        if k == 0:
            statuses.append('condition')
            visible_counts.append(len(world))
            continue
        if score < 0.3 and (visibility_masks is None or visibility_masks[k] is None):
            params.append([None, None, None])
            rmse.append(None)
            statuses.append('condition_identity_not_observed')
            visible_counts.append(0)
            continue
        if visibility_masks is not None and visibility_masks[k] is not None and visibility_masks[k].any():
            (y0m, x0m) = np.where(visibility_masks[0])
            (ym, xm) = np.where(visibility_masks[k])
            xx = x + float(xm.mean() - x0m.mean())
            yy = y + float(ym.mean() - y0m.mean())
            coarse_boxes[-1] = [int(v) for v in [xx, yy, xx + u - x, yy + v - y]]
        mask_distance = None
        if visibility_masks is not None and visibility_masks[k] is not None:
            mask_distance = cv2.distanceTransform((~visibility_masks[k]).astype(np.uint8), cv2.DIST_L2, 5)
        proposed_progress = (xx - x) * direction[0] + (yy - y) * direction[1]
        pixel_shift = np.array([xx - x, yy - y])
        eps = 0.001
        J = np.column_stack([(camera.project(origin + axis * eps) - camera.project(origin)) / eps, (camera.project(origin + perp * eps) - camera.project(origin)) / eps])
        seed = np.r_[np.linalg.lstsq(J, pixel_shift, rcond=None)[0], last_pose[2]]

        def residual(z):
            (c, s) = (np.cos(z[2]), np.sin(z[2]))
            R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            projected = camera.project(origin + axis * z[0] + perp * z[1] + rel @ R.T)
            finite = np.isfinite(projected).all(1)
            safe = np.where(finite[:, None], projected, [-1.0, -1.0])
            diff = sample(frames[k], safe) - reference
            inside = finite & (projected[:, 0] >= 0) & (projected[:, 0] < image_size[0]) & (projected[:, 1] >= 0) & (projected[:, 1] < image_size[1])
            diff -= np.median(diff[inside]) if inside.any() else 0.0
            diff[~inside] = 1.0
            penalty = np.zeros(len(projected)) if mask_distance is None else 0.02 * np.minimum(10.0, map_coordinates(mask_distance, [safe[:, 1], safe[:, 0]], order=1, mode='constant', cval=50.0) / 5.0)
            return np.r_[diff.ravel(), penalty]
        lower = np.r_[last_pose[:2] - 0.3, -0.35]
        upper = np.r_[last_pose[:2] + 0.3, 0.35]
        seed = np.clip(seed, lower + 1e-08, upper - 1e-08)
        starts = [seed, np.r_[seed[:2], 0.0], np.clip(last_pose, lower + 1e-08, upper - 1e-08)]
        fits = [least_squares(residual, z, bounds=(lower, upper), loss='soft_l1', f_scale=0.04, max_nfev=120, ftol=1e-09, xtol=1e-09, gtol=1e-09) for z in starts]
        best = min(fits, key=lambda r: r.cost)
        (c, s) = (np.cos(best.x[2]), np.sin(best.x[2]))
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        projected = camera.project(origin + axis * best.x[0] + perp * best.x[1] + rel @ R.T)
        inside = np.isfinite(projected).all(1) & (projected[:, 0] >= 0) & (projected[:, 0] < image_size[0]) & (projected[:, 1] >= 0) & (projected[:, 1] < image_size[1])
        visible_counts.append(int(inside.sum()))
        if inside.sum() < 24:
            params.append([None, None, None])
            rmse.append(None)
            statuses.append('insufficient_actual_viewport_support')
            continue
        params.append(best.x.tolist())
        rmse.append(float(np.sqrt(np.mean(best.fun[:3 * len(projected)] ** 2))))
        statuses.append('observed')
        last_pose = best.x
        last_progress = proposed_progress
    return dict(distance_m=np.asarray(params, dtype=object)[:, 0].tolist(), lateral_m=np.asarray(params, dtype=object)[:, 1].tolist(), secondary_translation_m=np.asarray(params, dtype=object)[:, 1].tolist(), secondary_axis=perp.tolist(), yaw_rad=np.asarray(params, dtype=object)[:, 2].tolist(), photo_rmse=rmse, photo_rmse_excludes_mask_penalty=True, condition_surface_world=world.tolist(), condition_pixels=pixels.tolist(), template_boxes=coarse_boxes, template_scores=scores, observation_status=statuses, visible_surface_points=visible_counts, condition_only_surface=True, future_source_poses_used=False)
