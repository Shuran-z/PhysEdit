"""Declared local generation contracts for the registered PhyEditing models.

This module only describes inputs and launches; importing it never loads a model.
The older fleet commands remain independent of this one-shot local controller.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelContract:
    runner: str
    frames: int
    fps: int
    mode: str = 'i2v'
    canvas: tuple[int, int] | None = None
    square_canvas: int | None = None
    needs: tuple[str, ...] = ()


MODELS = {
    'ltx_i2v': ModelContract('diffusers', 81, 16, canvas=(704, 480), square_canvas=480),
    'cogvideox_i2v': ModelContract('diffusers', 81, 16, canvas=(768, 480), square_canvas=480),
    # The TI2V checkpoint can also do T2V. This registered benchmark route
    # supplies condition_image to WanImageToVideoPipeline, so it is I2V only.
    'wan_ti2v5b': ModelContract('diffusers', 81, 16, mode='i2v', canvas=(832, 480)),
    'hunyuan15_i2v': ModelContract('diffusers', 121, 24, canvas=(848, 480), square_canvas=640),
    'cosmos': ModelContract('cosmos_predict2', 81, 16, mode='v2v_one_condition_frame',
                            needs=('code_dir',)),
    'dynamicrafter_i2v': ModelContract('dynamicrafter', 16, 8, needs=('code_dir',)),
    'videogpa_ti2v5b': ModelContract('videogpa', 49, 15, canvas=(832, 480),
                                     needs=('code_dir', 'lora_dir')),
    'physrvg_ti2v5b': ModelContract('physrvg', 49, 15, canvas=(832, 480), square_canvas=640,
                                    needs=('code_dir', 'lora_dir')),
    'cosmos3_nano': ModelContract('cosmos3', 81, 16, canvas=(832, 480), square_canvas=640),
    'wan22_i2v_a14b': ModelContract('wan22', 81, 16, canvas=(832, 480),
                                    needs=('code_dir',)),
    'physalign_wan22_i2v_a14b': ModelContract('wan22', 81, 16, canvas=(832, 480),
                                              needs=('code_dir', 'lora_dir', 'physalign_hook_dir')),
    'minimax_h3': ModelContract('minimax_h3', 124, 24, canvas=(896, 512), square_canvas=640),
}


def contract(model: str) -> ModelContract:
    try:
        return MODELS[model]
    except KeyError:
        raise ValueError('Unknown registered generation model: ' + str(model)) from None


def validate_registration(spec: dict, *, require_runtime=True) -> ModelContract:
    profile = contract(spec['model'])
    for key in ('mode', 'conditioning_mode'):
        if key in spec and spec[key] != profile.mode:
            raise ValueError(f"Registered {spec['model']} conditioning mode is {profile.mode}; "
                             f"requested {spec[key]}")
    if (type(spec['frames']) is not int or spec['frames'] != profile.frames or
            float(spec['fps']) != profile.fps):
        raise ValueError(f"Registered {spec['model']} clock is {profile.frames} frames at {profile.fps} fps")
    runtime = spec.get('generation_runtime', {})
    if not isinstance(runtime, dict):
        raise ValueError('generation_runtime must be an object')
    missing = [key for key in profile.needs if require_runtime and
               (not isinstance(runtime.get(key), str) or not runtime[key])]
    if missing:
        raise ValueError(f"{spec['model']} requires generation_runtime fields: {', '.join(missing)}")
    if 'python' in runtime and (not isinstance(runtime['python'], str) or not runtime['python']):
        raise ValueError('generation_runtime.python must be a nonempty executable path')
    if 'gpu_devices' in runtime and (not isinstance(runtime['gpu_devices'], str) or not runtime['gpu_devices']):
        raise ValueError('generation_runtime.gpu_devices must be a nonempty string')
    if 'pythonpath' in runtime and (not isinstance(runtime['pythonpath'], list) or
                                     any(not isinstance(p, str) or not p for p in runtime['pythonpath'])):
        raise ValueError('generation_runtime.pythonpath must be a list of paths')
    return profile
