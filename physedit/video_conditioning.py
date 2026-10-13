"""Explicit full-video input registration for LTX video editing.

Reference future frames are never selected as an implicit model input.
"""
import json
import math
from pathlib import Path

from .runners.media_contract import sha256, validate_video


def registration(spec):
    value = spec.get('v2v')
    if not isinstance(value, dict) or set(value) != {'manifest', 'manifest_sha256', 'denoise_strength', 'conditioning_strength'}:
        raise ValueError('v2v requires manifest, manifest_sha256, denoise_strength and conditioning_strength')
    for name in ('denoise_strength', 'conditioning_strength'):
        x = value[name]
        if type(x) not in (int, float) or not math.isfinite(x) or not 0 < x < 1:
            raise ValueError('v2v.' + name + ' must be strictly between zero and one')
    from .runners.model_parameters import parameters
    if int(parameters(spec['model'])['steps'] * value['denoise_strength']) < 1:
        raise ValueError('v2v_denoise_strength_produces_zero_steps')
    if sha256(value['manifest']) != value['manifest_sha256']:
        raise ValueError('v2v_manifest_sha256_mismatch')
    rows = [json.loads(line) for line in Path(value['manifest']).read_text().splitlines() if line.strip()]
    fields = {'item_id', 'video', 'video_sha256', 'fps', 'frames', 'start_frame'}
    if any(set(r) != fields for r in rows) or len({r['item_id'] for r in rows}) != len(rows):
        raise ValueError('v2v_manifest_fields_or_duplicate_item')
    return {r['item_id']: r for r in rows}


def attach(rows, spec):
    """Retain each failed/missing source row in the original denominator."""
    registered = registration(spec)
    if set(registered) - {r['item_id'] for r in rows}:
        raise ValueError('v2v_manifest_contains_unregistered_items')
    for row in rows:
        row['mode'] = 'v2v'
        if row.get('input_failure'):
            continue
        try:
            source = registered.get(row['item_id'])
            if source is None:
                raise ValueError('missing_registered_v2v_source')
            if source['video_sha256'] == row.get('source_video_sha256'):
                raise ValueError('v2v_input_must_be_distinct_from_target_reference')
            if type(source['start_frame']) is not int or source['start_frame'] < 0:
                raise ValueError('invalid_v2v_start_frame')
            if type(source['frames']) is not int or source['frames'] < 2:
                raise ValueError('invalid_v2v_source_frames')
            info = validate_video(source['video'], fps=source['fps'], frames=source['frames'],
                                  width=row['source_width'], height=row['source_height'])
            if info['video_sha256'] != source['video_sha256']:
                raise ValueError('v2v_source_sha256_mismatch')
            row.update(conditioning_video=str(Path(source['video']).resolve()),
                       conditioning_video_sha256=source['video_sha256'],
                       conditioning_fps=source['fps'], conditioning_frames=source['frames'],
                       conditioning_start_frame=source['start_frame'],
                       denoise_strength=spec['v2v']['denoise_strength'],
                       conditioning_strength=spec['v2v']['conditioning_strength'])
            # Verify registered time coverage and the initial geometry before
            # generation. Frozen prompts/pose stay attached to frame zero.
            load_frames(row, require_initial_match=True)
        except (ValueError, OSError, KeyError, TypeError) as error:
            row['input_failure'] = 'v2v_input_failure: ' + str(error)
    return rows


def load_frames(row, *, require_initial_match=True):
    """Resample a declared source interval in seconds, without speed changes."""
    import cv2
    import numpy as np
    from PIL import Image
    path = row['conditioning_video']
    if sha256(path) != row['conditioning_video_sha256']:
        raise ValueError('v2v_source_changed_since_registration')
    validate_video(path, fps=row['conditioning_fps'], frames=row['conditioning_frames'],
                   width=row['source_width'], height=row['source_height'])
    count, fps = int(row['num_frames']), float(row['output_fps'])
    start, native = row['conditioning_start_frame'], float(row['conditioning_fps'])
    if start + (count - 1) * native / fps > row['conditioning_frames'] - 1 + 1e-8:
        raise ValueError('incomplete_v2v_real_time_window')
    # Nearest native frame, tie toward the earlier frame; never stretch time.
    indices = np.ceil(start + np.arange(count) * native / fps - 0.5).astype(int)
    cap = cv2.VideoCapture(path)
    frames = []
    needed = set(indices.tolist())
    index = 0
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            if index in needed:
                frames.append((index, image))
            index += 1
    finally:
        cap.release()
    lookup = dict(frames)
    if set(lookup) != needed or sha256(path) != row['conditioning_video_sha256']:
        raise ValueError('v2v_decode_or_source_drift')
    first = lookup[indices[0]]
    if require_initial_match:
        condition = cv2.imread(row['condition_image'])
        if condition is None or not np.array_equal(condition, first):
            raise ValueError('v2v_initial_pixels_do_not_match_frozen_reference_geometry')
    return [Image.fromarray(cv2.cvtColor(lookup[i], cv2.COLOR_BGR2RGB)) for i in indices]
