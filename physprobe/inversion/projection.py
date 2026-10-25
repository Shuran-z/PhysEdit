"""Batch-1 known-answer evaluation (onset unknown, truth not in library, primary mover only, SAM3.1 observations).

For each (scene, parameter): projected-box loss vs SAM track with a continuous free time shift, explosion filter,
unweighted local quadratic fit in log-parameter, bound detection; plus a 3D-trajectory oracle with the same rules.
"""
import gzip, json, math, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as Rot

W = Path('/Users/zhangshuran/data/projects/PhysProbe/.local-research/evaluation/core100_inversion_workspace')
B = W / 'trial/batch1'
bound = json.load(open(W / 'ready/s4_bound.json'))
cams = json.load(open(B / 'cams.json'))
plan = json.load(open(B / 'lib_plan.json'))
SANITIZE_SCENES = {'T01', 'T02', 'T03', 'T04', 'T05', 'T11', 'T15'}
SHIFTS = np.arange(-20, 20.01, 0.25)


def load_meta(clip):
    return json.loads(gzip.decompress(open([lp for k, lp in bound[clip].items() if k.endswith('.json.gz')][0], 'rb').read()))


def camera(clip):
    meta = load_meta(clip); cm = meta
    for k, lp in bound[clip].items():
        if cams[clip] in k.split('/')[-1]:
            b = open(lp, 'rb').read(); b = gzip.decompress(b) if lp.endswith('.gz') else b
            d = json.loads(b)
            if (d.get('render') or {}).get('fixed_view'): cm = d; break
    fv = cm['render']['fixed_view']; Wd, Ht = cm['render']['resolution']
    eye = np.array(fv['position'], float); at = np.array(fv['look_at'], float)
    if clip[:3] in SANITIZE_SCENES:
        at[2] = max(at[2], float(cm['render'].get('camera_min_look_z', 0.08))); eye[2] = max(eye[2], float(cm['render'].get('camera_min_pos_z', 0.18)))
    fwd = (at - eye) / np.linalg.norm(at - eye); right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    return eye, fwd, right, up, (Ht / 2) / math.tan(math.radians(fv['fov_deg']) / 2), Wd, Ht


def size_of(s):
    if s.get('size'): return np.array(s['size'], float) * np.array((s.get('pose') or {}).get('scale', [1, 1, 1]), float)
    if s.get('collision_proxy_size'): return np.array(s['collision_proxy_size'], float)
    r = s.get('radius') or s.get('collision_proxy_radius'); h = s.get('height') or s.get('collision_proxy_height') or (2 * r)
    return np.array([2 * r, 2 * r, h], float)


def silhouette_points(s):
    """Local-frame points whose projections bound the object's image silhouette. Box: 8 corners. Cylinder (axis = local z,
    visual radius = size x/2): two rim circles; the corners of its bounding box would rotate with the object and swing the
    projected width between 1x and 1.41x the diameter while the real silhouette stays constant (T17/T19 cans).
    Sphere: dense surface sample (the perspective silhouette of a sphere touches its surface)."""
    size = size_of(s); shape = s.get('shape'); proxy = s.get('collision_proxy') or s.get('collision_proxy_shape')
    if shape == 'sphere' or proxy == 'sphere':
        n = 400; k = np.arange(n) + 0.5; phi = np.arccos(1 - 2 * k / n); th = np.pi * (1 + 5 ** 0.5) * k
        return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1) * (size[0] / 2)
    if shape == 'cylinder' or proxy == 'cylinder':
        a = np.linspace(0, 2 * np.pi, 72, endpoint=False); r = size[0] / 2
        return np.concatenate([np.stack([r * np.cos(a), r * np.sin(a), np.full_like(a, z)], 1) for z in (-size[2] / 2, size[2] / 2)])
    return np.array([[a, b, d] for a in (-.5, .5) for b in (-.5, .5) for d in (-.5, .5)]) * size


def boxes(cam, poses, pts):
    eye, fwd, right, up, F, Wd, Ht = cam
    out = []
    for p in poses:
        P = np.array(p[:3]) + pts @ Rot.from_quat(p[3:7]).as_matrix().T - eye
        u = Wd / 2 + F * (P @ right) / (P @ fwd); v = Ht / 2 - F * (P @ up) / (P @ fwd)
        out.append([u.min(), v.min(), u.max(), v.max()])
    return np.array(out)


def huber(x, k=0.02):
    a = np.abs(x); return np.where(a <= k, 0.5 * x * x, k * (a - 0.5 * k))


def shifted(sim, d, n):
    t = np.arange(4, n); s = t + d; ok = (s >= 4) & (s <= len(sim) - 1)
    s0 = np.floor(s[ok]).astype(int); w = (s[ok] - s0)[:, None]; s1 = np.minimum(s0 + 1, len(sim) - 1)
    return t[ok], (1 - w) * sim[s0] + w * sim[s1]


def box_loss(sim, obs, d):
    # condition-frame calibration: the frame-4 pose is known, so the frame-4 observed-minus-projected box offset is a
    # fixed appearance offset (silhouette vs projected box); remove it before comparing
    if not np.isnan(obs[4, 0]):
        obs = obs - (obs[4] - sim[4])
    t, pred = shifted(sim, d, len(obs)); ok = ~np.isnan(obs[t, 0])
    if ok.sum() < 30: return np.inf
    d0 = np.linalg.norm(obs[4, 2:] - obs[4, :2])
    return float(huber((pred[ok] - obs[t[ok]]) / d0).sum(axis=1).mean())


def rmse3d(sim, ref, d):
    t, pred = shifted(sim, d, len(ref)); return float(np.sqrt(np.mean(np.sum((pred - ref[t]) ** 2, axis=1))))


