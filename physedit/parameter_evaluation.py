"""Generated-video motion measurements with per-metric applicability and full IDs.

Estimators and the SAM/gravity implementation are reused unchanged. Targets are
kept outside estimator inputs; observations always belong to the generated video.
"""
import copy
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from .inversion_inputs import item_digest
from .motion_parameters import fit_sliding_friction, fit_velocity_with_frozen_gravity, scalar_error
from .runners.media_contract import sha256, validate_video

PARAMETERS = ('velocity', 'friction')
GRAVITY_ONLY_REASONS = {
    'reference_motion_not_supported_by_frozen_generation_score',
    'reference_not_qualified_by_existing_benchmark', 'reference_inversion_not_valid',
    'missing_reference_applicability_evidence', 'missing_verified_reference_item',
    'not_applicable_registered_window',
}
CONDITION_FIELDS = {'gravity_mps2', 'slope_angle_deg', 'downhill_direction',
                    'initial_position', 'world_corners', 'drag_per_second', 'evidence'}


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def write_rows(path, values):
    with Path(path).open('x') as f:
        for value in values:
            f.write(json.dumps(value, allow_nan=False) + '\n')


def friction_inputs(config, items):
    if not config.get('manifest'):
        return {}
    path = Path(config['manifest']).expanduser().resolve()
    if sha256(path) != config['manifest_sha256']:
        raise ValueError('friction_manifest_sha256_mismatch')
    entries = rows(path)
    if (any(not isinstance(r, dict) or not isinstance(r.get('item_id'), str) for r in entries)
            or len({r['item_id'] for r in entries}) != len(entries)
            or {r['item_id'] for r in entries} - set(items)):
        raise ValueError('friction_manifest_identity_mismatch')
    return {r['item_id']: r for r in entries}


def declaration(entry, item):
    """Check declared conditions, not a generated physical-truth assertion."""
    allowed = {'item_id', 'item_sha256', 'window', 'conditions', 'source_files',
               'requested_effective_friction', 'requested_initial_velocity_mps'}
    if set(entry) - allowed:
        raise ValueError('unsupported_friction_manifest_fields')
    if entry.get('item_sha256') != item_digest(item):
        raise ValueError('friction_source_item_changed')
    bindings = entry.get('source_files')
    if not isinstance(bindings, list) or not bindings:
        raise ValueError('missing_friction_source_evidence')
    for binding in bindings:
        if (not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}
                or not Path(binding['path']).is_absolute()
                or sha256(binding['path']) != binding['sha256']):
            raise ValueError('friction_source_evidence_drift')
    conditions = entry.get('conditions')
    if not isinstance(conditions, dict) or set(conditions) - CONDITION_FIELDS:
        raise ValueError('invalid_friction_conditions')
    for key in CONDITION_FIELDS - {'drag_per_second'}:
        if key not in conditions:
            raise ValueError('missing_friction_condition: ' + key)
    if not isinstance(conditions['evidence'], dict):
        raise ValueError('invalid_friction_evidence_flags')
    if conditions['gravity_mps2'] != item['gravity']:
        raise ValueError('friction_known_gravity_request_mismatch')
    # No observed pixels or scoring target can be supplied as conditions.
    window = entry.get('window', {k: item['window'][k] for k in ('start_frame', 'max_frames')})
    if (not isinstance(window, dict) or set(window) - {'start_frame', 'max_frames'}
            or type(window.get('start_frame')) is not int or window['start_frame'] < 23
            or type(window.get('max_frames')) is not int or window['max_frames'] < 6):
        raise ValueError('invalid_friction_observation_window')
    return copy.deepcopy(conditions), dict(window)


