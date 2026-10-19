"""Development can-velocity refinement from existing single-view RGB and masks.

This module never calls SAM or gravity fitting. The stored gravity prediction
only initializes a separately reported trajectory-curvature nuisance. A fixed
3px outline consistency check prevents accepting optical-flow convergence when
it contradicts the frozen silhouette. Neither branch reads a velocity target.
Only explicitly declared cans with round, densely sampled outline geometry are
eligible. Thin books and nonconvex cups are outside this observation model.
Pixel consistency is not a certificate of velocity-vector identifiability.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull, QhullError

from gravtrace.fit import _Problem
from gravtrace.motion import ballistic, torque_free
from .motion_parameters import velocity_from_prediction
from .velocity_kinematics import sample_digest, fit_registered_velocity

OUTLINE_CHECK_PX = 3.0


def can_geometry_eligibility(sample, source_object):
    """Check source semantics and body geometry without IDs, errors or targets.

    These are model applicability checks, not evidence of an exact historical
    visual mesh. A cylinder proxy can pass; that limitation remains reported.
    """
    asset = str(source_object.get('asset_id', '')).lower()
    if asset != 'can' and not asset.startswith(('can_', 'beverage_can_')):
        return dict(eligible=False, reason='pixel_velocity_requires_declared_can_asset')
    points = np.asarray(sample.get('object', {}).get('corners'), float)
    if (points.ndim != 2 or points.shape[1] != 3 or len(points) < 24
            or not np.isfinite(points).all()):
        return dict(eligible=False, reason='pixel_velocity_requires_sampled_round_can_geometry')
    extent = np.ptp(points, axis=0)
    if (np.any(extent <= 0) or max(extent[:2]) / min(extent[:2]) > 1.05
            or extent[2] <= max(extent[:2])):
        return dict(eligible=False, reason='declared_can_geometry_is_not_round_and_upright')
    xy = points[:, :2] - (points[:, :2].min(0) + points[:, :2].max(0)) / 2
    radius = np.linalg.norm(xy, axis=1)
    rim = xy[radius >= .9 * radius.max()]
    angles = np.unique(np.round(np.arctan2(rim[:, 1], rim[:, 0]), 4))
    gaps = np.diff(np.r_[angles, angles[0] + 2 * np.pi]) if len(angles) else [np.inf]
    if len(angles) < 12 or max(gaps) > np.pi / 3:
        return dict(eligible=False, reason='declared_can_has_insufficient_round_outline_sampling')
    return dict(eligible=True, source_asset_id=asset, rim_angle_count=len(angles),
                exact_visual_surface_certified=False)

def _polygon_moments(uv):
    idx = cv2.convexHull(uv.astype(np.float32), returnPoints=False).ravel()
    poly = uv[idx]
    q = np.roll(poly, -1, axis=0)
    cross = poly[:, 0] * q[:, 1] - q[:, 0] * poly[:, 1]
    A = cross.sum() / 2
    centre = ((poly + q) * cross[:, None]).sum(0) / (6 * A)
    second = ((poly ** 2 + poly * q + q ** 2) * cross[:, None]).sum(0) / (12 * A)
    return np.r_[centre, np.sqrt(np.maximum(second - centre ** 2, 1e-08))]

class RegisteredVelocityPixels:
    """Read exact cached pixels/masks; target values are never part of a row."""

    def __init__(self, path, expected_sha256):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('pixel_registration_path_must_be_absolute')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('pixel_registration_sha_mismatch')
        rows = json.loads(raw)
        allowed = {'id', 'sample_sha256', 'cache_path', 'cache_sha256', 'frames'}
        if (not isinstance(rows, list) or any(set(row) != allowed for row in rows)
                or len({row['id'] for row in rows}) != len(rows)):
            raise ValueError('invalid_or_duplicate_pixel_registration')
        self.rows = {row['id']: row for row in rows}

    @staticmethod
    def _bytes(path, digest):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('registered_pixel_path_must_be_absolute')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('registered_pixel_file_drift')
        return path

    def load(self, sample, reference):
        row = self.rows.get(sample['id'])
        if row is None or row['sample_sha256'] != sample_digest(sample):
            raise ValueError('missing_or_drifted_registered_pixel_sample')
        if [r['frame'] for r in row['frames']] != reference['source_frame_indices']:
            raise ValueError('registered_pixel_frame_mismatch')
        images, masks = [], []
        cache_path = self._bytes(row['cache_path'], row['cache_sha256'])
        with np.load(cache_path, allow_pickle=False) as cache:
            for frame in row['frames']:
                if set(frame) != {'frame', 'bgr_sha256', 'mask_path', 'mask_file_sha256'}:
                    raise ValueError('invalid_registered_pixel_frame_fields')
                img = cache['rgb_' + str(frame['frame'])]
                if (img.ndim != 3 or img.shape[-1] != 3 or img.dtype != np.uint8
                        or hashlib.sha256(img.tobytes()).hexdigest() != frame['bgr_sha256']):
                    raise ValueError('registered_frame_pixel_drift')
                path = self._bytes(frame['mask_path'], frame['mask_file_sha256'])
                with np.load(path, allow_pickle=False) as archive:
                    mask = archive['mask']
                if (mask.shape != img.shape[:2] or not np.isfinite(mask).all()
                        or not np.isin(mask, [0, 1]).all() or not mask.any()):
                    raise ValueError('invalid_registered_frozen_mask')
                images.append(img.copy())
                masks.append(mask.astype(np.uint8))
        return images, masks


def _fields(sample, masks):
    result = []
    for mask in masks:
        mask = cv2.resize(mask, tuple(sample['image_size']), interpolation=cv2.INTER_NEAREST)
        outside = cv2.distanceTransform(1 - mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        inside = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        result.append((outside - inside).astype(float))
    return result


def _outline_check(sample, velocity, acceleration, fields):
    t = np.asarray(sample['boxes']['times'], float)
    problem = _Problem(sample, t, np.asarray(sample['boxes']['xyxy'], float))
    centres = ballistic(t, problem.x0, velocity, -acceleration, problem.g_dir, problem.drag)
    uv = problem.camera.project(problem.points(t, centres))
    if not np.isfinite(uv).all():
        return dict(status='invalid_projection', consistent=False)
    polygons = [contour(frame) for frame in uv]

    def residual(shift):
        return np.concatenate([bilinear(field, poly + shift)
                               for field, poly in zip(fields, polygons)])

    fit = least_squares(residual, [0., 0.], bounds=(-8, 8), loss='soft_l1',
                        f_scale=1., max_nfev=100)
    error = residual(fit.x).reshape(-1, 64)
    rms = float(np.sqrt(np.mean(error ** 2)))
    return dict(status='ok' if fit.success else 'optimizer_failure',
                consistent=bool(fit.success and np.isfinite(rms) and rms <= OUTLINE_CHECK_PX),
                rms_px=rms, limit_px=OUTLINE_CHECK_PX,
                per_frame_rms_px=np.sqrt(np.mean(error ** 2, axis=1)).tolist(),
                constant_translation_px=fit.x.tolist())


def fit_pixel_velocity(sample, saved_gravity, planes, pixels):
    """Explicit development entry; original planar predictions stay unchanged.

    Only source-declared cans enter the new pixel branch. Whole-window mask
    moments and RGB flow are accepted only if they also fit the untouched mask
    outline. If that check fails, fit the full outline instead. Failed branches
    remain in ``attempts``. No error target or case-specific algorithm choice is
    accepted, and no default generation/evaluation pipeline calls this entry.
    """
    if 'truth' in sample or 'v0' in sample.get('motion', {}):
        return dict(status='input_failure', reason='velocity_truth_in_estimator_input')
    try:
        plane = planes.validate(sample)
        if plane['status'] == 'registered':
            return dict(fit_registered_velocity(sample, saved_gravity, planes),
                        source_model_branch='registered_planar')
        if plane.get('reason') not in ('observed_source_motion_not_in_declared_plane',
                                      'missing_declared_motion_plane'):
            return dict(status='inapplicable', reason=plane.get('reason', 'unsupported_source_model'))
        if sample.get('scenario') != 'projectile' or saved_gravity.get('status') != 'ok':
            raise ValueError('requires_frozen_projectile_reference')
        reference = planes.validate_initial_reference(sample, saved_gravity)
        header = json.loads(Path(reference['source_header_path']).read_text())
        source_object = next(o for o in header['objects'] if o['name'] == reference['object_name'])
        applicability = can_geometry_eligibility(sample, source_object)
        if not applicability['eligible']:
            return dict(status='inapplicable', reason=applicability['reason'],
                        new_pixel_model_applicability=applicability,
                        original_velocity_result_preserved=True)
        if (len(sample['boxes']['frames']) < 3 or len(sample['boxes']['frames']) != saved_gravity['frames']
                or not .1 < float(saved_gravity['gravity']) < 80):
            raise ValueError('invalid_registered_velocity_window_or_initialization')
        geometry = np.asarray(sample.get('object', {}).get('corners'), float)
        if (sample.get('features') == 'centre' or geometry.ndim != 2
                or geometry.shape[1] != 3 or len(geometry) < 4
                or not np.isfinite(geometry).all()
                or np.linalg.matrix_rank(geometry - geometry.mean(axis=0)) < 3):
            return dict(status='inapplicable', reason='requires_nonflat_declared_rigid_outline_geometry')
        images, masks = pixels.load(sample, reference)
        # _Problem normalizes its gravity direction. Protect all caller-owned
        # arrays too, not just the JSON-list inputs used in the development data.
        working = copy.deepcopy(sample)
        fields = _fields(working, masks)
        flow = _masked_flow(working, saved_gravity, reference['source_frame_indices'], images, masks)
        attempts = [dict(branch='mask_moments_and_adjacent_rgb_flow', prediction=flow)]
        selected = flow
        branch = 'mask_moments_and_adjacent_rgb_flow'
        check = None
        if flow['status'] == 'ok':
            check = _outline_check(working, flow['velocity'], flow['acceleration'], fields)
            attempts[0]['outline_check'] = check
        if check is None or not check['consistent']:
            selected = _silhouette_fit(working, saved_gravity, fields)
            branch = 'full_frozen_mask_outline'
            attempts.append(dict(branch=branch, prediction=selected))
            if selected['status'] != 'ok':
                return dict(status='fit_failure', reason='no_consistent_pixel_velocity', attempts=attempts)
            check = _outline_check(working, selected['velocity'], selected['acceleration_nuisance'], fields)
            attempts[-1]['outline_check'] = check
        velocity = np.asarray(selected['velocity'], float)
        accel = float(selected.get('acceleration', selected.get('acceleration_nuisance', np.nan)))
        if (velocity.shape != (3,) or not np.isfinite(velocity).all() or not np.isfinite(accel)
                or not check['consistent']):
            return dict(status='fit_failure', reason='no_consistent_pixel_velocity', attempts=attempts)
        if np.linalg.norm(velocity) >= 8 - 1e-6 or not -80 + 1e-6 < accel < -.1 - 1e-6:
            return dict(status='at_bound', reason='pixel_velocity_search_limit', attempts=attempts)
        return dict(status='ok', method='single_view_registered_can_pixels_velocity_v4',
                    new_pixel_model_applicability=applicability,
                    source_model_branch=branch, velocity_vector_mps=velocity.tolist(),
                    speed_mps=float(np.linalg.norm(velocity)),
                    vertical_acceleration_nuisance_mps2=accel, outline_check=check,
                    reference='declared_initial_state',
                    observation_start_offset_s=float(sample['boxes']['times'][0]),
                    source_observation_gap_count=reference['source_frame_indices'][-1]
                    - reference['source_frame_indices'][0] + 1 - len(reference['source_frame_indices']),
                    frames=len(sample['boxes']['frames']), attempts=attempts,
                    frozen_gravity_result_changed=False, frozen_sam_changed=False,
                    new_sam_inference=False, high_precision_certified=False,
                    scientific_independence_certified=False)
    except (OSError, KeyError, IndexError, ValueError, TypeError, np.linalg.LinAlgError, cv2.error, QhullError) as error:
        return dict(status='input_failure', reason=str(error))

def contour(uv, n=64):
    ind = cv2.convexHull(uv.astype(np.float32), returnPoints=False).ravel()
    poly = uv[ind]
    delta = np.roll(poly, -1, axis=0) - poly
    length = np.linalg.norm(delta, axis=1)
    ends = np.r_[0, np.cumsum(length)]
    at = (np.arange(n) + 0.5) * ends[-1] / n
    j = np.searchsorted(ends, at, side='right') - 1
    return poly[j] + delta[j] * ((at - ends[j]) / np.maximum(length[j], 1e-12))[:, None]

def bilinear(field, uv):
    (h, w) = field.shape
    xy = np.clip(uv, [0, 0], [w - 1.001, h - 1.001])
    ix = np.floor(xy).astype(int)
    a = xy - ix
    (x, y) = ix.T
    (ax, ay) = a.T
    value = (field[y, x] * (1 - ax) + field[y, x + 1] * ax) * (1 - ay) + (field[y + 1, x] * (1 - ax) + field[y + 1, x + 1] * ax) * ay
    return value + np.linalg.norm(uv - xy, axis=1)

def _silhouette_fit(sample, saved_gravity, fields):
    s = sample
    t = np.asarray(s['boxes']['times'])
    b = np.asarray(s['boxes']['xyxy'])
    pr = _Problem(s, t, b)
    def residual(x):
        cc = ballistic(t, pr.x0, x[:3], -x[3], pr.g_dir, pr.drag)
        uv = pr.camera.project(pr.points(t, cc))
        if not np.isfinite(uv).all():
            return np.ones(len(fields) * 64) * 1000000.0
        return np.concatenate([bilinear(field, contour(poly) + x[4:6]) / 4 for (field, poly) in zip(fields, uv)])
    g = saved_gravity['gravity']
    seed = np.r_[velocity_from_prediction(saved_gravity, pr.g_dir), -g, 0.0, 0.0]
    starts = [seed, np.r_[0.0, 0.0, 0.0, -g, 0.0, 0.0]]
    fits = [least_squares(residual, x, bounds=([-8, -8, -8, -80, -8, -8], [8, 8, 8, -0.1, 8, 8]), loss='soft_l1', f_scale=0.25, max_nfev=500, x_scale='jac') for x in starts]
    fit = min(fits, key=lambda r: r.cost)
    return dict(status='ok' if fit.success else 'fit_failure', velocity=fit.x[:3].tolist(), acceleration_nuisance=float(fit.x[3]), constant_mask_translation_px=fit.x[4:6].tolist(), pixel_cost=float(fit.cost), full_outline_rms_px=float(np.sqrt(np.mean(residual(fit.x) ** 2)) * 4), evaluations=int(fit.nfev), optimizer_success=bool(fit.success), frozen_gravity_changed=False, frozen_sam_changed=False, new_sam=False, source_future_pose_used=False)

def _masked_flow(sample, saved_gravity, frames, images, masks):
    s = sample
    t = np.asarray(s['boxes']['times'])
    b = np.asarray(s['boxes']['xyxy'])
    pr = _Problem(s, t, b)
    cam = pr.camera
    frames = list(frames)
    imgs = [cv2.resize(img, tuple(s['image_size'])) for img in images]
    grey = [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in imgs]
    moment_obs=[]
    for mask in masks:
        mask=cv2.resize(mask,tuple(s['image_size']),interpolation=cv2.INTER_NEAREST)
        mm=cv2.moments(mask)
        moment_obs.append([mm['m10']/mm['m00'],mm['m01']/mm['m00'],np.sqrt(mm['mu20']/mm['m00']),np.sqrt(mm['mu02']/mm['m00'])])
    moment_obs=np.asarray(moment_obs)
    pairs = []
    for k in range(len(frames) - 1):
        mask0 = masks[k].astype(np.uint8)
        nextmask = masks[k+1].astype(np.uint8)
        mask0 = cv2.resize(mask0, grey[k].shape[::-1], interpolation=cv2.INTER_NEAREST)
        nextmask = cv2.resize(nextmask, grey[k].shape[::-1], interpolation=cv2.INTER_NEAREST)
        mask = np.zeros(grey[k].shape, np.uint8)
        lo = np.maximum(np.ceil(b[k, :2] + 2).astype(int), 0)
        hi = np.minimum(np.floor(b[k, 2:] - 2).astype(int), grey[k].shape[::-1])
        mask[lo[1]:hi[1], lo[0]:hi[0]] = 255
        mask &= cv2.erode(mask0, np.ones((3, 3), np.uint8)) * 255
        pts = cv2.goodFeaturesToTrack(grey[k], maxCorners=60, qualityLevel=0.003, minDistance=2, mask=mask, blockSize=3)
        if pts is None:
            continue
        (q, ok, _) = cv2.calcOpticalFlowPyrLK(grey[k], grey[k + 1], pts, None, winSize=(9, 9), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 0.001))
        (back, ok2, _) = cv2.calcOpticalFlowPyrLK(grey[k + 1], grey[k], q, None, winSize=(9, 9), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 0.001))
        keep = ok[:, 0].astype(bool) & ok2[:, 0].astype(bool) & (np.linalg.norm(back[:, 0] - pts[:, 0], axis=1) < 0.5) & np.all((q[:, 0] > b[k + 1, :2] - 1) & (q[:, 0] < b[k + 1, 2:] + 1), axis=1)
        qxy = np.rint(q[:, 0]).astype(int)
        inside = (qxy[:, 0] >= 0) & (qxy[:, 0] < nextmask.shape[1]) & (qxy[:, 1] >= 0) & (qxy[:, 1] < nextmask.shape[0])
        nmask = np.zeros(len(qxy), bool)
        nmask[inside] = nextmask[qxy[inside, 1], qxy[inside, 0]] > 0
        keep &= nmask
        if keep.sum() >= 3:
            pairs.append((k, pts[keep, 0].astype(float), q[keep, 0].astype(float)))
    if len(pairs) < 3:
        return dict(status='inapplicable', reason='too_few_adjacent_RGB_flow_pairs', pair_count=len(pairs))
    W = np.linalg.inv(cam.world_to_cam)
    C = W[:3, 3]
    Rc = W[:3, :3]
    rot = (torque_free(t, pr.rotation0, pr.omega, pr.inertia, damping=pr.spin_damping) if pr.omega is not None else np.repeat(pr.rotation0[None], len(t), axis=0))
    g = saved_gravity['gravity']
    x = np.r_[velocity_from_prediction(saved_gravity, pr.g_dir), -g]
    history = []
    for it in range(3):
        centres = ballistic(t, pr.x0, x[:3], -x[3], pr.g_dir, pr.drag)
        geom = np.einsum('kij,cj->kci', rot, pr.body_corners) + centres[:, None]
        pb = cam.project_box(geom)
        xyz = []
        records = []
        for (k, uv, uvnext) in pairs:
            hull = ConvexHull(geom[k])
            A = hull.equations[:, :3]
            bb = hull.equations[:, 3]
            bias = (b[k, :2] + b[k, 2:] - (pb[k, :2] + pb[k, 2:])) / 2
            for (point, nextpoint) in zip(uv, uvnext):
                (u, v) = point - bias
                ray = np.einsum('ij,j->i', Rc, np.array([(u / cam.width - cam.cx) / cam.fx, -(v / cam.height - cam.cy) / cam.fy, -1.0], float))
                ad = np.einsum('ij,j->i', A, ray)
                rhs = -(np.einsum('ij,j->i', A, C) + bb)
                lo = np.max(rhs[ad < -1e-09] / ad[ad < -1e-09], initial=0)
                hi = np.min(rhs[ad > 1e-09] / ad[ad > 1e-09], initial=np.inf)
                if 0 < lo <= hi:
                    body = rot[k].T @ (C + lo * ray - centres[k])
                    records.append((k, point, nextpoint))
                    xyz.append(body)
        if len(xyz) < 12:
            return dict(status='inapplicable', reason='insufficient_on_geometry_flow_features', count=len(xyz))
        indices = np.array([r[0] for r in records])
        xyz = np.array(xyz)
        flows = np.array([r[2] - r[1] for r in records])
        cnt = np.bincount(indices, minlength=len(t))
        weight = 1 / np.sqrt(cnt[indices])
        local0 = np.einsum('kij,kj->ki', rot[indices], xyz)
        local1 = np.einsum('kij,kj->ki', rot[indices + 1], xyz)

        def residual(xx):
            cc = ballistic(t, pr.x0, xx[:3], -xx[3], pr.g_dir, pr.drag)
            a = cam.project(cc[indices] + local0)
            b = cam.project(cc[indices + 1] + local1)
            diff = b - a - flows
            uv=cam.project(np.einsum('kij,cj->kci',rot,pr.body_corners)+cc[:,None])
            if not np.isfinite(uv).all():return np.ones(diff.size+moment_obs.size)*1e6
            projected_moments=np.asarray([_polygon_moments(poly) for poly in uv]);md=projected_moments-moment_obs;md-=md.mean(0)
            res=np.r_[md.ravel(),(diff*weight[:,None]).ravel()]
            return res if np.isfinite(res).all() else np.ones(res.size)*1e6
        fit = least_squares(residual, x, bounds=([-8, -8, -8, -80], [8, 8, 8, -0.1]), loss='soft_l1', f_scale=0.5, max_nfev=500, x_scale='jac')
        x = fit.x
        history.append(dict(iteration=it, x=x.tolist(), cost=float(fit.cost), feature_count=len(xyz), counts=cnt.tolist()))
    return dict(status='ok' if fit.success else 'fit_failure', velocity=x[:3].tolist(), acceleration=float(x[3]), history=history, source_future_pose_used=False, new_sam=False)
