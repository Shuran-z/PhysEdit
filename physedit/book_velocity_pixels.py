"""Development single-view book velocity with visibility-aware observations.

Original cached RGB, masks, frame times and edge visibility are mandatory.
Projected shapes are clipped to the viewport and registered occlusion bounds;
no missing pixels or future source trajectories are used as observations.
Gravity initializes a separately reported curvature nuisance. The original
can/planar estimators and the default generation/evaluation pipeline are intact.
"""
from __future__ import annotations
import copy,json
from pathlib import Path
import cv2,numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull,QhullError
from gravtrace.fit import _Problem
from gravtrace.motion import ballistic,torque_free
from .motion_parameters import velocity_from_prediction
from .velocity_kinematics import fit_registered_velocity
from .velocity_pixels import RegisteredVelocityPixels,_fields,_polygon_moments,bilinear,contour,OUTLINE_CHECK_PX
from .book_visibility import clip_polygon,clip_observed_polygon,visibility

MIN_BOOK_FRAMES=8


def observed_convex_moments(mask):
    """Shape descriptor of observed pixel-cell supports, not a rewritten mask.

    The declared model is convex. Using uniform segmentation mass would treat
    holes in a dark cover as missing physical material and bias its centroid.
    RGB matching and consistency checks still use the untouched original mask.
    """
    yy,xx=np.nonzero(mask)
    if not len(xx):raise ValueError('empty_book_mask')
    centres=np.c_[xx,yy].astype(float)
    hull=centres[cv2.convexHull(centres.astype(np.float32),returnPoints=False).ravel()]
    cells=np.concatenate([hull+offset for offset in [(-.5,-.5),(-.5,.5),(.5,-.5),(.5,.5)]])
    return _polygon_moments(cells)


def book_geometry_eligibility(sample, source_object):
    asset=source_object.get('asset_id')
    points=np.asarray(sample.get('object',{}).get('corners'),float)
    size=np.asarray(source_object.get('size'),float)
    if asset not in ('book_thick_01_v2','book_textbook_01_v2'):
        return dict(eligible=False,reason='requires_registered_visual_book_asset')
    if (points.ndim!=2 or points.shape[1]!=3 or len(points)<24
            or not np.isfinite(points).all() or size.shape!=(3,)
            or not np.isfinite(size).all() or np.any(size<=0)):
        return dict(eligible=False,reason='requires_sampled_declared_visual_book_geometry')
    if not np.allclose(np.ptp(points,axis=0),size,rtol=.03,atol=.002):
        return dict(eligible=False,reason='book_geometry_does_not_match_source_size')
    return dict(eligible=True,source_asset_id=asset,
                exact_visual_surface_certified=False)
def _prepared_view_residual(sample, fields):
    t=np.asarray(sample['boxes']['times'],float);seen,shape,viewport=visibility(sample)
    problem=_Problem(sample,t,np.asarray(sample['boxes']['xyxy'],float),seen)
    offsets=problem.points(t,np.zeros((len(t),3)))
    def evaluate(velocity, acceleration, shift):
        cc=ballistic(t,problem.x0,velocity,-acceleration,problem.g_dir,problem.drag)
        uv=problem.camera.project(cc[:,None]+offsets)
        if not np.isfinite(uv).all():return np.full(len(t)*64,1e6)
        rows=[]
        for k,points in enumerate(uv):
            poly=clip_observed_polygon(points+shift,sample['image_size'],problem.obs[k],seen[k])
            if len(poly)<3:rows.append(np.full(64,1000.));continue
            rows.append(bilinear(fields[k],contour(poly)))
        return np.concatenate(rows)
    return evaluate

def _outline_check(sample, velocity, acceleration, fields):
    evaluate=_prepared_view_residual(sample,fields)
    def residual(shift):return evaluate(velocity,acceleration,shift)
    f=least_squares(residual,[0.,0.],bounds=(-8,8),loss='soft_l1',f_scale=1,max_nfev=100)
    error=residual(f.x).reshape(-1,64);rms=float(np.sqrt(np.mean(error**2)))
    seen,shape,viewport=visibility(sample)
    return dict(status='ok' if f.success else 'optimizer_failure',consistent=bool(f.success and np.isfinite(rms) and rms<=OUTLINE_CHECK_PX),rms_px=rms,limit_px=OUTLINE_CHECK_PX,per_frame_rms_px=np.sqrt(np.mean(error**2,axis=1)).tolist(),constant_translation_px=f.x.tolist(),observation_model='visible_shape_clipped_at_viewport_and_observed_occlusion_bounds',original_frames_retained=len(shape),occlusion_censored_frames=int((~shape).sum()),viewport_clipped_frames=int(viewport.any(1).sum()))


