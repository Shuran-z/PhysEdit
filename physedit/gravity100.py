"""Frame-zero generation and conditional gravity evaluation for the fixed 100 tasks."""
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .runners.media_contract import sha256

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / 'docs/phyediting/gravity100.csv'
if not MANIFEST.is_file():
    MANIFEST = Path(sys.prefix) / 'share/physedit/gravity100.csv'
MANIFEST_SHA256 = '8a0106b377fc66a6fd4e34d9996d202841a0e64b020a8586b7f2f7777769894f'


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def write_rows(path, values):
    with Path(path).open('x') as f:
        for value in values:
            f.write(json.dumps(value, allow_nan=False) + '\n')


def gpu_sharing_policy(spec):
    policy = spec.get('generation_runtime', {}).get('gpu_sharing')
    if policy is None:
        return None
    fields = {'allowed_gpu_uuids', 'minimum_free_mib', 'maximum_utilization_percent'}
    if not isinstance(policy, dict) or set(policy) != fields:
        raise ValueError('gpu_sharing_requires_device_allowlist_and_resource_limits')
    uuids = policy['allowed_gpu_uuids']
    if (not isinstance(uuids, list) or not uuids or
            any(not isinstance(x, str) or not x.startswith('GPU-') for x in uuids) or
            type(policy['minimum_free_mib']) is not int or policy['minimum_free_mib'] < 1024 or
            type(policy['maximum_utilization_percent']) is not int or
            not 0 <= policy['maximum_utilization_percent'] <= 100):
        raise ValueError('invalid_gpu_sharing_device_or_resource_limits')
    return policy


def require_idle_gpu(spec):
    """Check exclusive access by default, or explicitly selected shared devices."""
    sharing = gpu_sharing_policy(spec)
    devices = spec.get('generation_runtime', {}).get('gpu_devices')
    if not devices or not isinstance(devices, str):
        raise ValueError('explicit_generation_runtime_gpu_devices_required')
    for device in devices.split(','):
        selected = device.strip()
        queries = [
            ['nvidia-smi', '-i', selected, '--query-gpu=uuid,memory.used,utilization.gpu',
             '--format=csv,noheader,nounits'],
            ['nvidia-smi', '-i', selected, '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'],
        ]
        outputs = []
        for query in queries:
            p = subprocess.run(query, capture_output=True, text=True, timeout=15, check=True)
            outputs.append(p.stdout.strip())
        gpu = outputs[0].split(',')
        if len(gpu) != 3:
            raise RuntimeError('gpu_deferred_invalid_resource_readback: ' + selected)
        if sharing:
            if gpu[0].strip() not in sharing['allowed_gpu_uuids']:
                raise ValueError('gpu_sharing_device_not_authorized: ' + selected)
            free = subprocess.run(['nvidia-smi', '-i', selected, '--query-gpu=memory.free',
                                   '--format=csv,noheader,nounits'], capture_output=True,
                                  text=True, timeout=15, check=True)
            if (float(free.stdout.strip()) < sharing['minimum_free_mib'] or
                    float(gpu[2]) > sharing['maximum_utilization_percent']):
                raise RuntimeError('gpu_deferred_shared_resource_limit: ' + selected)
        elif outputs[1] or float(gpu[1]) > 128 or float(gpu[2]) != 0:
            raise RuntimeError('gpu_deferred_not_fully_idle: ' + selected)


def prepare_main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Prepare the fixed condition-frame gravity100 run; CPU only.')
    parser.add_argument('tasks', help='Registered portable tasks.jsonl')
    parser.add_argument('--model-config', required=True)
    parser.add_argument('--manifest', default=str(MANIFEST))
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    spec = json.loads(Path(args.model_config).read_text())
    allowed = {'model', 'model_dir', 'sam3', 'checkpoint', 'generation_runtime', 'generation_command',
               'frames', 'fps', 'seed', 'evaluation', 'native_runtime'}
    if set(spec) - allowed:
        raise ValueError('unsupported_model_config_fields')
    spec.update(protocol='gravity100', gravity100=dict(
        tasks=str(Path(args.tasks).resolve()), tasks_sha256=sha256(args.tasks),
        manifest=str(Path(args.manifest).resolve()), manifest_sha256=sha256(args.manifest)))
    plan = execution_plan(spec)
    with Path(args.out).open('x') as f:
        json.dump(spec, f, indent=2)
        f.write('\n')
    print(json.dumps({k: plan[k] for k in ('registered', 'input_ready', 'native_time_grid_ready',
                                          'conditioning_frame', 'gpu_started')}))
    return 0