def plan_inputs(spec, items):
    evaluation = spec.get('evaluation', {})
    output = {}
    from .motion_response import load as load_control_groups
    for name in PARAMETERS:
        if name in evaluation.get('metrics', []):
            load_control_groups(evaluation.get(name, {}))
    if 'friction' in evaluation.get('metrics', []):
        config = evaluation.get('friction', {})
        entries = friction_inputs(config, items)
        output['friction'] = dict(registered=len(items), supplied=len(entries),
                                 manifest_sha256=config.get('manifest_sha256'))
    if 'velocity' in evaluation.get('metrics', []):
        output['velocity'] = dict(method='cartesian_fixed_saved_gravity_or_registered_sliding',
                                  registered=len(items))
    return output


def parameter_generation_template(spec, template, output):
    """Allow independently documented sliding cases; keep the original G rejection."""
    evaluation = spec.get('evaluation', {})
    if 'friction' not in evaluation.get('metrics', []):
        return Path(template)
    from scripts import phyediting_gen as gen
    items = {i['id']: i for i in rows(spec['items'])}
    entries = friction_inputs(evaluation.get('friction', {}), items)
    values = rows(template)
    changed = False
    for row in values:
        reason = row.get('input_failure')
        if reason not in GRAVITY_ONLY_REASONS or row['item_id'] not in entries:
            continue
        item = items[row['item_id']]
        try:
            conditions, window = declaration(entries[item['id']], item)
            required = ('clock_verified', 'initial_identity_verified', 'single_plane_sliding',
                        'no_external_force', 'rotation_stable', 'camera_verified', 'effective_friction_verified')
            if any(conditions['evidence'].get(k) is not True for k in required):
                continue
            if item.get('input_failure'):
                continue
            start = window['start_frame'] / float(item['fps'])
            end = start + (window['max_frames'] - 1) / float(item['fps'])
            condition = 23 / float(item['fps'])
            if end > condition + (spec['frames']-1)/float(spec['fps']) + 1e-6 or start < condition:
                continue
            source = Path(row['source_video'])
            if sha256(source) != row['source_video_sha256']:
                raise ValueError('source_video_changed_before_parameter_generation')
            media = validate_video(source, fps=item['fps'], width=row['source_width'], height=row['source_height'])
            if window['start_frame'] + window['max_frames'] > media['frames']:
                raise ValueError('friction_source_window_outside_video')
            cap = cv2.VideoCapture(str(source))
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 23)
                ok, bgr = cap.read()
            finally:
                cap.release()
            if not ok or not cv2.imwrite(row['condition_image'], bgr):
                raise ValueError('condition_frame_read_or_write_failure')
            prompt = item.get('generation_prompt') or gen.EVENTS.get(item['event'])
            if not prompt or item['gravity'] not in gen.GRAVITY:
                continue
            folder = Path(row['prompt_file']).parent
            folder.mkdir(exist_ok=True)
            Path(row['prompt_file']).write_text(f"{prompt} The camera is fixed. {gen.GRAVITY[item['gravity']]}")
            Path(row['negative_prompt_file']).write_text(gen.NEGATIVE)
            row.update(input_failure=None, gravity_inapplicable_reason=reason,
                       generation_qualified_by='registered_single_plane_sliding_conditions')
            changed = True
        except (OSError, ValueError, KeyError, TypeError, cv2.error) as error:
            row['parameter_qualification_failure'] = str(error)
            changed = True
    if not changed:
        return Path(template)
    write_rows(output, values)
    return Path(output)


def scope(row, item, window):
    fps = float(row['output_fps'])
    initial = window['start_frame'] / float(item['fps'])
    end = initial + (window['max_frames']-1) / float(item['fps'])
    condition = row['condition_frame_index'] / float(item['fps'])
    if initial < condition-1e-6 or condition+(row['num_frames']-1)/fps < end-1e-6:
        raise ValueError('parameter_window_not_covered_by_generated_video')
    frames = [f for f in range(row['num_frames']) if initial-1e-6 <= condition+f/fps <= end+1e-6]
    return frames, [condition+f/fps-initial for f in frames]


