"""Local one-shot PhyEditing generation -> frozen SAM3.1 -> fixed scoring.

The CLI defaults to plan-only. No fleet, SSH, downloads or automatic retries.
"""
import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from .runners.media_contract import sha256

REPO = Path(__file__).resolve().parents[1]


def validate_settings(spec):
    """Reject misspelled settings and unavailable evaluations before any execution."""
    allowed = {'items', 'data_root', 'compact', 'model', 'model_dir', 'sam3', 'checkpoint',
               'seed', 'frames', 'fps', 'canvas', 'generation_runtime', 'generation_command',
               'mode', 'conditioning_mode', 'evaluation', 'applicability'}
    if not isinstance(spec, dict):
        raise ValueError('Run spec must be an object')
    unknown = set(spec) - allowed
    if unknown:
        raise ValueError('Unsupported spec fields: '+', '.join(sorted(unknown)))
    runtime = spec.get('generation_runtime', {})
    if not isinstance(runtime, dict):
        raise ValueError('generation_runtime must be an object')
    unknown = set(runtime) - {'python', 'gpu_devices', 'pythonpath', 'ffmpeg',
                              'code_dir', 'lora_dir', 'physalign_hook_dir'}
    if unknown:
        raise ValueError('Unsupported generation_runtime fields: '+', '.join(sorted(unknown)))
    if 'gpu_devices' in runtime and (not isinstance(runtime['gpu_devices'], str) or
                                    not runtime['gpu_devices'].strip()):
        raise ValueError('generation_runtime.gpu_devices must be a nonempty string')
    from .evaluation_settings import validate
    return validate(spec.get('evaluation', {'metrics': ['gravtrace']}))


def model_profile(spec):
    from .runners.oneclick_registry import contract
    try:
        return contract(spec['model'])
    except ValueError:
        if spec.get('generation_command'):
            return SimpleNamespace(runner='custom_argv', frames=None, fps=None,
                                   mode=spec.get('conditioning_mode', spec.get('mode', 'i2v')),
                                   canvas=None, square_canvas=None, needs=())
        raise


def resolve_model_defaults(spec):
    resolved = dict(spec)
    profile = model_profile(resolved)
    if profile.frames is not None:
        resolved.setdefault('frames', profile.frames)
        resolved.setdefault('fps', profile.fps)
    return resolved


def read_rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def write_rows(path, rows):
    with Path(path).open('x') as f:
        f.write(''.join(json.dumps(r)+'\n' for r in rows))


