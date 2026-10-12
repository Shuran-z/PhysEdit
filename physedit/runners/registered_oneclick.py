"""One-shot local adapters for the non-Diffusers registered models.

No model is imported here. Each legacy runner is called once with an argv list;
the wrapper records immutable attempts and independently seals valid media.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .media_contract import input_hashes, seal_completion, sha256, validate_video
    from .oneclick_registry import validate_registration
except ImportError:
    from media_contract import input_hashes, seal_completion, sha256, validate_video
    from oneclick_registry import validate_registration

RUNNERS = Path(__file__).resolve().parent


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _write_rows(path, rows):
    Path(path).write_text(''.join(json.dumps(row) + '\n' for row in rows))


def _program(value):
    if Path(value).expanduser().is_file():
        # Python locates pyvenv.cfg relative to the invoked executable. Resolving
        # a venv's python symlink silently selects the base environment instead.
        return str(Path(value).expanduser().absolute())
    found = shutil.which(value)
    if found:
        return found
    raise ValueError('registered_program_unavailable: ' + value)


def _preflight(spec, profile):
    runtime = dict(spec.get('generation_runtime', {}))
    for name in profile.needs:
        runtime[name] = str(Path(runtime[name]).expanduser().resolve())
    python = _program(runtime.get('python') or sys.executable)
    model = Path(spec['model_dir']).expanduser()
    if not model.exists():
        raise ValueError('registered_model_dir_missing: ' + str(model))
    for name in profile.needs:
        if not Path(runtime[name]).expanduser().exists():
            raise ValueError('registered_runtime_path_missing: ' + name)
    if profile.runner == 'videogpa' and not (Path(runtime['code_dir'])/'wan').exists():
        raise ValueError('videogpa_code_dir_must_contain_wan')
    if profile.runner == 'physrvg' and not (Path(runtime['code_dir'])/'fastvideo').exists():
        raise ValueError('physrvg_code_dir_must_contain_fastvideo')
    if profile.runner == 'cosmos_predict2' and not (Path(runtime['code_dir'])/'run_cosmos_v2w_from_video.py').is_file():
        raise ValueError('cosmos_predict2_producer_missing')
    if spec['model'].startswith('physalign_') and not (Path(runtime['physalign_hook_dir'])/'wan22_physalign_lora.py').is_file():
        raise ValueError('physalign_merge_hook_missing')
    ffmpeg = _program(runtime.get('ffmpeg') or 'ffmpeg')
    env = os.environ.copy()
    env['PATH'] = str(Path(ffmpeg).parent) + os.pathsep + env.get('PATH', '')
    env['IMAGEIO_FFMPEG_EXE'] = ffmpeg
    if profile.runner == 'physrvg' and not shutil.which('ffprobe', path=env['PATH']):
        raise ValueError('registered_program_unavailable: ffprobe')
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    if runtime.get('gpu_devices'):
        env['CUDA_VISIBLE_DEVICES'] = runtime['gpu_devices']
    imports = [str(RUNNERS.parent.parent)]
    if runtime.get('code_dir'):
        imports.append(str(Path(runtime['code_dir']).expanduser().resolve()))
    if runtime.get('physalign_hook_dir'):
        imports.append(str(Path(runtime['physalign_hook_dir']).expanduser().resolve()))
    imports.extend(str(Path(p).expanduser().resolve()) for p in runtime.get('pythonpath', []))
    if env.get('PYTHONPATH'):
        imports.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(imports)
    return python, ffmpeg, env


def _condition_video(row, destination):
    """For V2V, expose only condition frame 23; future reference frames stay hidden."""
    import cv2
    image = cv2.imread(row['condition_image'])
    if image is None:
        raise ValueError('condition_image_decode_failure')
    h, w = image.shape[:2]
    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*'mp4v'),
                             float(row['source_sample_fps']), (w, h))
    if not writer.isOpened():
        raise ValueError('condition_video_writer_failure')
    try:
        writer.write(image)
    finally:
        writer.release()
    validate_video(destination, fps=float(row['source_sample_fps']), frames=1, width=w, height=h)


def _command(spec, profile, manifest, root, python, ffmpeg, rows):
    runtime = dict(spec.get('generation_runtime', {}))
    for key in profile.needs:
        runtime[key] = str(Path(runtime[key]).expanduser().resolve())
    model = str(Path(spec['model_dir']).expanduser().resolve())
    runner = profile.runner
    if runner == 'cosmos_predict2':
        return [[python, str(RUNNERS/'cosmos_predict2.py'), '--generation-manifest', str(manifest),
                 '--cosmos-tools', runtime['code_dir'], '--python', python, '--model-dir', model]], None
    if runner == 'dynamicrafter':
        return [[python, str(RUNNERS/'dynamicrafter.py'), '--generation-manifest', str(manifest),
                 '--repo-dir', runtime['code_dir'], '--checkpoint', model, '--startup-reserve-mib', '0']], None
    if runner == 'cosmos3':
        return [[python, str(RUNNERS/'cosmos3.py'), '--model', model, '--manifest', str(manifest),
                 '--node', 'local_oneclick', '--status-jsonl', str(root/'model_status.jsonl'),
                 '--state-json', str(root/'model_state.json'), '--ffmpeg', ffmpeg]], None
    if runner == 'wan22':
        command = [python, str(RUNNERS/'wan22_a14b.py'), '--code-dir', runtime['code_dir'],
                   '--manifest', str(manifest), '--ckpt-dir', model,
                   '--status-jsonl', str(root/'model_status.jsonl'), '--state-json', str(root/'model_state.json')]
        if spec['model'].startswith('physalign_'):
            command.extend(['--physalign-adapter-dir', runtime['lora_dir']])
        return [command], None
    if runner == 'minimax_h3':
        return [[python, str(RUNNERS/'minimax_h3.py'), '--source-manifest', str(manifest),
                 '--out-root', str(root/'minimax_runtime'), '--model', model]], None
    if runner == 'physrvg':
        commands = []
        for width, height in sorted({(int(r['gen_width']), int(r['gen_height'])) for r in rows}):
            subset = root/f'physrvg_{width}x{height}.jsonl'
            _write_rows(subset, [r for r in rows if (r['gen_width'], r['gen_height']) == (width, height)])
            commands.append([python, str(RUNNERS/'physrvg.py'), '--manifest', str(subset),
                             '--model-id', model, '--lora-checkpoint', runtime['lora_dir'],
                             '--output-root', str(root), '--status-jsonl', str(root/f'physrvg_{width}x{height}_status.jsonl'),
                             '--height', str(height), '--width', str(width), '--num-frames', '49', '--fps', '15',
                             '--condition-policy', 'static_frame', '--startup-reserve-mib', '0'])
        return commands, None
    if runner == 'videogpa':
        prompts = root/'videogpa_prompts.json'
        prompts.write_text(json.dumps({r['sample_id']: dict(text_prompt=Path(r['prompt_file']).read_text().strip(),
                                                       image_prompt=r['condition_image'], seed=r['seed']) for r in rows}))
        raw = root/'videogpa_raw'
        command = [python, str(RUNNERS/'videogpa_wan22.py'), '--model_path', model,
                   '--prompt_json', str(prompts), '--output_dir', str(raw),
                   '--lora_path', runtime['lora_dir'], '--lora_weight', '0.2', '--gpu_id', '0',
                   '--frame_num', '49', '--sampling_steps', '20', '--fps', '15', '--max_area', '399360', '--offload_model']
        return [command], raw
    raise ValueError('No one-click adapter for ' + spec['model'])


def _finish_videogpa(rows, raw_dir, ffmpeg):
    for row in rows:
        source = raw_dir/row['sample_id']/f"seed_{row['seed']}.mp4"
        if not source.is_file():
            continue
        raw = Path(row['generated_video'])
        resized = Path(row['generated_video_resized_to_source'])
        if raw.exists() or resized.exists():
            raise ValueError('existing_output_retained_no_overwrite: ' + row['sample_id'])
        raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, raw)
        partial = resized.with_name(resized.stem + '.partial.mp4')
        subprocess.run([ffmpeg, '-n', '-v', 'error', '-i', str(raw), '-vf',
                        f"scale={row['source_width']}:{row['source_height']}:flags=lanczos",
                        '-r', str(row['output_fps']), '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(partial)],
                       check=True)
        validate_video(partial, fps=row['output_fps'], frames=row['num_frames'],
                       width=row['source_width'], height=row['source_height'])
        os.replace(partial, resized)


def run(spec, manifest, root):
    profile = validate_registration(spec)
    root = Path(root)
    rows = _rows(manifest)
    if not rows:
        return 0
    try:
        python, ffmpeg, env = _preflight(spec, profile)
    except Exception as error:
        with (root/'registered_model_status.jsonl').open('x') as handle:
            for row in rows:
                handle.write(json.dumps(dict(sample_id=row['sample_id'], status='failed_before_model',
                                             reason=str(error)))+'\n')
        return 1
    selected = []
    expected = {}
    status = root/'registered_model_status.jsonl'
    with status.open('x') as handle:
        for row in rows:
            sid = row['sample_id']
            try:
                if row.get('input_failure'):
                    raise ValueError('input_failure_row_not_eligible')
                if row.get('mode', profile.mode) != profile.mode:
                    raise ValueError('registered_conditioning_mode_mismatch')
                if row.get('source_video_sha256') and sha256(row['source_video']) != row['source_video_sha256']:
                    raise ValueError('source_video_changed_since_registration')
                output = Path(row['generated_video_resized_to_source'])
                out_dir = Path(row['out_dir'])
                out_dir.mkdir(parents=True, exist_ok=True)
                if output.exists() or Path(row['generated_video']).exists() or list(out_dir.glob('*.partial.mp4')):
                    raise ValueError('existing_output_or_partial_retained_no_retry')
                claim = out_dir/'generation.claim'
                with claim.open('x') as claimed:
                    claimed.write(json.dumps(dict(sample_id=sid, model=spec['model'], registered_row_sha256=sha256(manifest))))
                expected[sid] = input_hashes(row)
                if profile.runner == 'cosmos_predict2':
                    clip = out_dir/'condition_only.mp4'
                    _condition_video(row, clip)
                    row = {**row, 'conditioning_video': str(clip), 'cosmos_predict2_condition_frames': 1,
                           'cosmos_output_fps': row['output_fps']}
                selected.append(row)
            except Exception as error:
                handle.write(json.dumps(dict(sample_id=sid, status='failed_before_model', reason=str(error)))+'\n')
        handle.flush()
    if not selected:
        return 1
    staged = root/'model_eligible.jsonl'
    _write_rows(staged, selected)
    commands, raw_dir = _command(spec, profile, staged, root, python, ffmpeg, selected)
    codes = []
    for index, command in enumerate(commands):
        with (root/f'model_call_{index}.log').open('x') as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        codes.append(result.returncode)
    if raw_dir is not None:
        try:
            _finish_videogpa(selected, raw_dir, ffmpeg)
        except Exception as error:
            (root/'videogpa_finalize_failure.json').write_text(json.dumps({'reason': str(error)}))
            codes.append(1)
    original = {r['sample_id']: r for r in rows}
    failed = len(rows) - len(selected)
    with status.open('a') as handle:
        for row in selected:
            sid = row['sample_id']
            try:
                seal_completion(original[sid], settings=dict(model=spec['model'], runner=profile.runner,
                                model_dir=spec['model_dir'], runtime=spec.get('generation_runtime', {})),
                                expected_inputs=expected[sid])
                state, reason = 'complete', None
            except Exception as error:
                failed += 1
                state, reason = 'generation_output_failure', str(error)
            handle.write(json.dumps(dict(sample_id=sid, status=state, reason=reason))+'\n')
    return 1 if failed or any(codes) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args(argv)
    spec = json.loads(Path(args.spec).read_text())
    return run(spec, args.manifest, args.run_dir)


if __name__ == '__main__':
    sys.exit(main())
