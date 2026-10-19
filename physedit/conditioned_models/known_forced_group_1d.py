"""Registered conditional motion model and image objective."""
import numpy as np
KEYS = {'mass', 'known_friction', 'known_linear_drag_per_second', 'known_velocity', 'step_s', 'steps_per_observation', 'world_force_updates_from_config', 'condition_frame_relative'}

def displacement(condition, gravity):
    assert set(condition) == KEYS, 'unexpected_target_alias_or_future_state'
    assert condition['condition_frame_relative'] == 0
    assert condition['mass'] > 0 and condition['known_friction'] > 0
    assert len(condition['known_velocity']) == 3
    h = condition['step_s']
    steps = condition['steps_per_observation']
    assert h > 0 and isinstance(steps, int) and (steps > 0)
    controls = np.asarray(condition['world_force_updates_from_config'], float)
    assert controls.ndim == 2 and controls.shape[1] == 3 and np.isfinite(controls).all()
    assert np.max(np.abs(controls[:, 1:])) == 0
    x = 0.0
    v = float(condition['known_velocity'][0])
    result = [x]
    for force in controls[1:]:
        for _ in range(steps):
            v += h * (force[0] / condition['mass'] - condition['known_linear_drag_per_second'] * v)
            friction_step = condition['known_friction'] * gravity * h
            v = max(0.0, v - friction_step) if v > 0 else min(0.0, v + friction_step)
            x += h * v
        result.append(x)
    return np.asarray(result)
