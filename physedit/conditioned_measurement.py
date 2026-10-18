"""Evaluate current video observations using a registered condition-only model."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import cv2
import numpy as np

from .runners.media_contract import sha256


def read(path):
    return json.loads(Path(path).read_text())


def model_module(name):
    registry = read(Path(__file__).with_name('conditioned_models') / 'registry.json')
    if name not in registry:
        raise ValueError('unregistered_condition_model')
    for module, digest in registry.items():
        path = Path(__file__).with_name('conditioned_models') / (module + '.py')
        if sha256(path) != digest:
            raise ValueError('condition_model_source_changed: ' + module)
    return importlib.import_module('physedit.conditioned_models.' + name)


def reject_target(data):
    """The scoring table, source trajectories and old observations stay outside fitting."""
    forbidden = {'g', 'g0', 'g_value', 'gravity', 'gravity_magnitude', 'target_gravity', 'gravity_target',
                 'gravity_m_s2', 'gravity_truth', 'reference_gravity',
                 'estimated_gravity', 'reference_estimate_m_s2', 'truth', 'future_poses',
                 'source_poses', 'source_states', 'observed_boxes', 'boxes_xyxy',
                 'distance_m', 'normal_translation_m', 'observed_masks', 'boxes',
                 'visibility_mask_files', 'masks', 'source_video', 'reference_video'}
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in forbidden or (key.lower() == 'known_gravity' and value is not None):
                raise ValueError('target_or_reference_observations_in_conditions: ' + key)
            reject_target(value)
    elif isinstance(data, list):
        for value in data:
            reject_target(value)


def largest_mask(path):
    mask = np.load(path, allow_pickle=False)['mask'].astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        raise ValueError('empty_generated_object_mask')
    label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == label


def mask_box(mask):
    y, x = np.where(mask)
    return [float(x.min()), float(y.min()), float(x.max() + 1), float(y.max() + 1)]


def viewport_edges(boxes, size):
    w, h = size
    return [[b[0] > 0, b[1] > 0, b[2] < w, b[3] < h] for b in boxes]


def descriptor(task):
    path = Path(task['estimator'])
    if sha256(path) != task['estimator_sha256']:
        raise ValueError('registered_estimator_changed')
    d = read(path)
    if d.get('kind') not in {'frozen', 'ramp_rgb', 'displacement_rgb', 'displacement_pitch', 'native_physx', 'model'}:
        raise ValueError('unregistered_condition_measurement_kind')
    if 'forward_model_bank' in d:
        raise ValueError('reference_adaptive_response_bank_not_permitted')
    known_path = path.parent / d['known_conditions']
    if sha256(known_path) != d['known_conditions_sha256']:
        raise ValueError('registered_known_conditions_changed')
    known = read(known_path)
    reject_target(known)
    if d.get('observer'):
        reject_target(d['observer'])
    if d.get('module') and d['module'] != 'known_contact_rgb':
        model_module(d['module'])
    if d.get('audit_module'):
        model_module(d['audit_module'])
    return d, known, path.parent


def minimum_observations(d):
    if d['kind'] == 'ramp_rgb' or d.get('module') in ('known_contact_gravity', 'known_push_gravity', 'shallow_surface_RGB'):
        return 6
    if d['kind'] in ('frozen', 'displacement_rgb', 'displacement_pitch', 'native_physx'):
        return 4
    if d.get('module') in ('isolated_stopping_masks_yaw', 'foreground_safe_control_RGB',
                           'known_group_outline', 'closed_damped_visible_initial',
                           'released_foreground_rgb', 'visible_foreground_rgb',
                           'floor_hinge_surface_RGB', 'known_force_safe_RGB'):
        return 4
    return 2


def native_control_clock(d, known, times):
    """Adapt declared controls to observation times without changing the solver tick."""
    if d.get('module') != 'known_group_outline':
        return None
    c = known['known_group_condition']
    ct = np.asarray(d['registered_physical_times_s'])
    if (len(ct) != len(c['world_force_updates_from_config']) or
            np.max(np.abs(ct / c['step_s'] - np.rint(ct / c['step_s']))) > 1e-7):
        return 'declared_control_schedule_not_on_solver_step_grid'
    return None


def observation_video(video, frames, output):
    """Losslessly materialize the fixed native-frame prefix for sequential readers."""
    if frames != list(range(len(frames))):
        raise ValueError('observation_prefix_must_be_native_contiguous_frames')
    cap = cv2.VideoCapture(str(video))
    destination = Path(output) / 'current_observation.avi'
    writer = None
    try:
        for frame in frames:
            ok, image = cap.read()
            if not ok:
                raise ValueError('generated_observation_prefix_decode_failed')
            if writer is None:
                h, w = image.shape[:2]
                writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*'FFV1'),
                                         cap.get(cv2.CAP_PROP_FPS), (w, h))
                if not writer.isOpened():
                    raise ValueError('lossless_observation_writer_unavailable')
            writer.write(image)
    finally:
        cap.release()
        if writer is not None:
            writer.release()
    return str(destination)


def measure(task, video, frames, physical_times, masks_by_role, output, native_runtime=None):
    """Only the current video's masks and pixels supply post-condition observations."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    d, p, assets = descriptor(task)
    frames = list(frames)
    times = np.asarray(physical_times, float)
    if len(frames) < minimum_observations(d):
        return {'status': 'insufficient_temporal_evidence', 'gravity': None,
                'reason': 'native_frames_within_fixed_horizon_below_model_minimum'}
    if times[0] != 0 or not np.all(np.diff(times) > 0):
        raise ValueError('invalid_condition_relative_physics_clock')
    target = task['target_name']
    roles = task.get('measurement_roles', [target])
    if len(roles) > 1:
        combined = []
        for k in range(len(frames)):
            parts = []
            for role in roles:
                path = masks_by_role[role][k]
                if path is None:
                    raise ValueError('missing_generated_instance_in_union')
                parts.append(np.load(path, allow_pickle=False)['mask'].astype(bool))
            mask = np.logical_or.reduce(parts)
            path = output / ('union_%04d.npz' % k)
            np.savez_compressed(path, mask=mask)
            combined.append(str(path))
        masks_by_role = dict(masks_by_role, **{target: combined})
    paths = masks_by_role[target]
    if len(paths) != len(frames) or any(x is None for x in paths):
        raise ValueError('missing_generated_observation_in_fixed_scope')
    masks = [np.load(x, allow_pickle=False)['mask'].astype(bool) for x in paths]
    if any(not m.any() for m in masks):
        raise ValueError('empty_generated_object_mask')
    mask_paths = []
    for k, mask in enumerate(masks):
        dest = output / ('mask_%04d.npz' % k)
        np.savez_compressed(dest, mask=mask)
        mask_paths.append(str(dest.resolve()))
    boxes = [mask_box(m) for m in masks] if len(roles) > 1 else [mask_box(largest_mask(x)) for x in paths]
    if 'times_s' in p:
        p['times_s'] = times.tolist()
    if 'times_s' in p.get('condition', {}):
        p['condition']['times_s'] = times.tolist()
    clock_failure = native_control_clock(d, p, times)
    if clock_failure:
        return dict(status='unsupported_native_model_time_grid', gravity=None, reason=clock_failure)
    packet = dict(video=str(Path(video).resolve()), video_sha256=sha256(video),
                  frames=frames, condition_frame=0, visibility_mask_files=mask_paths)
    kind = d['kind']
    if kind == 'frozen':
        from gravtrace.fit import safe_fit
        from gravtrace.observations import refine_box
        cap = cv2.VideoCapture(str(video))
        try:
            for k, frame in enumerate(frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                ok, image = cap.read()
                if not ok:
                    raise ValueError('generated_frame_decode_failed')
                boxes[k], _ = refine_box(image, masks[k], boxes[k])
        finally:
            cap.release()
        p['id'] = 'observation'
        p['fps'] = 1 / float(times[1] - times[0])
        p['window'].update(start_frame=0, max_frames=len(frames),
                           edges_visible={str(k): e for k, e in enumerate(viewport_edges(boxes, p['image_size']))})
        p['boxes'] = dict(frames=list(range(len(frames))), times=times.tolist(), xyxy=boxes)
        result = safe_fit(p)
    elif kind == 'native_physx':
        from .native_physics import ForwardModel
        if native_runtime is None:
            return dict(status='native_runtime_unavailable', gravity=None,
                        reason='CPU_forward_model_command_not_configured')
        p.update(id='observation', frames=frames, observation_output=str(output.resolve()),
                 observed_masks=[])
        for k in range(len(frames)):
            row = []
            for role in ('striker', 'book'):
                source = masks_by_role.get(role, [None] * len(frames))[k]
                row.append(dict(path=source, sha256=sha256(source)) if source else None)
            p['observed_masks'].append(row)
        objective = model_module(d['module']).photo(p)
        # Every candidate, including the initial common grid, is a new forward response.
        # Reference-adaptive candidate values and reference image costs are never loaded.
        worker = ForwardModel(native_runtime, p['payload'], times, output)
        try:
            actual = worker.evaluate
            grid = [.5, 1., 2., 4., 8., 16., 32., 64.]
            search = model_module('actual_scalar_grid_search').optimize(
                [(g, actual(g)) for g in grid], objective, actual, tolerance=.001)
            pred = search['prediction']
            result = dict(pred, gravity=pred['estimate'], reference_cache_used=False,
                          new_forward_trials=True, native_worker=worker.ready)
            (output / 'current_video_trials.json').write_text(json.dumps(search, allow_nan=False))
        finally:
            worker.close()
    elif kind in ('ramp_rgb', 'displacement_rgb', 'displacement_pitch'):
        observer = copy.deepcopy(d['observer'])
        observer.update(packet)
        cap = cv2.VideoCapture(str(video))
        images = []
        try:
            for frame in frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                ok, image = cap.read()
                if not ok:
                    raise ValueError('generated_frame_decode_failed')
                images.append(image)
        finally:
            cap.release()
        obs = model_module(d['observer_module']).observe(
            observer['camera'], observer['image_size'], observer['origin'], observer['world_vertices'],
            observer['faces'], observer['axis'], images, secondary_axis=observer['secondary_axis'],
            visibility_masks=masks)
        (output / 'image_observations.json').write_text(json.dumps(obs, allow_nan=False))
        if any(s not in ('condition', 'observed') or e is None or e > .05
               for s, e in zip(obs['observation_status'], obs['photo_rmse'])):
            return {'status': 'image_observation_failure', 'gravity': None,
                    'reason': 'registered_RGB_quality_failed_in_fixed_scope'}
        if kind == 'ramp_rgb':
            from scipy.optimize import least_squares
            from .motion_parameters import sliding_displacement
            theta = np.radians(p['slope_angle_deg'])
            coefficient = np.sin(theta) - p['known_effective_friction'] * np.cos(theta)
            distance = np.asarray(obs['distance_m'])
            def residual(x):
                return sliding_displacement(times, x[1], np.exp(x[0]) * coefficient,
                                            p['drag_per_second']) - distance
            fits = [least_squares(residual, [np.log(seed), .1], bounds=([np.log(.1), 0], [np.log(80), 8]),
                     loss='soft_l1', f_scale=.00025, max_nfev=400, xtol=1e-11, ftol=1e-11, gtol=1e-11)
                    for seed in (1., 4., 16., 50.)]
            fit = min(fits, key=lambda x: x.cost)
            g = float(np.exp(fit.x[0]))
            result = dict(status='ok' if fit.success and .101 < g < 79.2 else 'at_bound',
                          gravity=g, initial_speed_mps=float(fit.x[1]))
        else:
            p.update(distance_m=obs['distance_m'], normal_translation_m=obs['secondary_translation_m'])
            result = model_module(d['module']).predict(p)
    else:
        module = model_module(d['module'])
        if d['module'] in ('released_foreground_rgb', 'visible_foreground_rgb', 'foreground_safe_control_RGB'):
            packet['video'] = observation_video(video, frames, output)
            packet['video_sha256'] = sha256(packet['video'])
        keys = getattr(module, 'KEYS', set())
        if 'video' in keys or hasattr(module, 'predict') and 'video' in d.get('observation_fields', []):
            p.update(packet)
            if 'condition_frame' not in d['observation_fields']:
                p.pop('condition_frame', None)
        if 'observed_boxes' in d['observation_fields']:
            p['observed_boxes'] = boxes
        if 'boxes_xyxy' in d['observation_fields']:
            p['boxes_xyxy'] = boxes
        if 'edges_visible' in d['observation_fields']:
            p['edges_visible'] = viewport_edges(boxes, task['image_size'])
        if 'frames' in d['observation_fields']:
            p['frames'] = frames
        if 'masks' in d['observation_fields']:
            p['masks'] = [dict(path=f, sha256=sha256(f)) for f in mask_paths]
        if d['module'] == 'foreground_safe_control_RGB':
            if len(times) != 4:
                return dict(status='unsupported_native_model_time_grid', gravity=None,
                            reason='registered_four_observation_model')
            h = p['known_interval']['integration_substep_s']
            n = float(times[1] / h)
            if abs(n - round(n)) > 1e-7:
                return dict(status='unsupported_native_model_time_grid', gravity=None,
                            reason='observation_interval_not_on_solver_step_grid')
            p['known_interval']['steps_per_observation'] = round(n)
        if d['module'] == 'known_group_outline':
            from .conditioned_control_clock import predict
            result = predict(p, d['registered_physical_times_s'])
        else:
            result = (module.estimate if hasattr(module, 'estimate') else module.predict)(p)
    result.update(frames=frames, physical_times_s=times.tolist(), video_sha256=sha256(video),
                  condition_frame=0, prior_fill=False, reference_result_reused=False)
    if d.get('audit_module') and result.get('gravity') is not None:
        input_path = output / 'current_observation_input.json'
        input_path.write_text(json.dumps(p, allow_nan=False))
        result['closed_input_sha256'] = sha256(input_path)
        prediction_path = output / 'prediction_before_quality.json'
        prediction_path.write_text(json.dumps(result, allow_nan=False))
        quality_path = output / 'image_quality.json'
        model_module(d['audit_module']).audit(str(input_path), str(prediction_path), str(quality_path))
        quality = read(quality_path)
        result['image_quality'] = quality
        if quality.get('status') not in ('image_precision_pass', 'image_quality_pass', 'PASS'):
            result.update(status='image_precision_review_required', reason=quality.get('status'))
    (output / 'prediction.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
    return result
