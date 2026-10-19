"""Registered conditional motion model and image objective."""
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.integrate import solve_ivp
from gravtrace.camera import quat_to_matrix
KEYS = {'position', 'quaternion_xyzw', 'velocity', 'angular_velocity', 'size', 'mass', 'linear_damping', 'angular_damping', 'times_s', 'hinge_axis_local', 'floor_z'}

def condition(p):
    assert set(p) == KEYS
    R = quat_to_matrix(p['quaternion_xyzw'])
    size = np.asarray(p['size'])
    omega = np.asarray(p['angular_velocity'])
    v = np.asarray(p['velocity'])
    h = p['hinge_axis_local']
    assert h in [0, 1]
    axis = R[:, h]
    assert abs(axis[2]) < 0.01
    speed = float(omega @ axis)
    assert abs(speed) > 0.1 and np.linalg.norm(omega - axis * speed) < 0.03
    other = [a for a in range(3) if a != h]
    edges = []
    for a in [-1, 1]:
        for b in [-1, 1]:
            r = np.zeros(3)
            r[other] = [a * size[other[0]] / 2, b * size[other[1]] / 2]
            edges.append(r)
    world = np.einsum('ij,kj->ik', edges, R)
    r = world[np.argmin(world[:, 2])]
    pivot = np.asarray(p['position']) + r
    pivot_v = v + np.cross(omega, r)
    assert abs(pivot[2] - p['floor_z']) < 0.003
    assert np.linalg.norm(pivot_v) < 0.03
    m = p['mass']
    I = m / 12 * np.asarray([size[1] ** 2 + size[2] ** 2, size[0] ** 2 + size[2] ** 2, size[0] ** 2 + size[1] ** 2])
    radial2 = float(r @ r - (r @ axis) ** 2)
    return (R, axis, speed, r, pivot, pivot_v, float(I[h] + m * radial2), float(p['angular_damping'] + p['linear_damping'] * radial2))

def forecast(p, g):
    (R0, axis, speed, r, pivot, pivot_v, Ip, damping) = condition(p)
    t = np.asarray(p['times_s'])
    m = p['mass']

    def rhs(_, x):
        Rt = Rotation.from_rotvec(axis * x[0]).as_matrix()
        com = -Rt @ r
        torque = float(np.cross(com, [0, 0, -m * g]) @ axis)
        return [x[1], (torque - damping * x[1]) / Ip]
    fit = solve_ivp(rhs, [0, float(t[-1])], [0.0, speed], t_eval=t, rtol=1e-09, atol=1e-11, max_step=1 / 1000)
    assert fit.success
    Rs = Rotation.from_rotvec(fit.y[0, :, None] * axis).as_matrix()
    pivot_translation = t[:, None] * pivot_v
    pivot_translation[:, 2] = np.maximum(0.0, t * pivot_v[2] - 0.5 * g * t * t)
    pos = pivot + pivot_translation - np.einsum('kij,j->ki', Rs, r)
    rot = np.einsum('kij,jl->kil', Rs, R0)
    return (pos, rot)
