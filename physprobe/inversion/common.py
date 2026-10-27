"""Shared helpers of the SAM jobs and the windowed evaluator, so that both use exactly the same camera, object
geometry and projection. Camera = the benchmark camera of each task (cams.json), with the renderer's camera
sanitising reproduced (every renderer except the T16-T20 base clamps look_at.z / position.z; limits from the config,
default 0.08 / 0.18, issue B2). Projection = shape-aware silhouette points (issue C9)."""
import gzip, json, math, os
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_closing, minimum_filter
from scipy.spatial.transform import Rotation as Rot

from paths import WORK as B, CODE, gt, WORKSPACE as W, PROJECTION, READY, KNOWN, READINESS, PREPARATION, GENERATED   # data dir (outside git) / code dir
man = json.load(open(B / 'manifest.json'))
bound = json.load(open(READY / 'bound.json'))
cams = json.load(open(PROJECTION / 'cams.json'))
T13_DIR = KNOWN / 'bound_metadata/T13_server'
NO_SANITIZE = {'T16', 'T17', 'T18', 'T19', 'T20'}
_ns = {'np': np, 'Rot': Rot}
_src = open(CODE / 'projection.py').read()
exec(_src[_src.index('def size_of(s):'):_src.index('def huber(')], _ns)
size_of, silhouette_points, boxes = _ns['size_of'], _ns['silhouette_points'], _ns['boxes']


def _load(lp):
    b = open(gt(lp), 'rb').read(); return json.loads(gzip.decompress(b) if str(lp).endswith('.gz') else b)


def recorded(clip):
    m = man[clip]
    if m.get('metadata_local'): return json.load(open(B / m['metadata_local']))
    key = m.get('metadata')
    if not key: return None
    if key.startswith('T13_server/'): return json.load(open(T13_DIR / key.split('/')[1] / 'annotation.json'))
    return _load(bound[clip][key])


def config(clip):
    f = B / 'cfg' / f'{clip}.json'
    return json.load(open(f)) if f.exists() else json.load(open(B / 't15' / f'{clip}_config.json'))


def spec(clip, name):
    for o in config(clip)['dynamic_objects']:
        s = dict(o.get('spec') or {}, **{k: v for k, v in o.items() if k != 'spec'})
        if s.get('name') == name: return s
    raise KeyError(name)


def _fixed_view(clip):
    """render block holding the benchmark camera's fixed_view"""
    want = cams.get(clip, 'cam01'); sc = clip[:3]
    if sc == 'T13':   # physics config had sync_cameras removed; take the camera from the original server config
        d = next(x for x in T13_DIR.iterdir() if x.name.startswith(json.load(open(B / 'cfg' / f'{clip}.json'))['sample_id'].replace('_rgb3d', '')))
        r = json.load(open(d / 'config.json'))['render']
        fv = next(c for c in r['sync_cameras'] if c['camera_id'].startswith(want))
        return dict(r, fixed_view=fv, resolution=fv.get('resolution', r['resolution']))
    if sc == 'T15':   # the rendered views are recorded in the metadata media binding
        meta_gz = [lp for k, lp in bound[clip].items() if k.endswith('.json.gz')][0]
        mb = _load(meta_gz)['media_binding.json']; fv = next(c for c in mb['cameras'] if c['camera_id'] == want)
        return dict(config(clip)['render'], fixed_view=fv, resolution=fv['resolution'])
    for k, lp in bound.get(clip, {}).items():   # a file of the benchmark camera itself (e.g. T03 cam03)
        if want in k.split('/')[-1] and (k.endswith('.json') or k.endswith('.json.gz')):
            d = _load(lp)
            if (d.get('render') or {}).get('fixed_view'): return d['render']
    meta = recorded(clip)
    if meta is not None and (meta.get('render') or {}).get('fixed_view'): return meta['render']
    return config(clip)['render']


def camera(clip):
    r = _fixed_view(clip); fv = r['fixed_view']; Wd, Ht = fv.get('resolution') or r['resolution']
    eye = np.array(fv['position'], float); at = np.array(fv['look_at'], float)
    if clip[:3] not in NO_SANITIZE:
        at[2] = max(at[2], float(r.get('camera_min_look_z', 0.08))); eye[2] = max(eye[2], float(r.get('camera_min_pos_z', 0.18)))
    fwd = (at - eye) / np.linalg.norm(at - eye); right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    return eye, fwd, right, up, (Ht / 2) / math.tan(math.radians(fv['fov_deg']) / 2), Wd, Ht


