"""Independent motion-parameter measurements; never refit the frozen gravity method.

Velocity is referenced to the declared fit-window initial state, not to an
unrelated actuator or event start. Sliding friction requires an independently
known gravity, calibrated geometry/clock and an identified contact coefficient.
Recorded trajectories are scoring targets, never pixel observations.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
from scipy.optimize import least_squares

from gravtrace.camera import Camera


def velocity_from_prediction(prediction, gravity_direction=(0., 0., -1.)):
    """Decode the existing projectile nuisance parameters, in world m/s."""
    if prediction.get('status') != 'ok':
        raise ValueError('unusable_frozen_prediction')
    p = prediction['params']
    speed, angle, azimuth = (float(p[k]) for k in ('speed', 'angle', 'azimuth'))
    direction = np.asarray(gravity_direction, dtype=float)
    if direction.shape != (3,) or not np.isfinite(direction).all() or np.linalg.norm(direction) == 0:
        raise ValueError('invalid_gravity_direction')
    if speed < 0 or not np.isfinite([speed, angle, azimuth]).all():
        raise ValueError('invalid_velocity_parameters')
    up = -direction / np.linalg.norm(direction)
    e1 = np.eye(3)[0 if abs(up[0]) < .9 else 1].copy()
    e1 -= np.dot(e1, up) * up
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    return speed * (np.cos(angle) * (np.cos(azimuth) * e1 + np.sin(azimuth) * e2)
                    + np.sin(angle) * up)


def scalar_error(estimate, target):
    estimate, target = float(estimate), float(target)
    if not np.isfinite([estimate, target]).all() or target < 0:
        raise ValueError('invalid_scalar_estimate_or_target')
    absolute = abs(estimate - target)
    return {'absolute_error': absolute,
            'relative_error_pct': 100 * absolute / target if target > 0 else None,
            'zero_target': target == 0}


def velocity_error(prediction, truth, gravity_direction=(0., 0., -1.)):
    estimate = velocity_from_prediction(prediction, gravity_direction)
    truth = np.asarray(truth, dtype=float)
    if truth.shape != (3,) or not np.isfinite(truth).all():
        raise ValueError('invalid_velocity_target')
    speed = float(np.linalg.norm(truth))
    out = scalar_error(np.linalg.norm(estimate), speed)
    vector_error = float(np.linalg.norm(estimate - truth))
    out.update(estimate_vector_mps=estimate.tolist(), target_vector_mps=truth.tolist(),
               estimate_speed_mps=float(np.linalg.norm(estimate)), target_speed_mps=speed,
               vector_absolute_error_mps=vector_error,
               vector_relative_error_pct=100 * vector_error / speed if speed > 0 else None,
               reference='declared_fit_window_initial_state')
    return out


def fit_velocity_with_frozen_gravity(sample, gravity_prediction):
    """Independent Cartesian velocity fit using the saved g and same pixel window.

    The frozen result supplies g and its registered time offset. Geometry,
    visibility and spin are read exactly as by the existing projection model.
    This estimates only v0; it never solves for g or receives a velocity target.
    Selection between two initializations uses pixel loss, never target error.
    """
    from gravtrace.fit import _Problem
    from gravtrace.motion import ballistic

    if 'truth' in sample or 'v0' in sample.get('motion', {}):
        return dict(status='input_failure', reason='velocity_truth_in_estimator_input')
    if sample.get('scenario') != 'projectile' or gravity_prediction.get('status') != 'ok':
        return dict(status='inapplicable', reason='requires_valid_frozen_projectile_gravity')
    try:
        frames = np.asarray(sample['boxes']['frames'], dtype=int)
        boxes = np.asarray(sample['boxes']['xyxy'], dtype=float)
        if len(frames) < 3 or boxes.shape != (len(frames), 4) or not np.isfinite(boxes).all():
            raise ValueError('missing_fixed_window_observations')
        if len(frames) != gravity_prediction['frames'] or np.any(np.diff(frames) <= 0):
            raise ValueError('fixed_window_or_frame_count_mismatch')
        raw_t = sample['boxes'].get('times')
        t = np.asarray(raw_t, dtype=float) if raw_t is not None else frames/float(sample['fps'])
        if not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
            raise ValueError('invalid_observation_clock')
        t = t-t[0]
        seen_map = sample.get('window', {}).get('edges_visible', {})
        seen = np.asarray([seen_map.get(str(f), [True]*4) for f in frames], bool)
        problem = _Problem(sample, t, boxes, seen)
        if problem.anchor is None:
            return dict(status='inapplicable', reason='insufficient_visible_supports')
        g = float(gravity_prediction['gravity'])
        offset = float(gravity_prediction['params']['t0'])
        if not np.isfinite([g, offset]).all() or g <= 0:
            raise ValueError('invalid_frozen_gravity_or_time')
        tau = np.maximum(t+offset, 0.)
        gdir = problem.g_dir

        def residual(v):
            centres = ballistic(tau, problem.x0, v, g, gdir, problem.drag)
            projected = problem.camera.project_box(problem.points(tau, centres))
            if not np.isfinite(projected).all():
                return np.full(boxes.size, 1e6)
            if problem.offset_mode == 'centred':
                diff = projected-problem.obs
                weights = problem.weight**2
                diff -= (diff*weights).sum(axis=0)/np.maximum(weights.sum(axis=0), 1e-12)
            else:
                diff = (projected-projected[problem.anchor])-(problem.obs-problem.obs[problem.anchor])
            return (diff*problem.weight).ravel()

        initial = velocity_from_prediction(gravity_prediction, gdir)
        fits = [least_squares(residual, start, bounds=(-8., 8.), max_nfev=150,
                              ftol=1e-9, xtol=1e-9, gtol=1e-9)
                for start in (initial, np.zeros(3))]
        best = min(fits, key=lambda f: float(np.sum(f.fun**2)))
        speed = float(np.linalg.norm(best.x))
        if not best.success or not np.isfinite(best.x).all():
            return dict(status='fit_failure', reason='velocity_optimizer_failed')
        if speed >= 8.-1e-6:
            return dict(status='at_bound', reason='velocity_exceeds_registered_speed_range')
        return dict(status='ok', velocity_vector_mps=best.x.tolist(), speed_mps=speed,
                    gravity_mps2=g, gravity_optimized=False, time_offset_optimized=False,
                    fixed_time_offset_s=offset, frames=len(frames), pixel_cost=float(best.cost),
                    initial_velocity_source='saved_frozen_nuisance_and_zero',
                    method='independent_cartesian_velocity_fixed_saved_gravity_v1')
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError) as error:
        return dict(status='input_failure', reason=str(error))


def summarize_errors(records, key='relative_error_pct', mean_limit=2.700312065214676,
                     max_limit=15.14809629360071):
    """Keep failures and zero targets in coverage; do not silently average zeros."""
    good = [r for r in records if r.get('status') == 'ok']
    errors = [r[key] for r in good if r.get(key) is not None and math.isfinite(r[key])]
    absolute_key = 'vector_absolute_error_mps' if key == 'vector_relative_error_pct' else 'absolute_error'
    zero_absolute = [r[absolute_key] for r in good if r.get('zero_target')
                     and r.get(absolute_key) is not None and math.isfinite(r[absolute_key])]
    n = len(records)
    return dict(registered=n, scored=len(good), relative_error_count=len(errors),
                zero_target_count=sum(bool(r.get('zero_target')) for r in good),
                zero_target_mean_absolute_error=float(np.mean(zero_absolute)) if zero_absolute else None,
                zero_target_max_absolute_error=max(zero_absolute) if zero_absolute else None,
                failed_or_inapplicable=n-len(good),
                coverage_rate=len(good)/n if n else None,
                failure_or_inapplicable_rate=1-len(good)/n if n else None,
                mean_pct=float(np.mean(errors)) if errors else None,
                max_pct=max(errors) if errors else None,
                p95_pct=float(np.percentile(errors, 95)) if errors else None,
                tolerance_failure_rate_all=sum(e > max_limit for e in errors)/n if n and errors else None,
                mean_within_gravity_reference=bool(errors and np.mean(errors) <= mean_limit),
                max_within_gravity_reference=bool(errors and max(errors) <= max_limit),
                reasons=dict(Counter(r.get('reason', r.get('status', 'missing'))
                                     for r in records if r.get('status') != 'ok')))


def sliding_displacement(times, speed, acceleration, drag=0.):
    """A monotonic kinetic-sliding segment: dv/dt = acceleration - drag*v.

    Stopping, direction reversal and contact changes end applicability of this
    model; they must not be hidden by trimming an already registered window.
    """
    times = np.asarray(times, dtype=float)
    if drag < 0 or not np.isfinite(drag):
        raise ValueError('invalid_declared_drag')
    if drag * np.max(times, initial=0.) < 1e-6:
        return speed*times + .5*acceleration*times**2
    k = -np.expm1(-drag*times)/drag
    return speed*k + acceleration*(times-k)/drag


def fit_sliding_friction(sample):
    """Fit single-view projected rigid boxes, with known g; return diagnostics.

    Required evidence flags distinguish an estimated effective coefficient from
    a verified material-parameter measurement. No gravity/geometry/clock is
    optimized and no ground-truth velocity is accepted by this function.
    """
    evidence = sample.get('evidence', {})
    reasons = [k for k in ('clock_verified', 'initial_identity_verified',
                           'single_plane_sliding', 'no_external_force', 'rotation_stable')
               if evidence.get(k) is not True]
    if reasons:
        return dict(status='inapplicable', reason='unverified_' + ','.join(reasons))
    try:
        times = np.asarray(sample['times_s'], dtype=float)
        boxes = np.asarray(sample['boxes_xyxy'], dtype=float)
        if (times.ndim != 1 or len(times) < 6 or boxes.shape != (len(times), 4)
                or not np.isfinite(times).all() or not np.isfinite(boxes).all()
                or np.any(np.diff(times) <= 0) or np.any(boxes[:, 2:] <= boxes[:, :2])):
            raise ValueError('missing_or_invalid_fixed_window_observations')
        times = times-times[0]
        if np.max(np.linalg.norm(boxes[:, :2]-boxes[0, :2], axis=1)) < 3.:
            out = dict(status='unidentifiable', reason='static_or_below_3px_motion',
                       friction=None, static_motion_is_not_exact_kinetic_friction=True)
            if evidence.get('static_equilibrium_verified') is True and evidence.get('camera_verified') is True:
                theta = float(sample['slope_angle_deg'])
                if not np.isfinite(theta) or not 0 <= theta < 90:
                    raise ValueError('invalid_static_equilibrium_slope')
                out['static_friction_bound'] = dict(lower=float(np.tan(np.radians(theta))),
                    upper=None, point_estimate=False, coefficient_scope='static_friction',
                    conditional_on_registered_static_equilibrium=True)
            return out
        camera = Camera.from_dict(sample['camera'], sample['image_size'])
        g, theta = float(sample['gravity_mps2']), np.radians(float(sample['slope_angle_deg']))
        if not (math.isfinite(g) and g > 0 and math.isfinite(theta) and abs(theta) < np.pi/2):
            raise ValueError('invalid_independent_gravity_or_slope')
        direction = np.asarray(sample['downhill_direction'], dtype=float)
        if direction.shape != (3,) or not np.isfinite(direction).all() or np.linalg.norm(direction) == 0:
            raise ValueError('invalid_slide_direction')
        direction = direction/np.linalg.norm(direction)
        # Angles and gravity must describe this same plane and signed direction.
        if abs(direction[2] + np.sin(theta)) > 1e-6:
            raise ValueError('slope_and_direction_mismatch')
        origin, corners = np.asarray(sample['initial_position'], float), np.asarray(sample['world_corners'], float)
        if origin.shape != (3,) or corners.ndim != 2 or corners.shape[1] != 3 or not np.isfinite(corners).all() or not np.isfinite(origin).all():
            raise ValueError('invalid_declared_geometry')
        drag = float(sample.get('drag_per_second', 0.))
        if not math.isfinite(drag) or drag < 0:
            raise ValueError('invalid_declared_drag')

        def project(p):
            mu, speed = p
            a = g*(np.sin(theta)-mu*np.cos(theta))
            distance = sliding_displacement(times, speed, a, drag)
            centres = origin + distance[:, None]*direction
            return camera.project_box(centres[:, None, :]+corners)

        def residual(p):
            b = project(p)
            if not np.isfinite(b).all():
                return np.full(boxes.size, 1e6)
            # A fixed edge offset accommodates mesh/proxy differences, not motion.
            diff = b-boxes
            return (diff-diff.mean(axis=0)).ravel()

        # The declared initial pose is fixed, as are camera and plane. Optimizing
        # it alongside a constant edge offset introduces redundant depth freedom.
        # Start near zero along-plane acceleration, using only the known slope.
        # A hard-coded low friction can launch a long-window hypothesis behind
        # the camera, where a flat invalid-projection penalty has no gradient.
        initial_mu = float(np.clip(np.tan(theta), 1e-6, 5.-1e-6))
        result = least_squares(residual, [initial_mu, .1], bounds=([0., 0.], [5., 8.]),
                               max_nfev=400, xtol=1e-10, ftol=1e-10, gtol=1e-10)
        mu, speed = map(float, result.x)
        a = g*(np.sin(theta)-mu*np.cos(theta))
        velocity = speed+a*times if drag == 0 else speed*np.exp(-drag*times)+a*(-np.expm1(-drag*times))/drag
        predicted = project(result.x)
        if not result.success or not np.isfinite(result.x).all() or not np.isfinite(predicted).all():
            return dict(status='fit_failure', reason='optimizer_failed_or_invalid_projection',
                        frames=len(times), gravity_mps2=g, gravity_optimized=False)
        out = dict(friction=mu, speed_at_window_start_mps=speed, acceleration_mps2=float(a),
                   position_offset_m=0., initial_position_optimized=False,
                   predicted_boxes_xyxy=predicted.tolist(),
                   pixel_residual_rmse=float(np.sqrt(np.mean(result.fun**2))),
                   frames=len(times), gravity_mps2=g, gravity_optimized=False,
                   observation_source=sample.get('observation_source'),
                   coefficient_scope='effective_kinetic_contact_coefficient')
        if mu < 1e-6 or mu > 5.-1e-6 or speed > 8.-1e-6:
            return dict(out, status='at_bound', reason='parameter_at_search_limit')
        if np.any(velocity < -1e-4):
            return dict(out, status='inapplicable', reason='registered_window_contains_stop_or_reversal')
        pending = [k for k in ('camera_verified', 'effective_friction_verified')
                   if evidence.get(k) is not True]
        if pending:
            return dict(out, status='review_required', reason='unverified_' + ','.join(pending))
        return dict(out, status='ok')
    except (KeyError, ValueError, TypeError, np.linalg.LinAlgError) as error:
        return dict(status='input_failure', reason=str(error))