def observations(row, item, track, frames):
    from scripts.phyediting_gen import _binding_failure
    error = _binding_failure(row, track)
    if error:
        raise ValueError(error)
    target = track.get('tracks', {}).get(item['object_name'])
    if target is None:
        raise ValueError('parameter_track_target_mismatch')
    indices, boxes = target['frames'], target['xyxy']
    if len(indices) != len(boxes) or len(indices) != len(set(indices)):
        raise ValueError('parameter_track_frame_mismatch')
    observed = dict(zip(indices, boxes))
    missing = [f for f in frames if observed.get(f) is None]
    if missing:
        reasons = track.get('reasons', [])
        detail = {str(f): reasons[indices.index(f)] if f in indices and indices.index(f) < len(reasons) else 'missing_frame'
                  for f in missing}
        raise ValueError('missing_parameter_observations: ' + json.dumps(detail, sort_keys=True))
    values = np.asarray([observed[f] for f in frames], float)
    if (values.shape != (len(frames), 4) or not np.isfinite(values).all()
            or np.any(values[:, 2:] <= values[:, :2])):
        raise ValueError('invalid_parameter_observations')
    return values.tolist()


def load_tracks(root, wanted):
    path = Path(root) / 'tracks_v4.jsonl' if root is not None else None
    values = rows(path) if path is not None and path.is_file() else []
    if len({r['id'] for r in values}) != len(values) or {r['id'] for r in values} - wanted:
        raise ValueError('parameter_tracking_identity_mismatch')
    return {r['id']: r for r in values}


def additional_tracks(spec, media_rows, items, initial, requests, existing, output):
    """Track only additional declared frames, with the unchanged SAM frontend."""
    from scripts import sam31_frontend as frontend
    jobs = []
    for row in media_rows:
        sid = row['sample_id']
        if sid not in requests or row.get('input_failure'):
            continue
        item = items[row['item_id']]
        frames = requests[sid]
        old = existing.get(sid, {}).get('tracks', {}).get(item['object_name'], {})
        if set(frames) <= set(old.get('frames', [])):
            continue
        seed = initial.get(sid, {})
        jobs.append(dict(id=sid, video=row['generated_video_resized_to_source'],
                         video_sha256=sha256(row['generated_video_resized_to_source']), fps=row['output_fps'],
                         frames=frames, prompt_frame=seed.get('prompt_frame', 0),
                         scene_boxes=seed.get('objects', {}), target_name=item['object_name'],
                         input_failure=seed.get('input_failure')))
    if not jobs:
        return existing
    output = Path(output)
    job_path = output.parent / 'parameter_sam31_jobs.jsonl'
    write_rows(job_path, jobs)
    frontend.prepare(job_path, output)
    try:
        frontend.run(output, spec['sam3'], spec['checkpoint'])
    except Exception as error:
        if not (output / 'tracks_v4.jsonl').exists():
            frontend.measure(output, pipeline_failure='parameter_frontend_failure: ' + str(error))
    return {**existing, **load_tracks(output, {r['sample_id'] for r in media_rows})}