def read_inputs(spec):
    from .conditioned_measurement import descriptor
    settings = spec['gravity100']
    if set(settings) != {'tasks', 'tasks_sha256', 'manifest', 'manifest_sha256'}:
        raise ValueError('gravity100 requires tasks, manifest and both SHA256 locks')
    manifest = Path(settings['manifest'])
    if sha256(manifest) != settings['manifest_sha256'] or settings['manifest_sha256'] != MANIFEST_SHA256:
        raise ValueError('fixed_gravity100_manifest_changed')
    members = list(csv.DictReader(manifest.open()))
    path = Path(settings['tasks'])
    if sha256(path) != settings['tasks_sha256']:
        raise ValueError('gravity100_tasks_changed')
    tasks = read_rows(path)
    for task in tasks:
        for key in ('conditioning_image', 'reference_video', 'estimator', 'generation_prompt'):
            if not Path(task[key]).is_absolute():
                task[key] = str((path.parent / task[key]).resolve())
    if len(tasks) != 100 or len({t['id'] for t in tasks}) != 100:
        raise ValueError('gravity100_requires_all_100_unique_members')
    by_id = {t['id']: t for t in tasks}
    if set(by_id) != {r['id'] for r in members}:
        raise ValueError('gravity100_member_identity_mismatch')
    for row in members:
        t = by_id[row['id']]
        n = int(row['evaluation_frame_count'])
        times = t['physical_times_s']
        if (type(t['conditioning_frame']) is not int or type(t['evaluation_start_frame']) is not int
                or t['conditioning_frame'] != 0 or t['evaluation_start_frame'] != 0
                or len(times) != n or times[0] != 0
                or any(not math.isfinite(v) for v in times)
                or any(b <= a for a, b in zip(times, times[1:]))):
            raise ValueError('gravity100_condition_or_physics_clock_changed: ' + t['id'])
        roles = t.get('measurement_roles', [t['target_name']])
        if not roles or not set(roles) <= set(t['initial_objects']):
            raise ValueError('missing_condition_target_prompt: ' + t['id'])
        for key, digest in [('conditioning_image', 'conditioning_image_sha256'),
                            ('reference_video', 'reference_video_sha256')]:
            if sha256(t[key]) != row[digest]:
                raise ValueError('gravity100_asset_changed: ' + t['id'] + ':' + key)
        d, _, _ = descriptor(t)
        if d['registered_physical_times_s'] != times:
            raise ValueError('registered_estimator_clock_mismatch: ' + t['id'])
        if not Path(t['generation_prompt']).is_file():
            raise ValueError('missing_registered_continuation_prompt: ' + t['id'])
        if sha256(t['generation_prompt']) != t['generation_prompt_sha256']:
            raise ValueError('registered_continuation_prompt_changed: ' + t['id'])
    return members, by_id


def observation_clock(member, task, fps, frames, native_runtime=None):
    from .conditioned_measurement import descriptor, minimum_observations, native_control_clock
    duration = (int(member['evaluation_frame_count']) - 1) / float(member['media_fps'])
    scheduled = [f for f in range(frames) if f / fps <= duration + 1e-9]
    scale = task['physical_times_s'][-1] / duration
    times = [f / fps * scale for f in scheduled]
    d, known, _ = descriptor(task)
    reason = None
    if (frames - 1) / fps + 1e-9 < duration:
        reason = 'generation_duration_shorter_than_fixed_scope'
    elif len(scheduled) < minimum_observations(d):
        reason = 'native_frames_within_fixed_horizon_below_model_minimum'
    elif d['kind'] == 'native_physx' and native_runtime is None:
        reason = 'native_CPU_forward_runtime_not_configured'
    elif d.get('module') == 'foreground_safe_control_RGB' and len(times) != 4:
        reason = 'registered_four_observation_model'
    elif len(times) >= 2:
        reason = native_control_clock(d, known, times)
    return dict(generated_frames=scheduled, physical_times_s=times, media_horizon_s=duration,
                physical_horizon_s=task['physical_times_s'][-1], physics_seconds_per_media_second=scale,
                applicable=reason is None, reason=reason)


