"""CPU-only full media validation and immutable generation completion bindings.

Also importable as a standalone module when runners are deployed together.
"""
import hashlib
import json
import math
import os
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def row_digest(row):
    # No transient status or host path substitutions after registration.
    return hashlib.sha256(json.dumps(row, sort_keys=True, allow_nan=False).encode()).hexdigest()


def validate_video(path, *, fps, frames=None, width=None, height=None):
    import cv2
    if not math.isfinite(float(fps)) or float(fps) <= 0:
        raise ValueError('invalid_registered_fps')
    path = Path(path)
    if not path.is_file():
        raise ValueError('missing_source_video')
    before_sha = sha256(path)
    cap = cv2.VideoCapture(str(path))
    n, stamps = 0, []
    try:
        if not cap.isOpened():
            raise ValueError('video_decode_failure')
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        declared_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isclose(actual_fps, float(fps), rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError('video_fps_mismatch')
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (width is not None and w != width) or (height is not None and h != height):
            raise ValueError('video_dimensions_mismatch')
        while True:
            ok, image = cap.read()
            if not ok:
                break
            if image is None or image.shape[:2] != (h, w):
                raise ValueError('video_decode_failure')
            stamps.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.)
            n += 1
        if not n or n != declared_count or (frames is not None and n != frames):
            raise ValueError('video_frame_count_mismatch')
        # Fail closed on absent/duplicate/VFR timestamps; never change the clock.
        tolerance = max(1e-5, 0.002 / float(fps))
        if any(not math.isfinite(t) or abs(t - i / float(fps)) > tolerance for i, t in enumerate(stamps)):
            raise ValueError('video_timestamp_mismatch')
    finally:
        cap.release()
    if sha256(path) != before_sha:
        raise ValueError('video_changed_during_validation')
    return dict(video_sha256=before_sha, frames=n, fps=actual_fps, width=w, height=h,
                timestamp_sha256=hashlib.sha256(json.dumps(stamps).encode()).hexdigest(), full_decode=True)


def validate_row(row):
    return validate_video(row.get('final_resized') or row['generated_video_resized_to_source'],
                          fps=float(row['output_fps']), frames=int(row['num_frames']),
                          width=int(row['source_width']), height=int(row['source_height']))


def completion_path(row):
    return Path(row.get('final_resized') or row['generated_video_resized_to_source']).with_suffix('.completed.json')


def input_hashes(row):
    names = ['condition_image', 'prompt_file', 'negative_prompt_file']
    if row.get('mode') in ('v2v', 'v2v_future'):
        names.append('conditioning_video')
    if row.get('mode') == 'v2v_future':
        names.extend(['conditioning_source_video', 'future_manifest'])
    return {k: sha256(row[k]) for k in names}


def seal_completion(row, settings=None, expected_inputs=None):
    media = validate_row(row)
    inputs = input_hashes(row)
    if expected_inputs is not None and inputs != expected_inputs:
        raise ValueError('generation_input_changed_during_run')
    receipt = dict(row_sha256=row_digest(row), media=media, input_sha256=inputs, settings=settings)
    path = completion_path(row)
    tmp = path.with_suffix('.json.partial')
    with tmp.open('x') as f:
        json.dump(receipt, f, sort_keys=True)
    os.replace(tmp, path)
    return receipt


def verified_completion(row, settings=None):
    """A receipt alone is insufficient: re-read bytes, decode, scope and clock."""
    receipt = json.loads(completion_path(row).read_text())
    if (receipt['row_sha256'] != row_digest(row) or receipt['media'] != validate_row(row) or
            receipt['input_sha256'] != input_hashes(row) or
            (settings is not None and receipt.get('settings') != settings)):
        raise ValueError('completed_media_or_contract_drift')
    return receipt