def friction_case(row, item, track, entry):
    if entry is None:
        return dict(status='inapplicable', reason='missing_registered_sliding_conditions')
    conditions, window = declaration(entry, item)
    required = ('clock_verified', 'initial_identity_verified', 'single_plane_sliding', 'no_external_force', 'rotation_stable')
    missing = [k for k in required if conditions['evidence'].get(k) is not True]
    if missing:
        return dict(status='inapplicable', reason='unverified_' + ','.join(missing))
    frames, times = scope(row, item, window)
    if len(frames) < 6:
        return dict(status='inapplicable', reason='sliding_measurement_requires_six_observations')
    measurement = dict(conditions, boxes_xyxy=observations(row, item, track, frames), times_s=times,
                       camera=copy.deepcopy(item['camera']), image_size=list(item['image_size']), initial_time_s=0.,
                       observation_source='generated_video_frozen_sam31')
    requested = row.get('parameter_targets', {})
    if 'effective_kinetic_friction' in requested and (
            requested['effective_kinetic_friction'] != entry.get('requested_effective_friction')
            or requested.get('friction_reference_source_frame') != window['start_frame']):
        raise ValueError('friction_target_changed_since_generation')
    prediction = fit_sliding_friction(measurement)
    out = dict(prediction=prediction, status=prediction['status'], reason=prediction.get('reason'),
               estimate=prediction.get('friction'), requested=entry.get('requested_effective_friction'),
               static_friction_bound=prediction.get('static_friction_bound'),
               frames=frames, times_s=times, observation_start_offset_s=times[0],
               reference_source_frame=window['start_frame'],
               gravity_basis='known_requested_input_gravity', gravity_mps2=conditions['gravity_mps2'],
               interpretation='effective_coefficient_deviation_conditional_on_declared_sliding_conditions',
               source_item_sha256=item_digest(item), evidence_scope='declared_source_conditions',
               target_basis='generation_request' if 'effective_kinetic_friction' in requested else 'registered_reference')
    if out['status'] == 'ok':
        out['point_estimate_available'] = True
        if out['requested'] is None:
            out.update(status='unscored', reason='missing_requested_effective_friction')
        elif type(out['requested']) not in (int, float) or not math.isfinite(out['requested']) or out['requested'] < 0:
            out.update(status='input_failure', reason='invalid_requested_effective_friction')
        else:
            out.update(scalar_error(out['estimate'], out['requested']))
    return out


def velocity_case(row, item, track, saved, sliding=None, entry=None):
    if (sliding and sliding.get('prediction', {}).get('status') == 'ok'
            and (row.get('gravity_inapplicable_reason') or saved.get('status') != 'ok')):
        conditions, window = declaration(entry, item)
        vector = np.asarray(conditions['downhill_direction'], float)
        vector = vector / np.linalg.norm(vector) * sliding['prediction']['speed_at_window_start_mps']
        target = entry.get('requested_initial_velocity_mps')
        if target is None and window['start_frame'] == item['window']['start_frame']:
            target = item.get('motion', {}).get('v0')
        prediction = dict(status='ok', velocity_vector_mps=vector.tolist(), speed_mps=float(np.linalg.norm(vector)),
                          method='registered_sliding_window_initial_speed', gravity_optimized=False)
        reference = window['start_frame']
    else:
        if row.get('gravity_inapplicable_reason') or saved.get('status') != 'ok':
            return dict(status='inapplicable', reason='requires_valid_frozen_gravity_or_registered_sliding_fit',
                        gravity_status=saved.get('status', 'missing_prediction'))
        frames, times = scope(row, item, item['window'])
        boxes = observations(row, item, track, frames)
        from scripts.phyediting_gen import _sample
        own_track = dict(tracks={item['object_name']: dict(frames=frames, xyxy=boxes)})
        sample = _sample(row, copy.deepcopy(item), own_track, 'agnostic', {})
        sample['motion'].pop('directions', None)
        sample.update(offset_mode='anchor')
        sample['window']['contact_check'] = False
        prediction = fit_velocity_with_frozen_gravity(sample, copy.deepcopy(saved))
        vector = np.asarray(prediction.get('velocity_vector_mps', []), float)
        target = item.get('motion', {}).get('v0')
        reference = item['window']['start_frame']
    out = dict(prediction=prediction, status=prediction['status'], reason=prediction.get('reason'),
               reference_source_frame=reference, reference='declared_measurement_window_initial_state',
               interpretation='initial_velocity_deviation_from_requested_state', gravity_refitted=False)
    if prediction['status'] != 'ok':
        return out
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError('nonfinite_velocity_estimate')
    out.update(estimate=float(np.linalg.norm(vector)), estimate_vector_mps=vector.tolist(), point_estimate_available=True)
    if target is None:
        return dict(out, status='unscored', reason='missing_requested_initial_velocity')
    target = np.asarray(target, float)
    if target.shape != (3,) or not np.isfinite(target).all():
        raise ValueError('invalid_requested_initial_velocity')
    requested = row.get('parameter_targets', {})
    if 'velocity_mps' in requested and (requested['velocity_mps'] != target.tolist()
            or requested.get('velocity_reference_source_frame') != reference):
        raise ValueError('velocity_target_changed_since_generation')
    out['target_basis'] = 'generation_request' if 'velocity_mps' in requested else 'registered_reference'
    speed = float(np.linalg.norm(target))
    difference = float(np.linalg.norm(vector-target))
    out.update(requested=speed, target_vector_mps=target.tolist(), vector_absolute_error_mps=difference,
               vector_relative_error_pct=100*difference/speed if speed > 0 else None,
               **scalar_error(out['estimate'], speed))
    return out


