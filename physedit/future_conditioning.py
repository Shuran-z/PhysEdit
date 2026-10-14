"""Five-frame Cosmos history, ending at the registered condition time."""
import json
import math
import subprocess
from pathlib import Path

from .runners.media_contract import sha256, validate_video


def registration(spec):
    value = spec.get('future')
    if not isinstance(value, dict) or set(value) != {'manifest', 'manifest_sha256'}:
        raise ValueError('future requires manifest and manifest_sha256')
    if sha256(value['manifest']) != value['manifest_sha256']:
        raise ValueError('future_manifest_sha256_mismatch')
    rows = [json.loads(s) for s in Path(value['manifest']).read_text().splitlines() if s.strip()]
    fields = {'item_id', 'video', 'video_sha256', 'fps', 'frames', 'end_frame'}
    if any(not isinstance(r, dict) or set(r) != fields for r in rows):
        raise ValueError('future_manifest_fields')
    if len({r['item_id'] for r in rows}) != len(rows):
        raise ValueError('future_manifest_duplicate_item')
    return {r['item_id']: r for r in rows}


def history(row, source):
    """Return only five real observations; never pad or pass a future frame."""
    import cv2
    import numpy as np
    if type(source['end_frame']) is not int or type(source['frames']) is not int:
        raise ValueError('invalid_future_frame_indices')
    native = float(source['fps'])
    if not math.isfinite(native) or native <= 0:
        raise ValueError('invalid_future_source_fps')
    end = source['end_frame']
    if not 0 <= end < source['frames']:
        raise ValueError('future_end_frame_outside_video')
    if not math.isclose(end/native, row['condition_frame_index']/float(row['source_native_fps']), abs_tol=1e-8):
        raise ValueError('future_history_end_time_mismatch')
    positions = end - np.arange(4, -1, -1) * native / float(row['output_fps'])
    indices = np.ceil(positions - .5).astype(int).tolist()
    if positions[0] < 0 or len(set(indices)) != 5 or max(indices) > end:
        raise ValueError('insufficient_distinct_future_history')
    info = validate_video(source['video'], fps=native, frames=source['frames'],
                          width=row['source_width'], height=row['source_height'])
    if info['video_sha256'] != source['video_sha256']:
        raise ValueError('future_source_sha256_mismatch')
    cap = cv2.VideoCapture(source['video'])
    pixels = []
    try:
        for index in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok:
                raise ValueError('future_history_decode_failure')
            pixels.append(image)
    finally:
        cap.release()
    condition = cv2.imread(row['condition_image'])
    if condition is None or not np.array_equal(pixels[-1], condition):
        raise ValueError('future_last_history_frame_must_match_condition_image')
    if sha256(source['video']) != source['video_sha256']:
        raise ValueError('future_source_changed_during_decode')
    return pixels, indices, (np.asarray(indices)/native - end/native).tolist()


def attach(rows, spec):
    registered = registration(spec)
    if set(registered) - {r['item_id'] for r in rows}:
        raise ValueError('future_manifest_contains_unregistered_items')
    ffmpeg = spec.get('generation_runtime', {}).get('ffmpeg', 'ffmpeg')
    for row in rows:
        row.update(mode='v2v_future', native_num_frames=81, num_frames=77,
                   condition_frames=5, evaluated_condition_frames=1,
                   predicted_future_frames=76, history_prefix_trim_frames=4)
        if row.get('input_failure'):
            continue
        try:
            source = registered.get(row['item_id'])
            if source is None:
                raise ValueError('missing_registered_future_history')
            pixels, indices, times = history(row, source)
            folder = Path(row['out_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            clip = folder/'history.mp4'
            partial = folder/'history.partial.mp4'
            if clip.exists() or partial.exists():
                raise ValueError('existing_future_history_retained_no_retry')
            # Lossless RGB encoding keeps the last history frame identical to
            # the original single-view condition, including after decoding.
            h, w = pixels[0].shape[:2]
            command = [ffmpeg, '-nostdin', '-n', '-v', 'error', '-f', 'rawvideo',
                       '-pixel_format', 'bgr24', '-video_size', f'{w}x{h}',
                       '-framerate', str(row['output_fps']), '-i', 'pipe:0', '-an',
                       '-c:v', 'libx264rgb', '-crf', '0', '-pix_fmt', 'bgr24', str(partial)]
            subprocess.run(command, input=b''.join(p.tobytes() for p in pixels), check=True)
            validate_video(partial, fps=row['output_fps'], frames=5, width=w, height=h)
            # Verify every encoded observation against the decoded source.
            import cv2
            import numpy as np
            cap = cv2.VideoCapture(str(partial))
            try:
                for image in pixels:
                    ok, decoded = cap.read()
                    if not ok or not np.array_equal(decoded, image):
                        raise ValueError('future_history_pixel_mismatch')
            finally:
                cap.release()
            partial.rename(clip)
            ratios = {'1:1':1., '4:3':4/3, '3:4':3/4, '16:9':16/9, '9:16':9/16}
            aspect = min(ratios, key=lambda key:abs(math.log((w/h)/ratios[key])))
            row.update(aspect_ratio=aspect, conditioning_video=str(clip.resolve()),
                       conditioning_video_sha256=sha256(clip),
                       conditioning_source_video=str(Path(source['video']).resolve()),
                       conditioning_source_sha256=source['video_sha256'],
                       future_manifest=str(Path(spec['future']['manifest']).resolve()),
                       future_manifest_sha256=spec['future']['manifest_sha256'],
                       history_source_indices=indices, history_relative_times_s=times,
                       history_sampling_max_error_s=max(abs(t-(k-4)/row['output_fps']) for k,t in enumerate(times)),
                       cosmos_predict2_condition_frames=5, source_sample_fps=row['output_fps'])
        except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
            row['input_failure'] = 'future_input_failure: ' + str(error)
    return rows