def initial_poses(clip, frame=4):
    """object poses [x,y,z,qx,qy,qz,qw] at the condition frame: recorded state if available (orientation from the spec
    when the record has positions only), else the first true-parameter replay"""
    meta = recorded(clip); out = {}
    if meta is not None:
        for o in meta['frames'][frame]['objects']:
            q = o.get('quaternion_xyzw')
            if q is None:
                try: q = list(Rot.from_euler('xyz', (spec(clip, o['name']).get('pose') or {}).get('euler_xyz', [0, 0, 0]), degrees=True).as_quat())
                except KeyError: q = [0, 0, 0, 1]
            out[o['name']] = [*o['position'], *q]
        return out
    run = json.load(open(B / 'truth_replays' / f'{clip}.json'))
    return {n: p[frame] for n, p in next(iter(run.values()))['poses'].items()}


def _hull(cam, pose, pts, scale):
    import cv2
    eye, fwd, right, up, F, Wd, Ht = cam
    P = np.array(pose[:3]) + pts @ Rot.from_quat(pose[3:7]).as_matrix().T - eye
    z = P @ fwd
    if np.any(z <= 1e-6): return None, None
    u = (Wd / 2 + F * (P @ right) / z) * scale; v = (Ht / 2 - F * (P @ up) / z) * scale
    return cv2.convexHull(np.stack([u, v], 1).astype(np.int32)), float(np.linalg.norm(np.array(pose[:3]) - eye))


def visibility(clip, cam, poses, names=None, scale=0.5):
    """fraction of each object's projected silhouette not covered by nearer objects (painter's algorithm over every
    visible scene object of the task config: moving objects at the given poses, fixed ones at their spec pose).
    poses: {name: [x,y,z,qx,qy,qz,qw]} for the moving objects. Static background meshes are not modelled."""
    import cv2
    Wd, Ht = int(cam[5] * scale), int(cam[6] * scale)
    items = []
    for o in config(clip)['dynamic_objects']:
        s = dict(o.get('spec') or {}, **{k: v for k, v in o.items() if k != 'spec'})
        if s.get('visualization') is False: continue
        n = s['name']
        if n in poses: pose = poses[n]
        else:
            p = s.get('pose') or {}
            if 'position' not in p: continue
            pose = [*p['position'], *Rot.from_euler('xyz', p.get('euler_xyz', [0, 0, 0]), degrees=True).as_quat()]
        try: pts = silhouette_points(s)
        except Exception: continue
        hull, depth = _hull(cam, pose, pts, scale)
        if hull is not None: items.append((depth, n, hull))
    owner = np.full((Ht, Wd), -1, np.int32)
    for k, (depth, n, hull) in enumerate(sorted(items, key=lambda x: -x[0])):   # far to near: nearer overwrite
        m = np.zeros((Ht, Wd), np.uint8); cv2.fillPoly(m, [hull], 1); owner[m > 0] = k
    out = {}
    order = sorted(items, key=lambda x: -x[0])
    for k, (depth, n, hull) in enumerate(order):
        if names is not None and n not in names: continue
        m = np.zeros((Ht, Wd), np.uint8); cv2.fillPoly(m, [hull], 1); area = int(m.sum())
        out[n] = float((owner[m > 0] == k).sum()) / area if area else 0.0
    return out


