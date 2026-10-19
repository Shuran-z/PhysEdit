"""Development-only velocity estimation with explicitly registered motion planes.

The frozen gravity output is never replaced. Trajectory curvature is a velocity
nuisance, initialized from that output rather than treating it as exact truth.
Motion-plane evidence is additional source information, not inferred from the
velocity scoring target. Unregistered/nonplanar cases remain in the denominator.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from gravtrace.fit import _Problem
from gravtrace.motion import ballistic
from .motion_parameters import velocity_from_prediction


def sample_digest(sample):
    return hashlib.sha256(json.dumps(sample, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


class RegisteredPlanes:
    """Read-only development source binding, never a formal QA certification."""

    def __init__(self, path, expected_sha256):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('plane_registration_path_must_be_absolute')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('plane_registration_sha_mismatch')
        rows = json.loads(raw)
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('duplicate_plane_registration_member')
        self.rows = {r['id']: r for r in rows}

    def validate_initial_reference(self, sample, saved_gravity):
        """Bind an unconstrained estimate to its original pose and observation clock.

        Observations may start later than the declared initial state. This reads
        only that initial position, never a source velocity or future trajectory.
        """
        row = self.rows.get(sample['id'])
        if row is None or row['input_sample_sha256'] != sample_digest(sample):
            raise ValueError('missing_or_drifted_registered_velocity_input')
        bound = {}
        for kind in ('header', 'state'):
            path = Path(row['source_'+kind+'_path'])
            if not path.is_absolute():
                raise ValueError('source_binding_path_must_be_absolute')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row['source_'+kind+'_sha256']:
                raise ValueError('registered_velocity_source_'+kind+'_drift')
            bound[kind] = path
        header = json.loads(bound['header'].read_text())
        fps = float(header['fps'])
        initial = row['source_initial_frame']
        frames = row['source_frame_indices']
        if (type(initial) is not int or initial < 0 or not frames
                or any(type(f) is not int or f < initial for f in frames)
                or any(b <= a for a, b in zip(frames, frames[1:]))):
            raise ValueError('invalid_registered_source_window')
        times = np.asarray(sample['boxes']['times'], float)
        expected = (np.asarray(frames)-initial)/fps if fps > 0 else np.full(len(frames), np.nan)
        offset = float(saved_gravity['params']['t0'])
        if (not np.isfinite(fps) or fps <= 0 or float(sample['fps']) != fps
                or len(frames) != len(sample['boxes']['frames']) or times.shape != (len(frames),)
                or not np.isfinite(times).all() or not np.allclose(times, expected, atol=1e-9, rtol=0)
                or not np.isfinite(offset) or abs(offset-times[0]) > 1e-9):
            raise ValueError('registered_velocity_reference_clock_mismatch')
        if row['object_name'] not in {o['name'] for o in header['objects']}:
            raise ValueError('registered_source_object_identity_mismatch')
        with np.load(bound['state']) as state:
            index = list(state['names']).index(row['object_name'])
            if max(frames) >= len(state['position']):
                raise ValueError('registered_velocity_frame_outside_source')
            position = state['position'][initial, index]
        if not np.isfinite(position).all() or not np.allclose(position, sample['object']['position'], atol=1e-10, rtol=0):
            raise ValueError('registered_velocity_initial_state_mismatch')
        return row

    def validate(self, sample):
        row = self.rows.get(sample['id'])
        if row is None:
            raise ValueError('missing_registered_plane_member')
        if row['input_sample_sha256'] != sample_digest(sample):
            raise ValueError('plane_registration_input_sample_drift')
        if row['status'] != 'registered':
            return row
        paths = {}
        for kind in ('header', 'state'):
            path = Path(row['source_'+kind+'_path'])
            if not path.is_absolute():
                raise ValueError('source_binding_path_must_be_absolute')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row['source_'+kind+'_sha256']:
                raise ValueError('registered_plane_source_'+kind+'_drift')
            paths[kind] = path
        header = json.loads(paths['header'].read_text())
        axes = []
        for obj in header['objects']:
            if obj.get('fixed'):
                continue
            velocity = np.asarray(obj.get('motion', {}).get('initial_velocity', [0, 0, 0]), float).copy()
            if velocity.shape != (3,) or not np.isfinite(velocity).all():
                raise ValueError('invalid_source_declared_velocity_direction')
            velocity[2] = 0
            if np.linalg.norm(velocity) > 1e-6:
                axes.append(velocity/np.linalg.norm(velocity))
        axis = np.asarray(row['axis'], float)
        if (axis.shape != (3,) or not np.isfinite(axis).all() or not axes or not np.allclose(axis, axes[0], atol=1e-10)
                or not all(abs(a@axes[0]) > np.cos(np.radians(1)) for a in axes)):
            raise ValueError('source_declared_plane_axis_mismatch')
        frames = row['source_frame_indices']
        if (not frames or any(type(f) is not int or f < 0 for f in frames)
                or len(frames) != len(sample['boxes']['frames']) or frames != list(range(frames[0], frames[0]+len(frames)))):
            raise ValueError('registered_plane_window_mismatch')
        proof_frames = row.get('source_plane_validation_frames', frames)
        if (not proof_frames or any(type(f) is not int or f < 0 for f in proof_frames)
                or proof_frames != list(range(proof_frames[0], proof_frames[0]+len(proof_frames)))
                or not set(frames).issubset(proof_frames)):
            raise ValueError('plane_source_proof_does_not_cover_observation_window')
        fps = float(header['fps'])
        times = np.asarray(sample['boxes']['times'], float)
        expected_times = (np.asarray(frames)-frames[0])/fps if fps > 0 else np.full(len(frames), np.nan)
        if (not np.isfinite(fps) or fps <= 0 or float(sample['fps']) != fps
                or times.shape != (len(frames),) or not np.isfinite(times).all()
                or not np.allclose(times-times[0], expected_times, atol=1e-9, rtol=0)):
            raise ValueError('registered_plane_observation_clock_mismatch')
        with np.load(paths['state']) as state:
            index = list(state['names']).index(row['object_name'])
            if max(proof_frames) >= len(state['position']):
                raise ValueError('registered_plane_frame_outside_source')
            positions = state['position'][frames, index]
            proof_positions = state['position'][proof_frames, index]
        if not np.isfinite(positions).all() or not np.isfinite(proof_positions).all():
            raise ValueError('nonfinite_source_motion_plane')
        if not np.allclose(positions[0], sample['object']['position'], atol=1e-10, rtol=0):
            raise ValueError('registered_plane_initial_state_mismatch')
        normal = np.cross([0, 0, 1], axis)
        drift = float(np.max(abs((proof_positions-proof_positions[0])@normal)))
        if drift > .002 or abs(drift-row['max_plane_drift_m']) > 1e-10:
            raise ValueError('source_motion_does_not_verify_registered_plane')
        return row


def fit_registered_velocity(sample, saved_gravity, planes):
    """Estimate window-origin velocity; never accept a velocity/acceleration target.

    Uses every original observation with nonzero fixed physical-time weights.
    Source conditions determine model applicability before errors are read.
    Acceleration is explicitly reported as a nuisance, not as a new g metric.
    """
    if 'truth' in sample or 'v0' in sample.get('motion', {}):
        return dict(status='input_failure', reason='velocity_truth_in_estimator_input')
    try:
        plane = planes.validate(sample)
        if plane['status'] != 'registered':
            return dict(status='inapplicable', reason=plane['reason'])
        if saved_gravity.get('status') != 'ok' or sample.get('scenario') != 'projectile':
            raise ValueError('requires_frozen_projectile_reference')
        frames = np.asarray(sample['boxes']['frames'], int)
        boxes = np.asarray(sample['boxes']['xyxy'], float)
        times = np.asarray(sample['boxes']['times'], float)
        if (boxes.shape != (len(frames), 4) or len(frames) < 3
                or len(frames) != saved_gravity['frames'] or not np.isfinite(boxes).all()
                or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
            raise ValueError('invalid_original_observation_window')
        times = times-times[0]
        visible = sample.get('window', {}).get('edges_visible', {})
        seen = np.asarray([visible.get(str(f), [True]*4) for f in frames], bool)
        problem = _Problem(sample, times, boxes, seen)
        if problem.anchor is None:
            raise ValueError('insufficient_visible_supports')
        g = float(saved_gravity['gravity'])
        offset = float(saved_gravity['params']['t0'])
        if not np.isfinite([g, offset]).all() or g <= 0:
            raise ValueError('invalid_frozen_gravity_or_time')
        if abs(offset) > 1e-8:
            return dict(status='inapplicable', reason='nonzero_time_offset_requires_velocity_reference_conversion')
        tau = times+offset
        axis = np.asarray(plane['axis'], float)
        if abs(axis@problem.g_dir) > 1e-8:
            raise ValueError('motion_plane_axis_not_horizontal')
        basis = np.column_stack([axis, -problem.g_dir])
        seed = np.r_[basis.T@velocity_from_prediction(saved_gravity, problem.g_dir), -g]
        time_weight = np.sqrt(1/(1+(times/.25)**2))

        def project(x):
            centres = ballistic(tau, problem.x0, basis@x[:2], -x[2], problem.g_dir, problem.drag)
            return problem.camera.project_box(problem.points(tau, centres))

        def residual(x):
            boxes = project(x)
            if not np.isfinite(boxes).all():
                return np.full(problem.obs.size, 1e6)
            diff = boxes-problem.obs
            weights = problem.weight**2
            diff -= (diff*weights).sum(axis=0)/np.maximum(weights.sum(axis=0), 1e-12)
            return (diff*problem.weight*time_weight[:, None]).ravel()

        bounds = ([-8, -8, -80], [8, 8, -.1])
        fits = [least_squares(residual, start, bounds=bounds, loss='soft_l1', f_scale=1,
                              max_nfev=200) for start in (seed, np.array([0, 0, -g]))]
        first = min(fits, key=lambda f: f.cost)
        values = residual(first.x)[problem.weight.ravel() > 0]
        sigma = max(.5, 1.4826*float(np.median(abs(values-np.median(values)))))
        result = least_squares(residual, first.x, bounds=bounds, loss='soft_l1', f_scale=sigma,
                               max_nfev=200)
        if not result.success or not np.isfinite(result.x).all() or not np.isfinite(project(result.x)).all():
            return dict(status='fit_failure', reason='kinematic_velocity_optimizer_failed_or_invalid_projection')
        velocity = basis@result.x[:2]
        if np.linalg.norm(velocity) >= 8-1e-6 or result.x[2] <= -80+1e-6 or result.x[2] >= -.1-1e-6:
            return dict(status='at_bound', reason='kinematic_velocity_search_limit')
        return dict(status='ok', velocity_vector_mps=velocity.tolist(),
                    speed_mps=float(np.linalg.norm(velocity)), pixel_cost=float(result.cost),
                    vertical_acceleration_nuisance_mps2=float(result.x[2]), pixel_noise_scale=sigma,
                    source_motion_plane_axis=axis.tolist(), frames=len(frames),
                    frozen_gravity_result_changed=False, trajectory_curvature_fitted_for_velocity=True,
                    additional_source_information='registered_source_motion_plane',
                    method='registered_planar_kinematic_velocity_v2',
                    scientific_independence_certified=False)
    except (OSError, KeyError, IndexError, ValueError, TypeError, np.linalg.LinAlgError) as error:
        return dict(status='input_failure', reason=str(error))


def fit_coverage_velocity(sample, saved_gravity, planes):
    """Retain planar estimates; try full 3D only for source-plane exclusions.

    The branch is chosen from source applicability, not from scoring targets or
    errors. Full-3D convergence is not a certificate of high velocity precision.
    """
    if 'truth' in sample or 'v0' in sample.get('motion', {}):
        return dict(status='input_failure', reason='velocity_truth_in_estimator_input')
    try:
        plane = planes.validate(sample)
        if plane['status'] == 'registered':
            return dict(fit_registered_velocity(sample, saved_gravity, planes),
                        source_model_branch='registered_planar')
        if plane.get('reason') not in ('observed_source_motion_not_in_declared_plane', 'missing_declared_motion_plane'):
            return dict(status='inapplicable', reason=plane.get('reason', 'unsupported_source_model'))
        if saved_gravity.get('status') != 'ok' or sample.get('scenario') != 'projectile':
            raise ValueError('requires_frozen_projectile_reference')
        reference = planes.validate_initial_reference(sample, saved_gravity)
        frames = np.asarray(sample['boxes']['frames'], int)
        boxes = np.asarray(sample['boxes']['xyxy'], float)
        times = np.asarray(sample['boxes']['times'], float)
        if (boxes.shape != (len(frames), 4) or len(frames) < 3
                or len(frames) != saved_gravity['frames'] or not np.isfinite(boxes).all()
                or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
            raise ValueError('invalid_original_observation_window')
        times = times-times[0]+float(saved_gravity['params']['t0'])
        visible = sample.get('window', {}).get('edges_visible', {})
        seen = np.asarray([visible.get(str(f), [True]*4) for f in frames], bool)
        problem = _Problem(sample, times, boxes, seen)
        if problem.anchor is None:
            return dict(status='inapplicable', reason='insufficient_visible_supports')
        g = float(saved_gravity['gravity'])
        if not np.isfinite(g) or not .1 < g < 80:
            raise ValueError('invalid_frozen_gravity_initialization')
        seed = np.r_[velocity_from_prediction(saved_gravity, problem.g_dir), -g]

        def project(x):
            centres = ballistic(times, problem.x0, x[:3], -x[3], problem.g_dir, problem.drag)
            return problem.camera.project_box(problem.points(times, centres))

        def residual(x):
            projected = project(x)
            if not np.isfinite(projected).all():
                return np.full(problem.obs.size, 1e6)
            diff = projected-problem.obs
            weights = problem.weight**2
            diff -= (diff*weights).sum(axis=0)/np.maximum(weights.sum(axis=0), 1e-12)
            return (diff*problem.weight).ravel()

        bounds = ([-8, -8, -8, -80], [8, 8, 8, -.1])
        fits = [least_squares(residual, start, bounds=bounds, loss='soft_l1', f_scale=1,
                              max_nfev=300) for start in (seed, np.array([0, 0, 0, -g]))]
        best = min(fits, key=lambda f: f.cost)
        if not best.success or not np.isfinite(best.x).all() or not np.isfinite(project(best.x)).all():
            return dict(status='fit_failure', reason='unconstrained_velocity_optimizer_failed_or_invalid_projection')
        velocity = best.x[:3]
        if np.linalg.norm(velocity) >= 8-1e-6 or best.x[3] <= -80+1e-6 or best.x[3] >= -.1-1e-6:
            return dict(status='at_bound', reason='unconstrained_velocity_search_limit')
        return dict(status='ok', velocity_vector_mps=velocity.tolist(), speed_mps=float(np.linalg.norm(velocity)),
                    vertical_acceleration_nuisance_mps2=float(best.x[3]), pixel_cost=float(best.cost),
                    frames=len(frames), source_model_branch='unconstrained_3d',
                    original_plane_exclusion_reason=plane['reason'],
                    source_observation_gap_count=reference['source_frame_indices'][-1]-reference['source_frame_indices'][0]+1-len(frames),
                    reference='declared_initial_state', observation_start_offset_s=float(times[0]),
                    frozen_gravity_result_changed=False, trajectory_curvature_fitted_for_velocity=True,
                    method='source_dispatched_velocity_coverage_v3', high_precision_certified=False,
                    scientific_independence_certified=False)
    except (OSError, KeyError, IndexError, ValueError, TypeError, np.linalg.LinAlgError) as error:
        return dict(status='input_failure', reason=str(error))