def estimate(vs, ys, delta):
    """Noise-calibrated identifiability: values whose loss is within  of the minimum cannot be told apart.
    band = all such values; touching the grid edge -> bound only; otherwise point estimate = local quadratic vertex
    (unweighted, log-parameter), clipped to the band."""
    i = int(np.argmin(ys)); m = ys <= ys[i] + delta
    band = (float(vs[m].min()), float(vs[m].max()))
    if m.all(): return dict(kind='unidentifiable', est=None, band=band)
    if m[0] and not m[-1]: return dict(kind='upper_bound', est=None, band=band)
    if m[-1] and not m[0]: return dict(kind='lower_bound', est=None, band=band)
    if band[1] / band[0] > 1.25: return dict(kind='interval', est=None, band=band)  # wide basin: interval only (low identifiability)
    k = np.where(m)[0]; lo, hi = max(k.min() - 1, 0), min(k.max() + 1, len(vs) - 1)
    sel = np.arange(lo, hi + 1)
    if len(sel) < 3: sel = np.argsort(np.abs(np.arange(len(vs)) - i))[:3]
    a, b, c = np.polyfit(np.log(vs[sel]), ys[sel], 2)
    e = float(np.exp(-b / (2 * a))) if a > 0 else float(vs[i])
    lo_v = float(vs[max(k.min() - 1, 0)]); hi_v = float(vs[min(k.max() + 1, len(vs) - 1)])
    return dict(kind='point', est=min(max(e, lo_v), hi_v), band=band)  # vertex may lie between the band and its neighbouring grid points


SIGMA_PX = 1.5      # observation noise (G1-level), pixels
DELTA_3D = 0.002    # replay noise (G0-level), metres


def delta_box(obs):
    d0 = np.linalg.norm(obs[4, 2:] - obs[4, :2])
    return 2 * (SIGMA_PX / d0) ** 2   # loss change of a sigma-level shift on the 4 box coordinates (Huber, quadratic zone)


def sam_obs():
    out = {}
    for f in sorted((W / 'trial/batch1/sam').glob('tracks_*.jsonl')):
        for line in open(f):
            r = json.loads(line); clip, n = r['id'].split('__')
            a = np.full((210, 4), np.nan)
            for fr, b in zip(r['tracks'][n]['frames'], r['tracks'][n]['xyxy']):
                if b is not None: a[fr] = b
            out[(clip, n)] = a
    return out


if __name__ == '__main__':
    obs_all = sam_obs()
    results = []
    for j in plan:
        clip, param, truth, primary = j['clip'], j['param'], j['truth'], j['movers'][0]
        lib_path = B / 'libs' / f"LIB_{clip}_{param}.json"
        if not lib_path.exists(): continue
        lib = json.load(open(lib_path)); meta = load_meta(clip)
        for extra in sorted([*(B / 'libs').glob(f'REF_{clip}_{param}_*.json'), *(B / 'libs').glob(f'R3_{clip}_{param}_*.json')]):
            for v, r in json.load(open(extra)).items():
                if r['poses'] is not None or v not in lib: lib[v] = r
        ref = np.array([[*next(o['position'] for o in fr['objects'] if o['name'] == n), *next(o for o in fr['objects'] if o['name'] == n).get('quaternion_xyzw', [0, 0, 0, 1])] for fr in meta['frames'] for n in [primary]])
        refz = {n: max(next(o['position'] for o in fr['objects'] if o['name'] == n)[2] for fr in meta['frames']) for n in j['movers']}
        spec = next(dict(o.get('spec') or {}, **{k: v for k, v in o.items() if k != 'spec'}) for o in meta['dynamic_objects'] if o['name'] == primary)
        cam = camera(clip); pts = silhouette_points(spec)
        vs, sims, dropped = [], [], []
        for v, r in sorted(lib.items(), key=lambda kv: float(kv[0])):
            if r['poses'] is None: dropped.append((float(v), 'no_output')); continue
            if any(np.array(r['poses'][n])[:, 2].max() > refz[n] + 0.3 for n in r['poses'] if n in refz):
                dropped.append((float(v), 'exploded')); continue
            vs.append(float(v)); sims.append(np.array(r['poses'][primary]))
        vs = np.array(vs)
        row = dict(clip=clip, param=param, truth=truth, primary=primary, n_lib=len(vs), dropped=dropped)
        o3 = np.array([min(rmse3d(s[:, :3], ref[:, :3], d) for d in SHIFTS) for s in sims])
        row['oracle'] = estimate(vs, o3, DELTA_3D); row['oracle_curve'] = [[float(v), float(y)] for v, y in zip(vs, o3)]; row['oracle_delta'] = DELTA_3D
        obs = obs_all.get((clip, primary))
        if obs is not None:
            ys = np.array([min(box_loss(boxes(cam, s, pts), obs, d) for d in SHIFTS) for s in sims])
            row['sam'] = estimate(vs, ys, delta_box(obs)); row['sam_curve'] = [[float(v), float(y)] for v, y in zip(vs, ys)]; row['sam_delta'] = delta_box(obs)
        results.append(row)
        fmt = lambda r: '-' if r is None else (f"{r['est']:.4g} ({100 * (r['est'] - truth) / truth:+.1f}%) band[{r['band'][0]:.3g},{r['band'][1]:.3g}]" if r['kind'] == 'point' else f"{r['kind']} [{r['band'][0]:.3g},{r['band'][1]:.3g}]")
        print(f"{clip} {param:2s} truth {truth:<9.4g} | lib {len(vs)} drop {len(dropped)} | 3D oracle {fmt(row['oracle'])} | SAM {fmt(row.get('sam'))}", flush=True)
    json.dump(results, open(B / 'results_batch1.json', 'w'), indent=1, default=float)