def summarize(media_rows, records, items, parameter):
    if [r['sample_id'] for r in records] != [r['sample_id'] for r in media_rows]:
        raise ValueError('parameter_denominator_or_order_mismatch')

    def stats(selected):
        good = [r for r in selected if r['status'] == 'ok']
        errors = [r['relative_error_pct'] for r in good if r.get('relative_error_pct') is not None]
        failures = [dict(sample_id=r['sample_id'], item_id=r['item_id'], status=r['status'], reason=r.get('reason') or r['status'])
                    for r in selected if r['status'] != 'ok']
        n = len(selected)
        zeros = [r for r in good if r.get('zero_target') is True]
        bounds = sum(bool(r.get('static_friction_bound')) and r['status'] == 'unidentifiable' for r in selected)
        points = sum(r.get('point_estimate_available') is True for r in selected)
        out = dict(registered=n, scored=len(good), failed=len(failures), failures=failures,
                   coverage_percent=100*len(good)/n if n else None,
                   failure_rate_percent=100*len(failures)/n if n else None,
                   status_counts=dict(Counter(r['status'] for r in selected)),
                   reasons=dict(Counter(r['reason'] for r in failures)),
                   point_estimates=points, point_coverage_percent=100*points/n if n else None,
                   relative_error_count=len(errors), mean_error_percent=float(np.mean(errors)) if errors else None,
                   max_error_percent=max(errors) if errors else None,
                   median_error_percent=float(np.median(errors)) if errors else None,
                   p95_error_percent=float(np.percentile(errors, 95)) if errors else None,
                   zero_target_mean_absolute_error=float(np.mean([r['absolute_error'] for r in zeros])) if zeros else None,
                   zero_target_max_absolute_error=max(r['absolute_error'] for r in zeros) if zeros else None,
                   mean_absolute_error=float(np.mean([r['absolute_error'] for r in good])) if good else None,
                   zero_target_count=sum(r.get('zero_target') is True for r in good),
                   static_bounds=bounds, point_or_bound_coverage_percent=100*(points+bounds)/n if n else None)
        if parameter == 'velocity':
            vector = [r['vector_relative_error_pct'] for r in good if r.get('vector_relative_error_pct') is not None]
            out.update(vector_mean_error_percent=float(np.mean(vector)) if vector else None,
                       vector_max_error_percent=max(vector) if vector else None,
                       vector_mean_absolute_error_mps=float(np.mean([r['vector_absolute_error_mps'] for r in good])) if good else None)
        return out
    out = stats(records)
    import scipy
    out.update(parameter=parameter, gravity_refitted=False, source='generated_video_frozen_sam31', groups={},
               runtime_versions=dict(numpy=np.__version__, scipy=scipy.__version__),
               measurement_sources_sha256={name: sha256(Path(__file__).with_name(name))
                                           for name in ('parameter_evaluation.py','motion_parameters.py','motion_response.py')})
    for key in ('split', 'event', 'camera_id', 'model_name', 'seed', 'gravity_truth'):
        groups = {}
        for row, record in zip(media_rows, records):
            value = row.get(key, items[row['item_id']].get(key, 'unspecified'))
            groups.setdefault(str(value), []).append(record)
        out['groups'][key] = {k: stats(v) for k, v in groups.items()}
    return out