def execution_plan(spec):
    metrics = validate_settings(spec)
    if 'gravtrace' not in metrics:
        raise ValueError('Generation pipeline includes gravtrace; use evaluate for standalone Qwen/V/P evaluation')
    from scripts.sam31_frontend import lock
    lock()
    required = ('items', 'data_root', 'compact', 'model', 'model_dir', 'sam3', 'checkpoint')
    if any(k not in spec for k in required):
        raise ValueError('Required spec fields: '+', '.join(required))
    spec = resolve_model_defaults(spec)
    from .runners.oneclick_registry import validate_registration
    profile = model_profile(spec)
    if profile.mode not in ('i2v', 'v2v', 'v2v_one_condition_frame'):
        raise ValueError('Only I2V and V2V are allowed; pure T2V is not supported')
    for key in ('mode', 'conditioning_mode'):
        if key in spec and spec[key] != profile.mode:
            raise ValueError(f'Registered conditioning mode is {profile.mode}; requested {spec[key]}')
    if 'frames' not in spec or 'fps' not in spec:
        raise ValueError('Custom generation_command requires explicit frames and fps')
    if spec.get('generation_command') is not None and (not isinstance(spec['generation_command'], list) or
            not spec['generation_command'] or any(not isinstance(t, str) for t in spec['generation_command'])):
        raise ValueError('generation_command must be a nonempty argv list; no shell string')
    if type(spec['frames']) is not int or spec['frames'] < 1 or not math.isfinite(float(spec['fps'])) or float(spec['fps']) <= 0:
        raise ValueError('Invalid registered generation clock')
    if profile.frames is not None:
        validate_registration(spec, require_runtime=not bool(spec.get('generation_command')))
    from .pixel_metrics import settings as pixel_settings
    items = read_rows(spec['items'])
    if len({i['id'] for i in items}) != len(items):
        raise ValueError('Duplicate registered item IDs')
    from .inversion_inputs import assess
    applicability = assess(items, spec.get('applicability'), frames=spec['frames'], fps=spec['fps'])
    return dict(registered=len(items), model=spec['model'],
                model_runner='custom_argv' if spec.get('generation_command') else profile.runner,
                conditioning_mode=profile.mode,
                frames=spec['frames'], fps=spec['fps'],
                evaluation_metrics=metrics,
                vp_pixel_settings=pixel_settings(spec.get('evaluation', {}).get('vp')) if 'vp' in metrics else None,
                gpu_devices=spec.get('generation_runtime', {}).get('gpu_devices', os.environ.get('CUDA_VISIBLE_DEVICES')),
                required_generation_runtime=list(profile.needs), single_view=True, v0='agnostic', offset_mode='anchor',
                stages=['inputs', 'generation', 'initial_prompts', 'sam31', 'fixed_score']+
                       [m for m in ('vp','qwen') if m in metrics]+['summary'],
                execution_requested=False, gpu_started=False, input_items_sha256=sha256(spec['items']),
                inversion_applicability=applicability)


def diffusers_launch(spec, manifest):
    """Resolve the registered model environment without importing a model."""
    from .runners.registered_oneclick import _preflight
    python, _, env = _preflight(spec, model_profile(spec))
    command = [python, str(REPO/'physedit/runners/diffusers_i2v.py'),
               '--generation-manifest', str(manifest),
               '--model-dir', str(Path(spec['model_dir']).expanduser().resolve()),
               '--pipeline', spec['model'], '--skip-existing']
    if spec['model'] == 'hunyuan15_i2v':
        command += ['--num-inference-steps', '12', '--guidance-scale', '1.0',
                    '--offload-mode', 'sequential']
    elif spec['model'] == 'wan_ti2v5b':
        command += ['--num-inference-steps', '40', '--guidance-scale', '3.5',
                    '--offload-mode', 'model']
    return command, env


def pipeline(spec, root):
    """Explicit execution only; caller must authorize it. Existing root is rejected."""
    plan = execution_plan(spec)
    devices = spec.get('generation_runtime', {}).get('gpu_devices')
    previous = os.environ.get('CUDA_VISIBLE_DEVICES')
    if devices is not None:
        os.environ['CUDA_VISIBLE_DEVICES'] = devices
    try:
        return _pipeline(spec, root, plan)
    finally:
        if devices is not None:
            if previous is None:
                os.environ.pop('CUDA_VISIBLE_DEVICES', None)
            else:
                os.environ['CUDA_VISIBLE_DEVICES'] = previous


