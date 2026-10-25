"""Batch-2 windowed known-answer evaluation (uniform method, issue D7): every tracked moving object contributes its
projected-box residuals only inside its predictability window. Same as batch 1 otherwise: free continuous time shift
(onset unknown), frame-4 appearance-offset calibration per object, Huber loss normalised by each object's frame-4 box
diagonal, noise-calibrated identifiability rule (sigma = 1.5 px), truth left out of the library.
Window of an object for a library value v: [motion start, start + (h - start) * k] with h the horizon at the truth
(horizons32.json); for gravity k = min(1, sqrt(g_true / g)) (events come earlier under stronger gravity; never
extended), otherwise k = 1. Occlusion (issue C10/D9): the prediction is the box of the object's VISIBLE part (per-pixel z-buffer over all scene
objects at the simulated poses, common2.visible_boxes); frames where less than MIN_VIS of the object is visible are
not used, and objects less than MIN_VIS visible at the condition frame are not used at all.
A 3D oracle (recorded trajectories, same windows) is reported for checking only.
Usage: python eval_batch2.py CLIP PARAM TRACKS_JSONL LIB_GLOB [LIB_GLOB ...]   e.g.
       python eval_batch2.py T11_C03 g sam2/pilot_tracks.jsonl 'libs2/LIB2_T11_C03_g_*.json'"""
import glob, json, sys
import numpy as np
import common2 as c2

ns = {'np': np}
src = open(c2.CODE / 'eval_batch1.py').read()
exec(src[src.index('def huber('):src.index('def rmse3d(')], ns)     # huber()
exec(src[src.index('def estimate('):src.index('SIGMA_PX = ')], ns)    # estimate()
huber, estimate = ns['huber'], ns['estimate']
SIGMA_PX, DELTA_3D = 1.5, 0.002
SHIFTS = np.arange(-20, 20.01, 0.25)
MIN_FRAMES = 3
MIN_VIS = 0.5


def load_tracks(path, clip):
    out = {}
    for line in open(path):
        r = json.loads(line); c, n = r['id'].split('__', 1)
        if c != clip: continue
        tr = r['tracks'][n]; nfr = max(tr['frames']) + 1
        a = np.full((nfr, 4), np.nan)
        for f, b in zip(tr['frames'], tr['xyxy']):
            if b is not None: a[f] = b
        out[n] = a
    return out


def windowed(sim, obs, d, hi):
    """observation frames t >= 4 matched to simulation frames s = t + d with 4 <= s <= hi (linear interpolation)"""
    t = np.arange(4, len(obs)); s = t + d
    ok = (s >= 4) & (s <= min(hi, len(sim) - 1)) & ~np.isnan(obs[t, 0])
    s0 = np.floor(s[ok]).astype(int); w = (s[ok] - s0)[:, None]; s1 = np.minimum(s0 + 1, len(sim) - 1)
    pred = (1 - w) * sim[s0] + w * sim[s1]; good = ~np.isnan(pred[:, 0])   # NaN = object not visible enough in the simulation
    return t[ok][good], pred[good]


def loss_for(sim_boxes, obs_all, his, d):
    """sum over objects of (object's mean Huber loss / its noise level 2(sigma/d0)^2): every object counts by its own
    resolving power, independent of how many frames it has (a long, insensitive track must not dilute a short,
    sensitive one, T13); for one object this is batch 1's rule (band = loss within 1 of the minimum)"""
    tot = 0.0; used = 0
    for n, obs in obs_all.items():
        sb = sim_boxes[n]
        if np.isnan(sb[4, 0]) or np.isnan(obs[4, 0]): continue
        o = obs - (obs[4] - sb[4])   # frame-4 appearance offset calibration
        t, pred = windowed(sb, o, d, his[n])
        if len(t) < MIN_FRAMES: continue
        d0 = np.linalg.norm(obs[4, 2:] - obs[4, :2])
        tot += float(huber((pred - o[t]) / d0).sum(axis=1).mean()) / (2 * (SIGMA_PX / d0) ** 2); used += 1
    return (tot, used) if used else (np.inf, 0)