def execution_plan(spec):
    from . import phyediting as legacy
    from .runners.oneclick_registry import validate_registration
    from .evaluation_settings import validate
    metrics = validate(spec.get('evaluation', {'metrics': ['gravtrace']}))
    gpu_sharing_policy(spec)
    if 'gravtrace' not in metrics or set(metrics) - {'gravtrace', 'vp', 'qwen'}:
        raise ValueError('gravity100 supports gravity, VP and Qwen; motion parameters use their own tasks')
    if spec.get('protocol') != 'gravity100':
        raise ValueError('explicit_gravity100_protocol_required')
    native = spec.get('native_runtime')
    if native is not None and (not isinstance(native, dict) or set(native) != {'command'} or
            not isinstance(native['command'], list) or not native['command'] or
            any(not isinstance(x, str) for x in native['command'])):
        raise ValueError('native_runtime_requires_command_argv')
    spec = legacy.resolve_model_defaults(spec)
    profile = legacy.model_profile(spec)
    if profile.mode not in ('i2v', 'v2v_one_condition_frame'):
        raise ValueError('gravity100 uses exactly one condition frame; no future reference prefix')
    if profile.frames is not None:
        validate_registration(spec, require_runtime=not bool(spec.get('generation_command')))
    if spec.get('generation_command') is not None and (
            not isinstance(spec['generation_command'], list) or not spec['generation_command'] or
            any(not isinstance(x, str) for x in spec['generation_command'])):
        raise ValueError('generation_command must be an argv list')
    if not isinstance(spec.get('frames'), int) or spec['frames'] < 2 or float(spec.get('fps', 0)) <= 0:
        raise ValueError('invalid_generation_clock')
    members, tasks = read_inputs(spec)
    clocks = {r['id']: observation_clock(r, tasks[r['id']], float(spec['fps']), spec['frames'],
                                       spec.get('native_runtime')) for r in members}
    return dict(protocol='gravity100', registered=100, model=spec['model'], conditioning_frame=0,
                evaluation_start_frame=0, single_view=True, input_ready=100,
                group_counts=dict(Counter(r['split'] for r in members)),
                frames=spec['frames'], fps=float(spec['fps']), native_output_frames=spec['frames'],
                condition_only=True, reference_result_reuse=False, evaluation_metrics=metrics,
                native_time_grid_ready=sum(c['applicable'] for c in clocks.values()),
                temporal_limitations={k: v['reason'] for k, v in clocks.items() if not v['applicable']},
                observation_clocks=clocks, source_manifest_sha256=spec['gravity100']['manifest_sha256'],
                tasks_sha256=spec['gravity100']['tasks_sha256'], execution_requested=False, gpu_started=False,
                stages=['inputs', 'generation', 'sam31', 'conditional_gravity',
                        *[x for x in ('vp', 'qwen') if x in metrics], 'summary'])


def build_inputs(spec, root):
    """Materialize current conditions only; no old frame-23 builder is called."""
    from . import phyediting as legacy
    spec = legacy.resolve_model_defaults(spec)
    plan = execution_plan(spec)
    members, tasks = read_inputs(spec)
    profile = legacy.model_profile(spec)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    items = []
    for member in members:
        task = tasks[member['id']]
        sid = hashlib.sha256(member['id'].encode()).hexdigest()[:24]
        dest = root / 'input' / sid
        dest.mkdir(parents=True)
        shutil.copyfile(task['conditioning_image'], dest / 'conditioning.png')
        shutil.copyfile(task['generation_prompt'], dest / 'prompt.txt')
        (dest / 'negative.txt').write_text('camera motion, cuts, distorted objects, watermark\n')
        w, h = task['image_size']
        canvas = profile.canvas or (704, 480)
        out = root / 'generated' / spec['model'] / sid
        clock = plan['observation_clocks'][member['id']]
        row = dict(index=len(rows), sample_id=sid, source_sample_id=sid, item_id=member['id'],
                   model_name=spec['model'], pipeline=spec['model'], mode=profile.mode,
                   benchmark='gravity100', scenario='conditional', protocol='gravity100',
                   condition_image=str((dest / 'conditioning.png').resolve()), condition_frames=1,
                   condition_frame_index=0, condition_time_ms=0.,
                   prompt_file=str((dest / 'prompt.txt').resolve()),
                   negative_prompt_file=str((dest / 'negative.txt').resolve()),
                   prompt_source_class=task['prompt_source'], prompt_is_exact_official=False,
                   source_video=task['reference_video'], source_video_sha256=member['reference_video_sha256'],
                   source_width=w, source_height=h, source_sample_fps=30., source_native_fps=30.,
                   source_orientation='landscape' if w >= h else 'portrait',
                   aspect_ratio='16:9' if w >= h else '9:16',
                   gen_width=canvas[0] if w >= h else canvas[1],
                   gen_height=canvas[1] if w >= h else canvas[0],
                   num_frames=spec['frames'], output_fps=float(spec['fps']), seed=spec.get('seed', 20261008),
                   out_dir=str(out.resolve()), generated_video=str((out / 'raw.mp4').resolve()),
                   generated_video_resized_to_source=str((out / 'resized.mp4').resolve()),
                   input_failure=None, gravity_truth=float(member['reference_gravity_m_s2']),
                   split=member['split'], event=member['event'], camera_id=member['camera'],
                   evaluation_horizon_seconds=clock['media_horizon_s'],
                   observation_clock=clock)
        rows.append(row)
        items.append(dict(id=member['id'], event=member['event'], split=member['split'],
                          camera_id=member['camera'], gravity=float(member['reference_gravity_m_s2']),
                          video=task['reference_video'], fps=30., image_size=[w, h], object_name=task['target_name'],
                          window=dict(start_frame=0, max_frames=int(member['evaluation_frame_count']))))
    write_rows(root / 'generation_rows.jsonl', rows)
    write_rows(root / 'items.jsonl', items)
    (root / 'registered.json').write_text(json.dumps(dict(plan=plan, spec=spec), indent=2))
    return plan, rows, tasks, items