def surface_points(s, n=3000, seed=0):
    """points spread over the object's surface (local frame), area-weighted: box faces, cylinder side + caps (axis z),
    sphere; used for per-pixel occlusion (z-buffer by point splatting)"""
    rng = np.random.default_rng(seed); size = size_of(s)
    shape = s.get('shape'); proxy = s.get('collision_proxy') or s.get('collision_proxy_shape')
    if shape == 'sphere' or proxy == 'sphere':
        v = rng.normal(size=(n, 3)); return v / np.linalg.norm(v, axis=1, keepdims=True) * (size[0] / 2)
    if shape == 'cylinder' or proxy == 'cylinder':
        r, h = size[0] / 2, size[2]; side = 2 * np.pi * r * h; cap = np.pi * r * r
        k = rng.choice(3, n, p=np.array([side, cap, cap]) / (side + 2 * cap)); a = rng.uniform(0, 2 * np.pi, n)
        rr = np.where(k == 0, r, r * np.sqrt(rng.uniform(0, 1, n)))
        z = np.where(k == 0, rng.uniform(-h / 2, h / 2, n), np.where(k == 1, h / 2, -h / 2))
        return np.stack([rr * np.cos(a), rr * np.sin(a), z], 1)
    sx, sy, sz = size; areas = np.array([sy * sz, sy * sz, sx * sz, sx * sz, sx * sy, sx * sy])
    f = rng.choice(6, n, p=areas / areas.sum()); u = rng.uniform(-.5, .5, (n, 3)) * size
    ax = f // 2; sign = np.where(f % 2 == 0, 0.5, -0.5)
    u[np.arange(n), ax] = sign * size[ax]
    return u


OCC_FILL = os.environ.get('PHYSPROBE_OCC_FILL', '0') == '1'


def visible_boxes(clip, cam, traj, scale=0.25, n=3000, eps=0.004):
    """per-pixel occlusion over a trajectory. traj: {moving name: array (frames, 7)}. Every visible scene object of the
    config takes part (fixed ones at their spec pose). Returns {name: (fraction visible (frames,), visible box (frames, 4)
    in full-resolution pixels, NaN when nothing is visible)} for the moving objects in traj."""
    eye, fwd, right, up, F, Wd, Ht = cam
    W2, H2 = int(Wd * scale), int(Ht * scale)
    objs = []
    for o in config(clip)['dynamic_objects']:
        s = dict(o.get('spec') or {}, **{k: v for k, v in o.items() if k != 'spec'})
        if s.get('visualization') is False: continue
        try: pts = surface_points(s, n)
        except Exception: continue
        if s['name'] in traj: objs.append((s['name'], pts, np.asarray(traj[s['name']], float)))
        else:
            p = s.get('pose') or {}
            if 'position' not in p: continue
            objs.append((s['name'], pts, np.array([[*p['position'], *Rot.from_euler('xyz', p.get('euler_xyz', [0, 0, 0]), degrees=True).as_quat()]])))
    T = max(len(t) for _, _, t in objs)
    out = {name: (np.zeros(T), np.full((T, 4), np.nan)) for name in traj}
    for f in range(T):
        proj = []
        for name, pts, t in objs:
            pose = t[min(f, len(t) - 1)]
            P = pose[:3] + pts @ Rot.from_quat(pose[3:7]).as_matrix().T - eye
            z = P @ fwd; ok = z > 1e-6
            u = Wd / 2 + F * (P[ok] @ right) / z[ok]; v = Ht / 2 - F * (P[ok] @ up) / z[ok]
            ui = np.floor(u * scale).astype(int); vi = np.floor(v * scale).astype(int)
            inb = (ui >= 0) & (ui < W2) & (vi >= 0) & (vi < H2)
            proj.append((name, u[inb], v[inb], ui[inb], vi[inb], z[ok][inb]))
        own = {}
        for name, u, v, ui, vi, z in proj:
            d = np.full((H2, W2), np.inf); np.minimum.at(d, (vi, ui), z); own[name] = d
        for name, u, v, ui, vi, z in proj:
            if name not in traj or len(z) == 0: continue
            others = [own[o] for o in own if o != name]
            occ = np.minimum.reduce(others) if others else np.full((H2, W2), np.inf)
            if OCC_FILL:                                  # D38: close the gaps between splatted points of the occluders (interior only)
                hole = np.isinf(occ) & binary_closing(np.isfinite(occ), structure=np.ones((3, 3), bool))
                if hole.any(): occ = np.where(hole, minimum_filter(occ, size=3), occ)
            vis = z <= np.minimum(occ, own[name])[vi, ui] + eps
            cov = len(np.unique(vi * W2 + ui)); seen = len(np.unique(vi[vis] * W2 + ui[vis]))
            out[name][0][f] = seen / cov if cov else 0.0
            if vis.any(): out[name][1][f] = [u[vis].min(), v[vis].min(), u[vis].max(), v[vis].max()]
    return out
