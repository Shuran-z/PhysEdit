"""Compare box contact candidates with saved-frame geometry, not substep poses.

Diagnostic only: this tool never grants acceptance or applies a rejection cutoff.
Run in the simulation environment (NumPy and SciPy required).
"""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def signed_overlap(a, b, size_a, size_b):
    rotations = [Rotation.from_quat(o['quaternion_xyzw']).as_matrix() for o in (a, b)]
    ra, rb = rotations
    delta = np.asarray(b['position']) - a['position']
    axes = [r[:, i] for r in rotations for i in range(3)]
    axes += [np.cross(ra[:, i], rb[:, j]) for i in range(3) for j in range(3)]
    overlaps = []
    for axis in axes:
        norm = np.linalg.norm(axis)
        if norm < 1e-8:
            continue
        axis = axis / norm
        radius_a = np.abs(ra.T @ axis) @ (np.asarray(size_a) / 2)
        radius_b = np.abs(rb.T @ axis) @ (np.asarray(size_b) / 2)
        overlaps.append(float(radius_a + radius_b - abs(delta @ axis)))
    return min(overlaps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('--objects', nargs=2, required=True)
    parser.add_argument('--frames', nargs='+', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    opener = gzip.open if args.state.suffix == '.gz' else open
    with opener(args.state, 'rt', encoding='utf8') as stream:
        state = json.load(stream)
    specs = {o['name']: o['spec'] for o in state['dynamic_objects']}
    sizes = []
    for name in args.objects:
        spec = specs[name]
        if spec.get('collision_proxy') != 'box':
            raise ValueError(f'{name}: explicit box collision proxy required')
        sizes.append(spec['collision_proxy_size'])
    rows = []
    for frame in state['frames']:
        if frame['frame_index'] not in args.frames:
            continue
        objects = {o['name']: o for o in frame['objects']}
        overlap = signed_overlap(*(objects[n] for n in args.objects), *sizes)
        rows.append(dict(frame=frame['frame_index'], signed_min_axis_overlap_m=overlap,
                         box_proxies_overlap=overlap > 0))
    if {r['frame'] for r in rows} != set(args.frames):
        raise ValueError('Requested frames missing from state')
    result = dict(state_path=str(args.state), objects=args.objects, frames=rows,
                  formal_acceptance=False,
                  limitation='Saved-frame box proxies only; substep poses and visual meshes not reconstructed.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
