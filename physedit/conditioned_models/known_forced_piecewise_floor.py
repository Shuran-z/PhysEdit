"""Registered conditional motion model and image objective."""
import itertools
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.integrate import solve_ivp
from .known_floor_edge_rocking import KEYS as BASE_KEYS, condition
KEYS = BASE_KEYS | {'world_force_updates'}

def forecast_with_events(p, g):
    assert set(p) == KEYS
    (R0, axis, speed, world_r, pivot, pivot_v, _, _) = condition({k: p[k] for k in BASE_KEYS})
    updates = p['world_force_updates']
    assert updates and all((set(a) == {'time_s', 'force_world_N'} for a in updates))
    force_t = np.array([a['time_s'] for a in updates])
    force_F = np.array([a['force_world_N'] for a in updates])
    assert np.isfinite(force_t).all() and force_t[0] == 0 and np.all(np.diff(force_t) > 0) and (force_F.shape == (len(force_t), 3)) and np.isfinite(force_F).all()
    size = np.asarray(p['size'])
    mass = float(p['mass'])
    hinge = p['hinge_axis_local']
    other = [a for a in range(3) if a != hinge]
    edges = np.zeros((4, 3))
    edges[:, other] = np.asarray(list(itertools.product([-1.0, 1.0], repeat=2))) * size[other] / 2
    local_initial = R0.T @ world_r
    active = int(np.argmin(np.linalg.norm(edges - local_initial, axis=1)))
    assert np.linalg.norm(edges[active] - local_initial) < 1e-08
    I = mass / 12 * np.asarray([size[1] ** 2 + size[2] ** 2, size[0] ** 2 + size[2] ** 2, size[0] ** 2 + size[1] ** 2])
    Ic = float(I[hinge])
    times = np.asarray(p['times_s'])
    assert times[0] == 0 and np.all(np.diff(times) > 0)
    end = float(times[-1])
    P = np.full((len(times), 3), np.nan)
    Rs = np.full((len(times), 3, 3), np.nan)
    events = []
    start = 0.0
    theta = 0.0
    omega = float(speed)
    base = pivot.copy()

    def rot(a):
        return Rotation.from_rotvec(axis * a).as_matrix() @ R0

    def bounce(t):
        return max(0.0, t * pivot_v[2] - 0.5 * g * t * t)

    def translated(t, begin, origin):
        shift = (t - begin) * pivot_v
        shift = shift.copy()
        shift[2] = bounce(t) - bounce(begin)
        return origin + shift
    for event_count in range(80):
        radial = edges[active]
        radial2 = float(radial @ radial - radial[hinge] ** 2)
        Ip = Ic + mass * radial2
        damping = float(p['angular_damping'] + p['linear_damping'] * radial2)
        force_index = int(np.searchsorted(force_t, start + 1e-10, side='right') - 1)
        force = force_F[force_index]
        next_update = float(force_t[force_index + 1]) if force_index + 1 < len(force_t) else end
        segment_end = min(end, next_update)

        def rhs(t, x):
            com = -(rot(x[0]) @ radial)
            torque = float(np.cross(com, np.array([0.0, 0.0, -mass * g]) + force) @ axis)
            return [x[1], (torque - damping * x[1]) / Ip]
        candidates = [i for i in range(4) if i != active]

        def contact(t, x):
            R = rot(x[0])
            return float(min(((R @ (edges[i] - radial))[2] for i in candidates)))
        contact.terminal = True
        contact.direction = -1
        fit = solve_ivp(rhs, [start, segment_end], [theta, omega], events=contact, dense_output=True, rtol=1e-10, atol=1e-12, max_step=0.0005)
        assert fit.success
        stop = float(fit.t[-1])
        selected = np.flatnonzero((times >= start - 1e-11) & (times <= stop + 1e-11))
        for k in selected:
            x = fit.sol(float(times[k]))
            R = rot(float(x[0]))
            P[k] = translated(float(times[k]), start, base) - R @ radial
            Rs[k] = R
        if stop >= end - 1e-10:
            break
        if len(fit.t_events[0]) == 0:
            base = translated(stop, start, base)
            start = stop
            (theta, omega) = map(float, fit.y[:, -1])
            continue
        assert stop > start + 1e-10, 'nonadvancing_contact_event'
        (theta, omega) = map(float, fit.y[:, -1])
        R = rot(theta)
        new_active = min(candidates, key=lambda i: (R @ (edges[i] - radial))[2])
        new_radial = edges[new_active]
        point = translated(stop, start, base) - R @ radial
        new_pivot = point + R @ new_radial
        cross_radius = float(radial @ new_radial - radial[hinge] * new_radial[hinge])
        new_Ip = Ic + mass * float(new_radial @ new_radial - new_radial[hinge] ** 2)
        coefficient = (Ic + mass * cross_radius) / new_Ip
        omega_after = coefficient * omega
        events.append(dict(time_s=stop, old_edge_local=radial.tolist(), new_edge_local=new_radial.tolist(), incoming_angular_speed=omega, outgoing_angular_speed=omega_after, momentum_coefficient=coefficient, trigger='other known rectangle edge reaches current support plane'))
        start = stop
        active = new_active
        base = new_pivot
        omega = omega_after
    else:
        raise AssertionError('too_many_contact_switches')
    assert np.isfinite(P).all() and np.isfinite(Rs).all()
    vertices = np.asarray(list(itertools.product([-1.0, 1.0], repeat=3))) * size / 2
    minimum = np.asarray([(vertices @ R.T + pos)[:, 2].min() for (pos, R) in zip(P, Rs)])
    assert minimum.min() >= minimum[0] - 1e-08, 'nonactive_corner_below_support'
    return (P, Rs, events)

def forecast(p, g):
    (P, R, _) = forecast_with_events(p, g)
    return (P, R)