def run(spec, media_rows, items, initial, output, predictions, tracking_root, contexts, media_failures):
    enabled = set(spec['evaluation']['metrics']) & set(PARAMETERS)
    if not enabled:
        return {}
    output = Path(output)
    wanted = {r['sample_id'] for r in media_rows}
    failures = dict(media_failures)
    try:
        tracks = load_tracks(tracking_root, wanted)
    except (OSError, ValueError, KeyError, TypeError) as error:
        tracks = {}
        failures.update({sid: str(error) for sid in wanted})
    saved = {}
    for prediction in predictions or []:
        if prediction.get('id') not in wanted or prediction['id'] in saved:
            raise ValueError('parameter_gravity_prediction_identity_mismatch')
        saved[prediction['id']] = prediction.get('prediction', prediction)
    try:
        entries = friction_inputs(spec['evaluation'].get('friction', {}), items) if 'friction' in enabled else {}
        manifest_error = None
    except (OSError, ValueError, KeyError, TypeError) as error:
        entries, manifest_error = {}, str(error)
    requests, declarations_failed = {}, {}
    for row in media_rows:
        sid, item = row['sample_id'], items[row['item_id']]
        if sid in failures or item['id'] not in entries:
            continue
        try:
            _, window = declaration(entries[item['id']], item)
            frames, _ = scope(row, item, window)
            required = ('clock_verified', 'initial_identity_verified', 'single_plane_sliding', 'no_external_force', 'rotation_stable')
            if len(frames) >= 6 and all(entries[item['id']]['conditions']['evidence'].get(k) is True for k in required):
                requests[sid] = frames
        except (OSError, ValueError, KeyError, TypeError) as error:
            declarations_failed[sid] = str(error)
    velocity_tracks = dict(tracks)
    try:
        tracks = additional_tracks(spec, media_rows, items, initial, requests, tracks, output/'parameter_sam31')
    except Exception as error:
        declarations_failed.update({sid: 'parameter_frontend_failure: '+str(error) for sid in requests})
    results = {name: [] for name in enabled}
    for row in media_rows:
        sid, item = row['sample_id'], items[row['item_id']]
        common = dict(sample_id=sid, item_id=item['id'], video_sha256=contexts.get(sid, {}).get('generated_sha256'),
                      gravity_refitted=False, sam_method_changed=False)
        sliding = None
        if 'friction' in enabled:
            try:
                error = failures.get(sid) or manifest_error or declarations_failed.get(sid)
                if error:
                    raise ValueError(error)
                sliding = friction_case(row, item, tracks.get(sid, {}), entries.get(item['id']))
            except Exception as error:
                sliding = dict(status='input_failure', reason=type(error).__name__+': '+str(error))
            results['friction'].append(dict(common, **sliding))
        if 'velocity' in enabled:
            try:
                if sid in failures:
                    raise ValueError(failures[sid])
                velocity = velocity_case(row, item, velocity_tracks.get(sid, {}), saved.get(sid, {}), sliding, entries.get(item['id']))
            except Exception as error:
                velocity = dict(status='input_failure', reason=type(error).__name__+': '+str(error))
            results['velocity'].append(dict(common, **velocity))
    summaries = {}
    for name, records in results.items():
        write_rows(output/(name+'_results.jsonl'), records)
        summaries[name] = summarize(media_rows, records, items, name)
        from .motion_response import summarize as control_summary
        summaries[name]['parameter_response'] = control_summary(media_rows, records, items, name,
                                                               spec['evaluation'].get(name, {}), entries)
    return summaries


