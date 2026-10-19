"""Portable entry for the frozen single-view SAM3.1 + RGB + V4 frontend.

Preparation and export do not import torch or run a fitter. GPU inference is
an explicit, one-shot `run`; existing partial outputs are never overwritten.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FROZEN = Path(__file__).resolve().parent/'sam31_frozen'
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sam31_prompts import point
from physedit.runners.media_contract import validate_video


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path, rows):
    Path(path).write_text(''.join(json.dumps(row)+'\n' for row in rows))


def lock():
    manifest = json.loads((FROZEN/'manifest.json').read_text())
    for name, expected in manifest['sources'].items():
        if sha(FROZEN/name) != expected:
            raise ValueError('Frozen frontend source drift: '+name)
    for name, expected in manifest['core_sources'].items():
        if sha(REPO/name) != expected:
            raise ValueError('Frozen core source drift: '+name)
    return manifest


def identity_prompts(boxes, target):
    positive, rule = point(boxes[target], [b for n, b in boxes.items() if n != target])
    prompts = [dict(xy=positive, label=1, source=target, rule=rule)]
    b = boxes[target]
    area = (b[2]-b[0])*(b[3]-b[1])
    for name, b in boxes.items():
        if name == target:
            continue
        negative, rule = point(b, [v for n, v in boxes.items() if n != name])
        if (b[2]-b[0])*(b[3]-b[1]) < area:
            negative = [round((b[0]+b[2])/2), round((b[1]+b[3])/2)]
            rule = 'smaller_other_object_box_centre'
        if math.dist(positive, negative) > 3:
            prompts.append(dict(xy=negative, label=0, source=name, rule=rule))
    return prompts


FIELDS = {'id', 'video', 'video_sha256', 'frames', 'prompt_frame', 'scene_boxes',
          'target_name', 'fps', 'input_failure'}


def validate_job(row):
    if set(row)-FIELDS:
        raise ValueError('Unexpected fields (no truth/per-frame reference prompts): '+str(set(row)-FIELDS))
    j = dict(row)
    if not isinstance(j['id'], str) or not j['id'] or not isinstance(j['target_name'], str):
        raise ValueError('String case and target IDs required')
    frames = j['frames']
    if not isinstance(frames, list) or any(type(f) is not int or f < 0 for f in frames):
        raise ValueError('Nonnegative integer frames required')
    if frames != sorted(set(frames)):
        raise ValueError('Frames must be unique and ordered')
    if type(j['prompt_frame']) is not int or j['prompt_frame'] < 0 or (frames and j['prompt_frame'] > frames[0]):
        raise ValueError('Prompt must precede the fixed window')
    if not math.isfinite(j['fps']) or j['fps'] <= 0:
        raise ValueError('Positive finite fps required')
    boxes = j['scene_boxes']
    if not j.get('input_failure') and j['target_name'] not in boxes:
        raise ValueError('Declared initial target box missing')
    for b in boxes.values():
        if len(b) != 4 or not all(math.isfinite(v) for v in b) or b[2] <= b[0] or b[3] <= b[1]:
            raise ValueError('Invalid declared initial box')
    j['video'] = str(Path(j['video']).resolve())
    if j.get('input_failure'):
        reason = j['input_failure']
    elif not Path(j['video']).is_file():
        reason = 'missing_source_video'
    elif not j.get('video_sha256') or sha(j['video']) != j['video_sha256']:
        reason = 'video_sha256_mismatch'
    elif not frames:
        reason = 'empty_registered_window'
    else:
        import cv2
        try:
            media = validate_video(j['video'], fps=j['fps'])
            if max(frames + [j['prompt_frame']]) >= media['frames']:
                raise ValueError('registered_frame_outside_video')
        except (OSError, ValueError, cv2.error) as error:
            j['input_failure'] = str(error)
            return validate_job(j)
        cap = cv2.VideoCapture(j['video'])
        cap.set(cv2.CAP_PROP_POS_FRAMES, j['prompt_frame'])
        ok, image = cap.read()
        cap.release()
        if not ok:
            reason = 'initial_rgb_read_failure'
        else:
            j['initial_box'] = boxes[j['target_name']]
            j['semantic_point_prompts'] = identity_prompts(boxes, j['target_name'])
            h, w = image.shape[:2]
            if any(not (0 <= q['xy'][0] < w and 0 <= q['xy'][1] < h) for q in j['semantic_point_prompts']):
                reason = 'initial_identity_point_outside_image'
            else:
                reason = None
    # Whole rows stay in the original denominator, including input failures.
    j['input_failure'] = j.get('input_failure') or reason
    j['boxes'] = [j.get('initial_box')]*len(frames)
    return j


def prepare(jobs_path, root):
    manifest = lock()
    original = read_rows(jobs_path)
    if len({j['id'] for j in original}) != len(original):
        raise ValueError('Duplicate case IDs')
    jobs = [validate_job(j) for j in original]
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root/'runs').mkdir()
    for name in manifest['sources']:
        shutil.copyfile(FROZEN/name, root/name)
    shutil.copyfile(Path(__file__).with_name('sam31_scope.py'), root/'sam31_scope.py')
    write_rows(root/'all_jobs.jsonl', jobs)
    valid = [j for j in jobs if not j['input_failure']]
    shards = [valid[::2], valid[1::2]]
    for w, shard in enumerate(shards):
        write_rows(root/f'sam31_identity_full30_w{w}_jobs.jsonl', shard)
        write_rows(root/f'sam31_semantic_books_full30_w{w}_jobs.jsonl', [
            {**j, 'semantic_text': 'book'} for j in shard if 'book' in j['target_name']])
    write_rows(root/'sam31_rgb_health_full30_jobs.jsonl', valid)
    scope = dict(cases=len(valid), frames=sum(len(j['frames']) for j in valid),
                 prefix_frames=sum(j['frames'][-1]-j['prompt_frame']+1 for j in valid),
                 book_cases=sum('book' in j['target_name'] for j in valid),
                 initial_actual_cases=0, shard_sizes=list(map(len, shards)), sources=manifest['sources'])
    (root/'generation_scope.json').write_text(json.dumps(scope, indent=2)+'\n')
    protocols = {
        'sam31_integrated_full30_protocol.json': {'runner_sha256': manifest['sources']['repair_sam31_integrated_full30.py'], 'rgb_policy_sha256': manifest['sources']['repair_sam31_static_attachment.py']},
        'sam31_rgb_health_full30_protocol.json': {'sources': {n: manifest['sources'][n] for n in ('repair_sam31_rgb_health_full30.py', 'sam31_rgb_observation_health.py', 'repair_sam31_static_attachment.py')}},
        'sam31_rgb_certified_full30_protocol.json': {'runner_sha256': manifest['sources']['certify_sam31_recovered_rgb_full30.py'], 'rgb_health_module_sha256': manifest['sources']['sam31_rgb_observation_health.py']},
        'sam31_visible_projection_full30_protocol.json': {'observation_sources': {n: manifest['sources'][n] for n in ('repair_sam31_visible_projection_full30.py', 'sam31_observed_integer_rgb_rim.py', 'sam31_rgb_observation_health.py', 'track_sam31_initial_actual_foreground.py')}},
    }
    for name, protocol in protocols.items():
        (root/name).write_text(json.dumps(protocol, indent=2)+'\n')
    receipt = dict(registered_cases=len(jobs), eligible_cases=len(valid),
                   input_failures={j['id']: j['input_failure'] for j in jobs if j['input_failure']},
                   prepared_file_hashes={p.name: sha(p) for p in root.iterdir() if p.is_file()},
                   frozen_manifest=manifest, gpu_run=False, fitter_run=False)
    (root/'prepared.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def tracker(root, source, jobs_name, stem, sam3, checkpoint):
    output = root/'runs'/(stem+'_tracks.jsonl')
    if not read_rows(root/jobs_name):
        output.write_text('')
        return
    execute(root, stem, [sys.executable, str(root/source), str(root/jobs_name), str(output),
                        '--sam3', str(sam3), '--checkpoint', str(checkpoint),
                        '--mask-dir', str(root/'runs'/(stem+'_masks'))])


def execute(root, name, command):
    with (root/'runs'/(name+'.log')).open('x') as log:
        subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)


def measure(root, pipeline_failure=None):
    """Same locked V4 function as the development/generation measurement."""
    import cv2
    import numpy as np
    from gravtrace.observations import refine_box
    cv2.setNumThreads(1)
    rows = root/'runs/sam31_visible_projection_full30_tracks.jsonl'
    jobs = read_rows(root/'all_jobs.jsonl')
    raw = read_rows(rows) if rows.exists() and not pipeline_failure else []
    integer = {t['id']: t for t in raw}
    if not pipeline_failure and (len(integer) != len(raw) or set(integer) != {j['id'] for j in jobs if not j['input_failure']}):
        raise ValueError('Final case identity/denominator mismatch')
    predictions, details = [], []
    for j in jobs:
        failure = j['input_failure'] or pipeline_failure
        t = integer.get(j['id'])
        boxes, statuses, pixels, masks = [], [], {}, {}
        if not failure and (t is None or t['frames'] != j['frames'] or len(t['boxes']) != len(j['frames'])):
            raise ValueError('Final scope/frame identity mismatch: '+j['id'])
        if not failure and sha(j['video']) != j['video_sha256']:
            raise ValueError('Source video drift before V4 measurement: '+j['id'])
        cap = cv2.VideoCapture(j['video']) if not failure else None
        try:
            for k, f in enumerate(j['frames']):
                b = t['boxes'][k] if t else None
                if failure or b is None:
                    boxes.append(None)
                    statuses.append(failure or t['reasons'][k])
                    continue
                path = root/'runs/sam31_visible_projection_full30_masks'/f'{hashlib.sha256(j["id"].encode()).hexdigest()[:12]}_{f}.npz'
                with np.load(path, allow_pickle=False) as z:
                    m = z['mask']
                cap.set(cv2.CAP_PROP_POS_FRAMES, f)
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError('Selected source RGB unreadable: '+j['id'])
                box, diagnostic = refine_box(bgr, m, b)
                boxes.append(box)
                statuses.append(diagnostic['status'])
                pixels[str(f)] = hashlib.sha256(bgr.tobytes()).hexdigest()
                masks[str(f)] = hashlib.sha256(m.astype(np.uint8).tobytes()).hexdigest()
        finally:
            if cap is not None:
                cap.release()
        predictions.append(dict(id=j['id'], fps=j['fps'], tracks={j['target_name']: dict(frames=j['frames'], xyxy=boxes)},
                                frontend='sam31_single_view_frozen_v4', reasons=statuses, video=j['video'],
                                video_sha256=j.get('video_sha256'), frontend_manifest_sha256=sha(FROZEN/'manifest.json')))
        details.append(dict(id=j['id'], frames=j['frames'], statuses=statuses,
                            pixel_sha256=pixels, mask_sha256=masks, video_sha256=j.get('video_sha256')))
    write_rows(root/'measurements_v4.jsonl', details)
    for p in predictions:
        p['measurements_path'] = str((root/'measurements_v4.jsonl').resolve())
        p['measurements_sha256'] = sha(root/'measurements_v4.jsonl')
    write_rows(root/'tracks_v4.jsonl', predictions)
    return dict(registered_cases=len(predictions), missing_boxes=sum(b is None for p in predictions for t in p['tracks'].values() for b in t['xyxy']),
                tracks_sha256=sha(root/'tracks_v4.jsonl'), fitter_run=False, single_view=True)


def validate_runtime(sam3, checkpoint):
    """Check frozen source and weights on CPU before spending generation GPU time."""
    sam3, checkpoint = Path(sam3).expanduser().resolve(), Path(checkpoint).expanduser().resolve()
    manifest = lock()
    if sha(checkpoint) != manifest['checkpoint_sha256']:
        raise ValueError('Official checkpoint SHA mismatch')
    commit = subprocess.check_output(['git', '-C', str(sam3), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != manifest['official_source_commit']:
        raise ValueError('Official SAM source revision mismatch')
    subprocess.run(['git', '-C', str(sam3), 'diff', '--exit-code', 'HEAD', '--', '*.py'], check=True, stdout=subprocess.DEVNULL)
    return dict(source_commit=commit, checkpoint_sha256=manifest['checkpoint_sha256'], gpu_started=False)


def run(root, sam3, checkpoint):
    if not __debug__:
        raise RuntimeError('Python -O is unsupported')
    root, sam3, checkpoint = Path(root).resolve(), Path(sam3).resolve(), Path(checkpoint).resolve()
    manifest = lock()
    receipt = json.loads((root/'prepared.json').read_text())
    if receipt['frozen_manifest'] != manifest:
        raise ValueError('Prepared version does not match frozen manifest')
    for name, expected in receipt['prepared_file_hashes'].items():
        if sha(root/name) != expected:
            raise ValueError('Prepared input/source drift: '+name)
    # No import/build of SAM before source/version and input binding checks.
    for j in read_rows(root/'all_jobs.jsonl'):
        if not j['input_failure'] and sha(j['video']) != j['video_sha256']:
            raise ValueError('Input video drift: '+j['id'])
    if (root/'started.json').exists():
        raise ValueError('Run already attempted; keep its partial outputs, no automatic retry')
    eligible = receipt['eligible_cases']
    if eligible:
        validate_runtime(sam3, checkpoint)
    (root/'started.json').write_text(json.dumps({'gpu_requested': bool(eligible), 'fitter_run': False})+'\n')
    try:
        if eligible:
            (root/'sam31_official').symlink_to(sam3, target_is_directory=True)
            (root/'weights/sam3.1').mkdir(parents=True)
            (root/'weights/sam3.1/sam3.1_multiplex.pt').symlink_to(checkpoint)
            for w in (0, 1):
                tracker(root, 'track_sam31_identity_center_control.py', f'sam31_identity_full30_w{w}_jobs.jsonl', f'sam31_identity_full30_w{w}', sam3, checkpoint)
                tracker(root, 'track_sam31_whole_book_control.py', f'sam31_semantic_books_full30_w{w}_jobs.jsonl', f'sam31_semantic_books_full30_w{w}', sam3, checkpoint)
            jobs = {j['id']: j for j in read_rows(root/'sam31_rgb_health_full30_jobs.jsonl')}
            actual = [{**jobs[t['id']], 'semantic_text': 'book'} for w in (0, 1)
                      for t in read_rows(root/'runs'/f'sam31_semantic_books_full30_w{w}_tracks.jsonl')
                      if t.get('exception') == 'AssertionError: No unambiguous initial target identity from actual masks']
            scope = json.loads((root/'generation_scope.json').read_text())
            scope['initial_actual_cases'] = len(actual)
            (root/'generation_scope.json').write_text(json.dumps(scope, indent=2)+'\n')
            for w in range(4):
                write_rows(root/f'sam31_initial_actual_foreground_w{w}_jobs.jsonl', actual if w == 0 else [])
                if w:
                    (root/'runs'/f'sam31_initial_actual_foreground_w{w}_tracks.jsonl').write_text('')
            for name in ('repair_sam31_integrated_full30.py', 'repair_sam31_rgb_health_full30.py', 'certify_sam31_recovered_rgb_full30.py'):
                execute(root, name, [sys.executable, str(root/'sam31_scope.py'), str(root), name])
            tracker(root, 'track_sam31_initial_actual_foreground.py', 'sam31_initial_actual_foreground_w0_jobs.jsonl', 'sam31_initial_actual_foreground_w0', sam3, checkpoint)
            name = 'repair_sam31_visible_projection_full30.py'
            execute(root, name, [sys.executable, str(root/'sam31_scope.py'), str(root), name])
        result = measure(root)
        (root/'completed.json').write_text(json.dumps(result, indent=2)+'\n')
    except Exception as error:
        failure = type(error).__name__+': '+str(error)
        (root/'failure.json').write_text(json.dumps({'reason': failure, 'partial_outputs_retained': True})+'\n')
        measure(root, pipeline_failure=failure)
        raise
    return result


def generation_jobs(items_path, rows_path, initial_path, output):
    item_rows, initial_rows = read_rows(items_path), read_rows(initial_path)
    items = {it['id']: it for it in item_rows}
    initial = {j['id']: j for j in initial_rows}
    if len(items) != len(item_rows) or len(initial) != len(initial_rows):
        raise ValueError('Duplicate registered item or initial-prompt ID')
    jobs = []
    for row in read_rows(rows_path):
        it = items[row['item_id']]
        seed = initial.get(row['sample_id'], {})
        fps = float(row['output_fps'])
        start = it['window']['start_frame']/float(it['fps'])
        end = start+(it['window']['max_frames']-1)/float(it['fps'])
        condition = row['condition_frame_index']/float(it['fps'])
        frames = [f for f in range(int(row['num_frames'])) if start-1e-6 <= condition+f/fps <= end+1e-6]
        video = Path(seed.get('video', row.get('generated_video_resized_to_source', 'missing'))).resolve()
        path_mismatch = row.get('generated_video_resized_to_source') and video != Path(row['generated_video_resized_to_source']).resolve()
        jobs.append(dict(id=row['sample_id'], video=str(video), video_sha256=sha(video) if video.is_file() else None,
                         frames=frames, prompt_frame=seed.get('prompt_frame', 0), scene_boxes=seed.get('objects', {}),
                         target_name=it['object_name'], fps=fps,
                         input_failure=row.get('input_failure') or seed.get('input_failure') or
                         ('generated_video_path_mismatch' if path_mismatch else None) or
                         ('missing_initial_prompt_record' if not seed else None)))
    if Path(output).exists():
        raise ValueError('Do not overwrite existing jobs')
    write_rows(output, jobs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare', help='CPU-only validation and immutable run preparation')
    p.add_argument('jobs'); p.add_argument('run_dir')
    p = commands.add_parser('run', help='Explicit one-shot GPU frontend; no fitting')
    p.add_argument('run_dir'); p.add_argument('--sam3', required=True); p.add_argument('--checkpoint', required=True)
    p = commands.add_parser('generation-jobs', help='Convert the public generation jobs to the fixed single-view window')
    p.add_argument('items'); p.add_argument('rows'); p.add_argument('initial_jobs'); p.add_argument('out')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.jobs, args.run_dir)
        print(json.dumps({k: result[k] for k in ('registered_cases', 'eligible_cases', 'input_failures', 'gpu_run', 'fitter_run')}))
    elif args.command == 'run':
        print(json.dumps(run(args.run_dir, args.sam3, args.checkpoint)))
    else:
        generation_jobs(args.items, args.rows, args.initial_jobs, args.out)


if __name__ == '__main__':
    main()