if __name__ == '__main__':
    clip, param, tracks = sys.argv[1], sys.argv[2], sys.argv[3]
    lib = {}
    for pat in sys.argv[4:]:
        for f in sorted(glob.glob(str(c2.B / pat)) or glob.glob(pat)):
            for v, r in json.load(open(f)).items():
                if r.get('poses') is not None or v not in lib: lib[v] = r
    hz = json.load(open(c2.B / 'horizons32.json'))[clip]['objects']
    cam = c2.camera(clip); p4 = c2.initial_poses(clip)
    movers0 = {n: np.array([p]) for n, p in p4.items() if not c2.spec(clip, n).get('fixed')}
    vis4 = {n: float(v[0][0]) for n, v in c2.visible_boxes(clip, cam, movers0).items()}
    use = [n for n, o in hz.items() if o['usable_frames'] >= 2 and o['moved_in_window_cm'] * 10 >= 2 * o['threshold_mm'] and vis4.get(n, 0) >= MIN_VIS]
    if tracks == 'none':   # oracle only: the same objects SAM would track, no SAM
        obs_all = {n: np.full((300, 4), np.nan) for n in use}
    else:
        obs_all = {n: o for n, o in load_tracks(tracks, clip).items() if n in use}
    cfg = c2.config(clip); truth = -cfg['scene_overrides']['gravity'][2] if param == 'g' else None
    meta = c2.recorded(clip)
    vs, ys, o3 = [], [], []
    for v, r in sorted(lib.items(), key=lambda kv: float(kv[0])):
        if r.get('poses') is None: continue
        v = float(v); k = min(1.0, np.sqrt(truth / v)) if param == 'g' else 1.0
        his = {n: int(hz[n]['start'] + (hz[n]['horizon'] - hz[n]['start']) * k) for n in obs_all}
        vb = c2.visible_boxes(clip, cam, {n: np.array(p) for n, p in r['poses'].items()})
        sim_boxes = {n: np.where((vb[n][0] >= MIN_VIS)[:, None], vb[n][1], np.nan) for n in obs_all}
        best = min((loss_for(sim_boxes, obs_all, his, d) for d in SHIFTS), key=lambda x: x[0]) if tracks != 'none' else (np.nan, 0)
        vs.append(v); ys.append(best[0])
        if meta is not None:   # 3D oracle on the same windows
            errs = []
            for d in SHIFTS:
                e = []
                for n in obs_all:
                    R = np.array([next(o['position'] for o in fr['objects'] if o['name'] == n) for fr in meta['frames']])
                    P = np.array(r['poses'][n])[:, :3]
                    t, pred = windowed(P, R, d, his[n]); e.append(float(np.mean(np.sum((pred - R[t]) ** 2, axis=1))) / DELTA_3D ** 2) if len(t) >= MIN_FRAMES else None
                e = [x for x in e if x is not None]
                errs.append(sum(e) if e else np.inf)
            o3.append(min(errs))
    vs, ys = np.array(vs), np.array(ys)
    res = dict(clip=clip, param=param, truth=truth, objects=list(obs_all), visible_at_frame4=vis4, windows={n: (hz[n]['start'], hz[n]['horizon']) for n in obs_all}, n_lib=len(vs))
    if tracks != 'none':
        # losses are already divided by each object's noise level -> indistinguishable = within 1 of the minimum
        res.update(sam=estimate(vs, ys, 1.0), sam_curve=[[float(a), float(b)] for a, b in zip(vs, ys)])
    if o3: res['oracle'] = estimate(vs, np.array(o3), 1.0)   # normalised: within 1 of the minimum = indistinguishable
    fmt = lambda e: f"{e['est']:.4g} ({100 * (e['est'] - truth) / truth:+.1f}%) band[{e['band'][0]:.3g},{e['band'][1]:.3g}]" if e['kind'] == 'point' else f"{e['kind']} [{e['band'][0]:.3g},{e['band'][1]:.3g}]"
    print(f"{clip} {param} truth {truth} | objects {[n.split('_', 1)[1] for n in obs_all]} windows {res['windows']} | lib {len(vs)} | SAM {fmt(res['sam']) if 'sam' in res else '-'}" + (f" | 3D oracle {fmt(res['oracle'])}" if o3 else ''))
    if tracks == 'none': res['oracle_curve'] = [[float(a), float(b)] for a, b in zip(vs, o3)]
    out = c2.B / 'results2'; out.mkdir(exist_ok=True)
    json.dump(res, open(out / f"{clip}_{param}{'_oracle' if tracks == 'none' else ''}.json", 'w'), indent=1, default=float)
