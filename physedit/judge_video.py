"""Native video evidence for the visual judge; unrelated to inversion observations."""
import math
import hashlib
from pathlib import Path


def sampling(count, native_fps, config):
    if type(count) is not int or count < 2 or not math.isfinite(native_fps) or native_fps <= 0:
        raise ValueError('insufficient_video_frames_for_judge')
    requested = config.get('video_fps', 2.0)
    maximum = config.get('max_video_frames', 64)
    n = max(2, round((count-1)/native_fps*requested)+1)
    n += n % 2  # Qwen temporal patches contain two frames, with no implicit padding.
    if n > count:
        n = count - count % 2
    if n > maximum:
        raise ValueError('judge_full_video_exceeds_registered_frame_budget')
    indices = [round(k*(count-1)/(n-1)) for k in range(n)]
    assert len(set(indices)) == n and indices[0] == 0 and indices[-1] == count-1
    return indices, (n-1)*native_fps/(count-1)


def verify_evidence(evidence, prompt_path):
    """Bind the actual consumed image/video and temporal anchors to registration."""
    import cv2
    from .qwen_judge import file_sha
    if evidence.get('protocol') != 'visible_video_full_v2':
        raise ValueError('judge_requires_registered_video_input')
    if Path(evidence['condition_image']).resolve() != Path(evidence['condition']['path']).resolve():
        raise ValueError('judge_condition_path_mismatch')
    video = evidence['video']
    frames = evidence['frames']
    expected, fps = sampling(video['frame_count'], video['native_fps'], {
        'video_fps': evidence['requested_sampling_fps'],
        'max_video_frames': max(64, len(frames)),
    })
    if ([f['frame_index'] for f in frames] != expected
            or any(type(f['frame_index']) is not int for f in frames)
            or not math.isclose(evidence['sampling_fps'], fps, rel_tol=0, abs_tol=1e-9)
            or any(not math.isclose(f['time_seconds'], f['frame_index'] / video['native_fps'],
                                    rel_tol=0, abs_tol=1e-9) for f in frames)):
        raise ValueError('judge_temporal_registration_mismatch')
    if file_sha(video['path']) != video['sha256']:
        raise ValueError('judge_video_drift')
    for record in [evidence['condition']] + frames:
        if file_sha(record['path']) != record['png_sha256']:
            raise ValueError('judge_image_drift')
        decoded = cv2.imread(record['path'])
        if (decoded is None or hashlib.sha256(decoded.tobytes()).hexdigest() != record['decoded_bgr_sha256']
                or [decoded.shape[1], decoded.shape[0]] != record['size']):
            raise ValueError('judge_decoded_pixel_drift')
    if file_sha(prompt_path) != evidence['prompt_sha256']:
        raise ValueError('judge_prompt_drift')


def local_inputs(processor, evidence, prompt):
    import numpy as np
    import cv2
    from PIL import Image
    from .qwen_judge import PROMPT_PATH
    verify_evidence(evidence, PROMPT_PATH)
    condition = Image.open(evidence['condition']['path']).convert('RGB')
    frames = []
    for f in evidence['frames']:
        bgr = cv2.imread(f['path'])
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    content = [
        {'type':'text','text':'Declared conditioning image, not a reference continuation:'},
        {'type':'image','image':condition},
        {'type':'text','text':video_description(evidence)},
        {'type':'video','video':evidence['video']['path']},
        {'type':'text','text':prompt},
    ]
    text = processor.apply_chat_template([{'role':'user','content':content}],
                                         tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
    inputs = processor(text=[text], images=[condition], videos=[np.stack(frames)],
                       fps=evidence['sampling_fps'], max_pixels=evidence['processor_max_pixels'],
                       return_tensors='pt')
    if 'pixel_values_videos' not in inputs or 'video_grid_thw' not in inputs:
        raise ValueError('judge_processor_did_not_encode_video')
    audit = {k:list(v.shape) for k,v in inputs.items() if hasattr(v,'shape')}
    for k in ('image_grid_thw','video_grid_thw'):
        if k in inputs: audit[k+'_values'] = inputs[k].tolist()
    if 'second_per_grid_ts' in inputs: audit['second_per_grid_ts'] = list(inputs['second_per_grid_ts'])
    audit.update(video_sha256=evidence['video']['sha256'], sampled_indices=[f['frame_index'] for f in evidence['frames']],
                 sampled_actual_times=[f['time_seconds'] for f in evidence['frames']], sampling_fps=evidence['sampling_fps'])
    return inputs, audit


def video_description(evidence):
    video = evidence['video']
    return (f"Full generated video: {video['duration_seconds']:.6f} seconds, "
            f"{video['frame_count']} native frames at {video['native_fps']} fps. "
            'Assess the visible sequence, not hidden events. A visual judgement does not prove physical correctness. '
            'Registered native frame anchors (frame: seconds): ' + ', '.join(
                f"{f['frame_index']}: {f['time_seconds']:.6f}" for f in evidence['frames']))