def fit_book_pixel_velocity(sample, saved_gravity, planes, pixels):
    """Explicit development entry; original planar predictions stay unchanged.

    Only registered visual books enter the new branch. Match each frame's
    visible shape, with viewport/occlusion censoring from its original metadata.
    If joint shape/flow is inconsistent, fit the visible outline. Failed branches
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
        applicability = book_geometry_eligibility(sample,source_object)
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
        if len(sample['boxes']['frames']) < MIN_BOOK_FRAMES:
            return dict(status='inapplicable', reason='book_shape_flow_requires_eight_original_frames', original_velocity_result_preserved=True)
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
        return dict(status='ok', method='single_view_book_visible_shape_flow_v6',
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

def _silhouette_fit(sample, saved_gravity, fields):
    t=np.asarray(sample['boxes']['times']);problem=_Problem(sample,t,np.asarray(sample['boxes']['xyxy']))
    g=saved_gravity['gravity'];seed=np.r_[velocity_from_prediction(saved_gravity,problem.g_dir),-g,0.,0.]
    evaluate=_prepared_view_residual(sample,fields)
    def residual(x):return evaluate(x[:3],x[3],x[4:6])/4
    fits=[least_squares(residual,x,bounds=([-8,-8,-8,-80,-8,-8],[8,8,8,-.1,8,8]),loss='soft_l1',f_scale=.25,max_nfev=500,x_scale='jac') for x in (seed,np.r_[0,0,0,-g,0.,0.])]
    f=min(fits,key=lambda r:r.cost)
    return dict(status='ok' if f.success else 'fit_failure',velocity=f.x[:3].tolist(),acceleration_nuisance=float(f.x[3]),constant_mask_translation_px=f.x[4:6].tolist(),pixel_cost=float(f.cost),evaluations=int(f.nfev),optimizer_success=bool(f.success))

def _masked_flow(sample, saved_gravity, frames, images, masks):
    s = sample
    t = np.asarray(s['boxes']['times'])
    b = np.asarray(s['boxes']['xyxy'])
    seen,original_shape_valid,viewport=visibility(s)
    shape_valid=np.ones(len(t),bool)
    pr = _Problem(s, t, b, seen)
    cam = pr.camera
    frames = list(frames)
    imgs = [cv2.resize(img, tuple(s['image_size'])) for img in images]
    grey = [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in imgs]
    moment_obs=[]
    for mask in masks:
        mask=cv2.resize(mask,tuple(s['image_size']),interpolation=cv2.INTER_NEAREST)
        moment_obs.append(observed_convex_moments(mask))
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
        projected=cam.project(geom)
        pb=np.empty_like(b,dtype=float)
        for kk,poly in enumerate(projected):
            visible_poly=clip_observed_polygon(poly,s['image_size'],b[kk],seen[kk])
            if len(visible_poly)<3:
                return dict(status='inapplicable',reason='insufficient_predicted_visible_geometry_for_flow',history=history)
            pb[kk]=np.r_[visible_poly.min(0),visible_poly.max(0)]
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
                    world = C + lo * ray
                    body = rot[k].T @ (world - centres[k])
                    face = int(np.argmin(abs(A @ world + bb)))
                    body_normal = rot[k].T @ A[face]
                    next_world = centres[k+1] + rot[k+1] @ body
                    next_normal = rot[k+1] @ body_normal
                    # A material point cannot remain visible after its face
                    # rotates away; image-mask membership alone is insufficient.
                    if next_normal @ (C - next_world) <= 0:
                        continue
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
            if not np.isfinite(uv).all():return np.ones(diff.size+moment_obs.size+pr.obs.size)*1e6
            projected_moments=moment_obs.copy()
            for kk in np.flatnonzero(shape_valid):
                poly=clip_observed_polygon(uv[kk],s['image_size'],pr.obs[kk],seen[kk])
                if len(poly)<3:return np.ones(diff.size+moment_obs.size+pr.obs.size)*1e6
                projected_moments[kk]=_polygon_moments(poly)
            md=projected_moments-moment_obs
            if shape_valid.any():md[shape_valid]-=md[shape_valid].mean(0)
            bbox=np.c_[uv.min(1),uv.max(1)]-pr.obs;ww=pr.weight**2
            bbox-=(bbox*ww).sum(0)/np.maximum(ww.sum(0),1e-12)
            bbox*=pr.weight*(~shape_valid)[:,None]
            res=np.r_[md.ravel(),bbox.ravel(),(diff*weight[:,None]).ravel()]
            return res if np.isfinite(res).all() else np.ones(res.size)*1e6
        fit = least_squares(residual, x, bounds=([-8, -8, -8, -80], [8, 8, 8, -0.1]), loss='soft_l1', f_scale=0.5, max_nfev=500, x_scale='jac')
        x = fit.x
        history.append(dict(iteration=it, x=x.tolist(), cost=float(fit.cost), feature_count=len(xyz), counts=cnt.tolist()))
    return dict(status='ok' if fit.success else 'fit_failure', velocity=x[:3].tolist(), acceleration=float(x[3]), history=history, source_future_pose_used=False, new_sam=False)