def score_gravity(args, media_rows):
    """Run the original scorer on G-applicable inputs; retain excluded IDs."""
    from scripts import phyediting_gen as gen
    excluded = [r for r in media_rows if r.get('gravity_inapplicable_reason')]
    if not excluded:
        return gen.score(args)
    eligible_path = Path(args.out).parent / 'gravity_rows.jsonl'
    write_rows(eligible_path, [r for r in media_rows if not r.get('gravity_inapplicable_reason')])
    own_args = copy.copy(args)
    own_args.rows = str(eligible_path)
    gen.score(own_args)
    with Path(args.out).open('a') as out:
        for row in excluded:
            out.write(json.dumps(dict(id=row['sample_id'], item_id=row['item_id'], status='inapplicable',
                                      reason=row['gravity_inapplicable_reason'], frames=0,
                                      gravity_target=row['gravity_truth']), allow_nan=False)+'\n')


def attach_requested_parameters(spec, media_rows, items, output):
    """Add enabled physical requests before hashing inference inputs."""
    enabled = set(spec.get('evaluation', {}).get('metrics', []))
    if not enabled & set(PARAMETERS):
        return media_rows
    entries = friction_inputs(spec['evaluation'].get('friction', {}), items) if 'friction' in enabled else {}
    output = Path(output)
    for row in media_rows:
        if row.get('input_failure'):
            continue
        item = items[row['item_id']]
        targets, text = {}, []
        entry = entries.get(item['id'])
        if 'velocity' in enabled:
            target = item.get('motion', {}).get('v0')
            reference = item['window']['start_frame']
            if row.get('gravity_inapplicable_reason') and entry is not None:
                try:
                    _, sliding_window = declaration(entry, item)
                    reference = sliding_window['start_frame']
                    target = entry.get('requested_initial_velocity_mps', target if reference == item['window']['start_frame'] else None)
                except (OSError, ValueError, KeyError, TypeError):
                    target = None
            if target is not None:
                vector = np.asarray(target, float)
                if vector.shape == (3,) and np.isfinite(vector).all():
                    targets['velocity_mps'] = vector.tolist()
                    targets['velocity_reference_source_frame'] = reference
                    offset = (reference-row['condition_frame_index'])/float(item['fps'])
                    text.append(f"At {offset:g} seconds after the conditioning frame, the target object's requested "
                                f"world-coordinate velocity is {vector.tolist()} m/s (speed {np.linalg.norm(vector):g} m/s).")
        if 'friction' in enabled and entry is not None:
            try:
                _, window = declaration(entry, item)
                target = entry.get('requested_effective_friction')
                if type(target) in (int, float) and math.isfinite(target) and target >= 0:
                    targets['effective_kinetic_friction'] = target
                    targets['friction_reference_source_frame'] = window['start_frame']
                    text.append(f"The requested effective kinetic friction coefficient between the target object "
                                f"and its declared supporting surface is {target:g}.")
            except (OSError, ValueError, KeyError, TypeError):
                pass  # The metric retains the detailed declaration failure.
        if not text:
            continue
        output.mkdir(exist_ok=True)
        name = hashlib.sha256(row['sample_id'].encode()).hexdigest()[:24] + '.txt'
        path = output/name
        with path.open('x') as f:
            f.write(Path(row['prompt_file']).read_text()+' '+' '.join(text))
        row.update(prompt_file=str(path.resolve()), parameter_targets=targets,
                   prompt_transformation='append_fixed_camera_and_requested_gravity_and_motion_parameters')
    return media_rows


def snapshot_inputs(spec, output):
    """Preserve exact optional measurement declarations before execution."""
    output = Path(output)
    for name in PARAMETERS:
        if name not in spec.get('evaluation', {}).get('metrics', []):
            continue
        config = spec['evaluation'].get(name, {})
        for field in ('manifest', 'response_manifest'):
            if not config.get(field):
                continue
            path = Path(config[field]).expanduser().resolve()
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != config[field+'_sha256']:
                raise ValueError(name + '_' + field + '_changed_before_execution')
            output.mkdir(exist_ok=True)
            target = output/(name+'_'+field+path.suffix)
            with target.open('xb') as f:
                f.write(raw)
