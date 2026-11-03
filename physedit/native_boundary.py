"""Registered native model clocks, separate from reference task windows."""
import math
import hashlib
import json
from pathlib import Path

from .runners.oneclick_registry import contract

VERSION='native-window-v1'


def model_contract(model):
    p=contract(model)
    return dict(schema=VERSION,model=model,native_frames=p.frames,native_fps=p.fps,
        output_policy='full_native_video; score the registered reference window; no retiming, interpolation, looping or chaining')


def coverage(registered,rows):
    expected=model_contract(registered['model'])
    if any(registered.get(k)!=v for k,v in expected.items()):raise ValueError('native_model_contract_changed')
    if registered.get('registration_path'):
        path=Path(registered['registration_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=registered.get('registration_sha256'):
            raise ValueError('native_generation_registration_changed')
        config=json.loads(path.read_text(encoding='utf8'))
        if (config['model']!=expected['model']or config['frames']!=expected['native_frames']or config['fps']!=expected['native_fps']):
            raise ValueError('native_generation_registration_clock_changed')
    unsupported=[]
    for row in rows:
        fps=row.get('fps',row.get('output_fps'));n=row['num_frames'];reasons=[]
        if type(fps)not in(int,float)or not math.isfinite(fps)or abs(fps-expected['native_fps'])>1e-8:
            reasons.append('requested_fps_differs_from_registered_native_clock')
        if type(n)is not int or n<2 or n>expected['native_frames']:
            reasons.append('required_native_frame_count_exceeds_registered_model')
        elif n!=expected['native_frames']:
            reasons.append('generation_length_is_not_registered_native_length')
        horizon=row.get('evaluation_duration_s')
        if horizon is not None and horizon>(expected['native_frames']-1)/expected['native_fps']+1e-6:
            reasons.append('reference_window_exceeds_registered_native_horizon')
        if reasons:unsupported.append(dict(sample_id=row['sample_id'],clip_id=row.get('clip_id'),
            required_frames=n,reference_horizon_s=horizon,reasons=reasons))
    return dict(registered=len(rows),compatible=len(rows)-len(unsupported),unsupported_count=len(unsupported),
        native_frames=expected['native_frames'],native_fps=expected['native_fps'],
        native_horizon_s=(expected['native_frames']-1)/expected['native_fps'],
        execution_supported=not unsupported,unsupported=unsupported,
        unsupported_is_a_configuration_limit_not_an_observed_physics_error=True)