def tracking_jobs(rows, tasks):
    jobs = []
    for row in rows:
        t = tasks[row['item_id']]
        c = row['observation_clock']
        path = Path(row['generated_video_resized_to_source'])
        for role in t['initial_objects']:
            jobs.append(dict(id=row['sample_id'] + '_' + role, video=str(path),
                             video_sha256=sha256(path) if path.is_file() else None,
                             frames=c['generated_frames'], prompt_frame=0, scene_boxes=t['initial_objects'],
                             target_name=role, fps=row['output_fps'],
                             input_failure=row.get('input_failure') or c['reason']))
    return jobs


def summarize(rows, predictions):
    by_id = {p['id']: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {r['sample_id'] for r in rows}:
        raise ValueError('gravity100_prediction_denominator_changed')
    def group(selected):
        errors, failures, numerical = [], [], 0
        for row in selected:
            p = by_id[row['sample_id']]
            g = p.get('gravity')
            finite = type(g) in (float, int) and math.isfinite(g) and g > 0
            numerical += finite
            if finite and p.get('status') == 'ok' and not row.get('input_failure'):
                errors.append(100 * abs(g / row['gravity_truth'] - 1))
            else:
                failures.append(dict(id=row['item_id'], item_id=row['item_id'], sample_id=row['sample_id'],
                                     status=p.get('status'),
                                     reason=row.get('input_failure') or p.get('reason') or p.get('status')))
        n = len(selected)
        return dict(registered=n, scored=len(errors), failed=n-len(errors),
                    mean_error_percent=sum(errors)/len(errors) if errors else None,
                    max_error_percent=max(errors) if errors else None,
                    failure_rate_percent=100*(n-len(errors))/n if n else None,
                    numeric_output_coverage_percent=100*numerical/n if n else None,
                    coverage_percent=100*len(errors)/n if n else None, failures=failures)
    result = group(rows)
    result['groups'] = {k: group([r for r in rows if r['split'] == k]) for k in ('ID', 'OOD-1', 'OOD-2')}
    result.update(protocol='gravity100', conditioning_frame=0, single_view=True,
                  error_interpretation='deviation_from_requested_gravity', reference_result_reuse=False)
    return result


def score_generated(rows, tasks, sam_root, output, native_runtime=None):
    from .conditioned_measurement import measure
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tracks_path = Path(sam_root) / 'tracks_v4.jsonl'
    track_rows = read_rows(tracks_path) if tracks_path.exists() else []
    tracks = {r['id']: r for r in track_rows}
    if len(tracks) != len(track_rows):
        raise ValueError('duplicate_generated_observation_ids')
    predictions = []
    for row in rows:
        task = tasks[row['item_id']]
        clock = row['observation_clock']
        reason = row.get('input_failure') or clock['reason']
        try:
            if reason:
                status = ('input_failure' if row.get('input_failure') else
                          'runtime_unavailable' if reason == 'native_CPU_forward_runtime_not_configured' else
                          'insufficient_temporal_evidence')
                p = dict(status=status,
                         gravity=None, reason=reason)
            else:
                masks = {}
                for role in task['initial_objects']:
                    job_id = row['sample_id'] + '_' + role
                    observed = tracks.get(job_id, {})
                    track = observed.get('tracks', {}).get(role, {})
                    required_role = role in task.get('measurement_roles', [task['target_name']])
                    if (track.get('frames') != clock['generated_frames'] or
                            len(track.get('xyxy', [])) != len(clock['generated_frames']) or
                            (required_role and any(box is None for box in track.get('xyxy', []))) or
                            observed.get('video_sha256') != sha256(row['generated_video_resized_to_source'])):
                        raise ValueError('incomplete_or_unbound_generated_tracking: ' + role)
                    stem = hashlib.sha256((row['sample_id'] + '_' + role).encode()).hexdigest()[:12]
                    masks[role] = [str(Path(sam_root) / 'runs/sam31_visible_projection_full30_masks' /
                                       (stem + '_' + str(frame) + '.npz')) if box is not None else None
                                   for frame, box in zip(clock['generated_frames'], track['xyxy'])]
                p = measure(task, row['generated_video_resized_to_source'], clock['generated_frames'],
                            clock['physical_times_s'], masks, output / row['sample_id'],
                            **({'native_runtime': native_runtime} if native_runtime else {}))
        except Exception as error:
            p = dict(status='measurement_failure', gravity=None, reason=type(error).__name__ + ': ' + str(error))
        predictions.append(dict(p, id=row['sample_id'], item_id=row['item_id']))
    write_rows(output / 'predictions.jsonl', predictions)
    return predictions


def pipeline(spec, root):
    from . import phyediting as legacy
    from .runners.media_contract import input_hashes, seal_completion, verified_completion
    from scripts import sam31_frontend as frontend
    spec = legacy.resolve_model_defaults(spec)
    root = Path(root).resolve()
    plan, rows, tasks, items = build_inputs(spec, root)
    profile = legacy.model_profile(spec)
    hashes = {r['sample_id']: input_hashes(r) for r in rows}
    try:
        if profile.runner != 'custom_argv':
            require_idle_gpu(spec)
        frontend.validate_runtime(spec['sam3'], spec['checkpoint'])
        env = None
        if spec.get('generation_command'):
            command = [v.format(manifest=str(root / 'generation_rows.jsonl'), run_dir=str(root),
                                model_dir=spec['model_dir']) for v in spec['generation_command']]
        elif profile.runner == 'diffusers':
            command, env = legacy.diffusers_launch(spec, root / 'generation_rows.jsonl')
        else:
            (root / 'model_spec.json').write_text(json.dumps(spec))
            command = [sys.executable, str(REPO / 'physedit/runners/registered_oneclick.py'),
                       '--spec', str(root / 'model_spec.json'), '--manifest', str(root / 'generation_rows.jsonl'),
                       '--run-dir', str(root)]
        with (root / 'generation.log').open('x') as log:
            process = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        (root / 'generation_exit.json').write_text(json.dumps(dict(returncode=process.returncode)))
    except RuntimeError as error:
        if str(error).startswith('gpu_deferred_'):
            (root / 'deferred.json').write_text(json.dumps(dict(reason=str(error), generation_started=False)))
            raise
        for row in rows:
            row['input_failure'] = 'generation_launch_failure: ' + str(error)
    except Exception as error:
        for row in rows:
            row['input_failure'] = 'generation_launch_failure: ' + str(error)
    for row in rows:
        if row.get('input_failure'):
            continue
        try:
            if spec.get('generation_command'):
                seal_completion(row, settings={'protocol': 'gravity100'}, expected_inputs=hashes[row['sample_id']])
            else:
                verified_completion(row)
        except Exception as error:
            row['input_failure'] = 'generation_output_failure: ' + str(error)
    write_rows(root / 'observed_rows.jsonl', rows)
    jobs = tracking_jobs(rows, tasks)
    write_rows(root / 'sam31_jobs.jsonl', jobs)
    frontend.prepare(root / 'sam31_jobs.jsonl', root / 'sam31')
    try:
        if profile.runner != 'custom_argv' and any(not j['input_failure'] for j in jobs):
            require_idle_gpu(spec)
        previous = os.environ.get('CUDA_VISIBLE_DEVICES')
        devices = spec.get('generation_runtime', {}).get('gpu_devices')
        if devices:
            os.environ['CUDA_VISIBLE_DEVICES'] = devices
        try:
            frontend.run(root / 'sam31', spec['sam3'], spec['checkpoint'])
        finally:
            if devices and previous is None:
                os.environ.pop('CUDA_VISIBLE_DEVICES', None)
            elif previous is not None:
                os.environ['CUDA_VISIBLE_DEVICES'] = previous
    except RuntimeError as error:
        if str(error).startswith('gpu_deferred_'):
            (root / 'deferred.json').write_text(json.dumps(dict(reason=str(error), generation_complete=True,
                                                               tracking_started=False)))
            raise
        (root / 'frontend_failure.json').write_text(json.dumps(dict(reason=str(error), partial_outputs_retained=True)))
    except Exception as error:
        (root / 'frontend_failure.json').write_text(json.dumps(dict(reason=str(error), partial_outputs_retained=True)))
    predictions = score_generated(rows, tasks, root / 'sam31', root / 'conditional_gravity', spec.get('native_runtime'))
    result = summarize(rows, predictions)
    result['evaluation_metrics'] = plan['evaluation_metrics']
    if set(plan['evaluation_metrics']) & {'vp', 'qwen'}:
        from .evaluations import run_additional, attach_summary
        initial = {r['sample_id']: dict(objects=tasks[r['item_id']]['initial_objects'], prompt_frame=0,
                   input_failure=None if tasks[r['item_id']]['target_name'] in tasks[r['item_id']]['initial_objects']
                   else 'registered_multi_instance_VP_masks_required')
                   for r in rows}
        extra = run_additional(spec, rows, {i['id']: i for i in items}, initial,
                               root / 'evaluation', gravity_predictions=predictions,
                               tracking_root=root / 'sam31')
        result = attach_summary(result, extra, plan['evaluation_metrics'])
    else:
        result['evaluation_failed'] = result['failed']
    (root / 'summary.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
    (root / 'completed.json').write_text(json.dumps(dict(protocol='gravity100', registered=100,
        successful=result['scored'], failed=result['failed'], summary_sha256=sha256(root / 'summary.json'),
        predictions_sha256=sha256(root / 'conditional_gravity/predictions.jsonl'))))
    return result


def existing_run(spec, run_dir, output_dir, execute=False):
    """Reuse this run's measured generated-video predictions; never a reference prediction."""
    plan = execution_plan(spec)
    run = Path(run_dir)
    registered = json.loads((run / 'registered.json').read_text())
    prior = registered['plan']
    for key in ('protocol', 'source_manifest_sha256', 'tasks_sha256', 'model', 'frames', 'fps'):
        if prior[key] != plan[key]:
            raise ValueError('registered_gravity100_run_changed: ' + key)
    predictions_path = run / 'conditional_gravity/predictions.jsonl'
    completed = json.loads((run / 'completed.json').read_text())
    if sha256(predictions_path) != completed['predictions_sha256']:
        raise ValueError('generated_prediction_archive_changed')
    rows = read_rows(run / 'observed_rows.jsonl')
    from .runners.media_contract import verified_completion
    for row in rows:
        if not row.get('input_failure'):
            verified_completion(row)
    if not execute:
        return dict(protocol='gravity100', registered=100, generation_started=False,
                    tracking_started=False, gravity_refit=False, execution_requested=False)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False)
    result = summarize(rows, read_rows(predictions_path))
    if set(plan['evaluation_metrics']) & {'vp', 'qwen'}:
        from .evaluations import run_additional, attach_summary
        _, tasks = read_inputs(spec)
        initial = {r['sample_id']: dict(objects=tasks[r['item_id']]['initial_objects'], prompt_frame=0,
                   input_failure=None if tasks[r['item_id']]['target_name'] in tasks[r['item_id']]['initial_objects']
                   else 'registered_multi_instance_VP_masks_required')
                   for r in rows}
        items = {i['id']: i for i in read_rows(run / 'items.jsonl')}
        extra = run_additional(spec, rows, items, initial, root / 'evaluation',
                               gravity_predictions=read_rows(predictions_path), tracking_root=run / 'sam31')
        result = attach_summary(result, extra, plan['evaluation_metrics'])
    else:
        result['evaluation_failed'] = result['failed']
    (root / 'summary.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
    return result