def _pipeline(spec, root, plan):
    from scripts import phyediting_gen as gen, sam31_frontend as frontend, phyediting_gen_summary as summary
    from .runners.media_contract import input_hashes, seal_completion, verified_completion
    spec = resolve_model_defaults(spec)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    spec = dict(spec)
    items_path = root/'items.jsonl'
    # Immutable public input registration, preserving exact bytes and all IDs.
    items_path.write_bytes(Path(spec['items']).read_bytes())
    if sha256(items_path) != plan['input_items_sha256']:
        raise ValueError('registered_items_changed_since_plan')
    (root/'registered.json').write_text(json.dumps(dict(plan=plan, spec=spec), indent=2)+'\n')
    rows = []
    try:
        input_dir = root/'input'
        gen.build(SimpleNamespace(items=str(items_path), out=str(input_dir), host_root=str(input_dir),
                                 source_root=str(Path(spec['data_root']).resolve()), data_root=spec['data_root'],
                                 per_gravity=None, min_window_frames=8, max_end_frame=170,
                                 seed=spec.get('seed', 20261008), applicability=spec.get('applicability'),
                                 generation_frames=spec['frames'], generation_fps=spec['fps']))
        rows_path = root/'rows.jsonl'
        profile = model_profile(spec)
        canvas = spec.get('canvas') or (f'{profile.canvas[0]}x{profile.canvas[1]}' if profile.canvas else None)
        gen.model_rows(SimpleNamespace(template=str(input_dir/'template.jsonl'), out=str(rows_path),
                                        model=spec['model'], frames=spec['frames'], fps=spec['fps'],
                                        out_root=str(root/'generated'), canvas=canvas, mode=profile.mode,
                                        square_canvas=None if spec.get('canvas') else profile.square_canvas))
        rows = read_rows(rows_path)
        # Obtain initial prompts BEFORE inference; missing prompt sources cannot start a model.
        initial_path = root/'initial_jobs.jsonl'
        gen.track_jobs(SimpleNamespace(items=str(items_path), rows=str(rows_path), out=str(initial_path),
                                       compact=spec['compact'], host_prefix='', local_prefix=''))
        initial = {j['id']: j for j in read_rows(initial_path)}
        for r in rows:
            r['input_failure'] = r.get('input_failure') or initial[r['sample_id']].get('input_failure')
            if (not r.get('input_failure') and r.get('source_video_sha256') and
                    sha256(r['source_video']) != r['source_video_sha256']):
                r['input_failure'] = 'source_video_changed_since_registration'
        if any(not r.get('input_failure') for r in rows):
            try:
                runtime_receipt = frontend.validate_runtime(spec['sam3'], spec['checkpoint'])
                (root/'frontend_runtime_verified.json').write_text(json.dumps(runtime_receipt)+'\n')
            except Exception as error:
                for r in rows:
                    if not r.get('input_failure'):
                        r['input_failure'] = 'frontend_runtime_failure: '+str(error)
        ready = root/'generation_rows.jsonl'
        write_rows(ready, rows)
        expected_inputs = {r['sample_id']: input_hashes(r) for r in rows if not r.get('input_failure')}
        if any(not r.get('input_failure') for r in rows):
            generation_env = None
            if spec.get('generation_command'):
                eligible_path = root/'eligible_generation_rows.jsonl'
                write_rows(eligible_path, [r for r in rows if not r.get('input_failure')])
                command = [t.format(manifest=str(eligible_path), run_dir=str(root), model_dir=spec['model_dir'])
                           for t in spec['generation_command']]
            elif profile.runner == 'diffusers':
                try:
                    command, generation_env = diffusers_launch(spec, ready)
                except Exception as error:
                    command = None
                    write_rows(root/'registered_model_status.jsonl', [
                        dict(sample_id=r['sample_id'], status='failed_before_model', reason=str(error))
                        for r in rows if not r.get('input_failure')])
            else:
                model_spec_path = root/'model_spec.json'
                model_spec_path.write_text(json.dumps(spec, indent=2)+'\n')
                command = [sys.executable, str(REPO/'physedit/runners/registered_oneclick.py'),
                           '--spec', str(model_spec_path), '--manifest', str(ready), '--run-dir', str(root)]
            if command is not None:
                with (root/'generation.log').open('x') as log:
                    result = subprocess.run(command, env=generation_env, stdout=log, stderr=subprocess.STDOUT)
                (root/'generation_exit.json').write_text(json.dumps({'returncode': result.returncode}))
        # Independently validate every completed output; failed rows stay in all later stages.
        model_status_path = root/'registered_model_status.jsonl'
        model_status = ({r['sample_id']: r for r in read_rows(model_status_path)}
                        if model_status_path.is_file() else {})
        if profile.runner == 'diffusers':
            diffusers_status_path = root / f"{spec['model']}_generation_status.jsonl"
            if diffusers_status_path.is_file():
                for status in read_rows(diffusers_status_path):
                    if status['sample_id'] not in expected_inputs:
                        continue  # Ineligible inputs keep their original input failure.
                    model_status[status['sample_id']] = status
        for r in rows:
            if not r.get('input_failure'):
                try:
                    if spec.get('generation_command'):
                        seal_completion(r, settings=dict(model=spec['model'], runner='custom_argv'),
                                        expected_inputs=expected_inputs[r['sample_id']])
                    else:
                        verified_completion(r)
                except Exception as error:
                    status = model_status.get(r['sample_id'], {})
                    detail = status.get('reason') or status.get('error') or str(error)
                    r['input_failure'] = 'generation_output_failure: '+detail
        observed_rows = root/'observed_rows.jsonl'
        write_rows(observed_rows, rows)
        jobs_path = root/'sam31_jobs.jsonl'
        frontend.generation_jobs(items_path, observed_rows, initial_path, jobs_path)
        sam_root = root/'sam31'
        frontend.prepare(jobs_path, sam_root)
        try:
            frontend.run(sam_root, spec['sam3'], spec['checkpoint'])
        except Exception as error:
            # Pre-model rejection can happen before frontend.run's internal try.
            if not (sam_root/'tracks_v4.jsonl').exists():
                frontend.measure(sam_root, pipeline_failure='frontend_failure: '+str(error))
            (root/'frontend_failure.json').write_text(json.dumps({'reason': str(error), 'partial_outputs_retained': True}))
        predictions_path = root/'predictions.jsonl'
        gen.score(SimpleNamespace(items=str(items_path), rows=str(observed_rows), tracks=str(sam_root/'tracks_v4.jsonl'),
                                  out=str(predictions_path), v0='agnostic', offset_mode='anchor', shard='0/1',
                                  camera_motion=None, scan=False))
        result = summary.report(rows, read_rows(predictions_path), {i['id']: i for i in read_rows(items_path)})
        result['evaluation_metrics'] = plan['evaluation_metrics']
        if set(plan['evaluation_metrics']) & {'vp','qwen'}:
            from .evaluations import run_additional, attach_summary
            extra=run_additional(spec,rows,{i['id']:i for i in read_rows(items_path)},initial,root/'evaluation')
            result=attach_summary(result,extra,plan['evaluation_metrics'])
        else:
            result['evaluation_failed'] = result['failed']
        (root/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        (root/'completed.json').write_text(json.dumps(dict(registered=len(rows), single_view=True,
                    evaluation_metrics=plan['evaluation_metrics'],
                    evaluation_failed=result['evaluation_failed'],
                    summary_sha256=sha256(root/'summary.json'), successful=result['scored'], failed=result['failed'],
                    completion_is_not_scientific_certification=True), indent=2)+'\n')
        return result
    except Exception as error:
        (root/'failure.json').write_text(json.dumps(dict(reason=str(error), partial_outputs_retained=True,
                                                        registered=plan['registered']), indent=2)+'\n')
        # Every original ID also gets a controller-failure reason, without deleting prior artifacts.
        write_rows(root/'controller_failures.jsonl', [dict(item_id=i['id'], reason='controller_failure: '+str(error))
                                                   for i in read_rows(items_path)])
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', required=True, help='JSON run registration, with explicit source and model paths')
    p.add_argument('--run-dir', required=True)
    p.add_argument('--execute', action='store_true', help='explicitly start generation, frontend and scoring')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)
    if args.execute and args.dry_run:
        p.error('Choose execute or dry-run')
    spec = json.loads(Path(args.spec).read_text())
    result = pipeline(spec, args.run_dir) if args.execute else execution_plan(spec)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if args.execute and result.get('evaluation_failed',result['failed']) else 0


if __name__ == '__main__':
    sys.exit(main())
