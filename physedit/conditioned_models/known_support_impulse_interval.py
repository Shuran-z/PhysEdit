"""Registered conditional motion model and image objective."""
import numpy as np
KEYS = {'mass', 'known_linear_damping', 'known_weighted_velocity', 'known_weighted_force', 'weighted_gravity_coefficient', 'integration_substep_s', 'steps_per_observation'}

def coefficients(p):
    assert set(p) == KEYS, 'unexpected_target_alias_or_future_state'
    m = p['mass']
    h = p['integration_substep_s']
    n = p['steps_per_observation']
    gamma = p['known_linear_damping'] / m
    assert m > 0 and h > 0 and (type(n) is int) and (n > 0) and (p['weighted_gravity_coefficient'] > 0)
    if gamma < 1e-10:
        return (n * h, 0.5 * h * h * n * (n + 1))
    a = 1 - gamma * h
    assert 0 < a < 1
    sum_a = a * -np.expm1(n * np.log(a)) / (1 - a)
    return (h * sum_a, h * h / (1 - a) * (n - sum_a))

def distance(p, g):
    (A, B) = coefficients(p)
    return A * p['known_weighted_velocity'] + B * (p['known_weighted_force'] / p['mass'] - p['weighted_gravity_coefficient'] * g)

def gravity_from_distance(p, d):
    (A, B) = coefficients(p)
    return (p['known_weighted_force'] / p['mass'] - (d - A * p['known_weighted_velocity']) / B) / p['weighted_gravity_coefficient']
