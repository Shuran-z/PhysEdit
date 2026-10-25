"""Evaluator v3 (2026-10-24): one method for reference AND generated videos, any frame rate / resolution / length.
Physical clock: simulation frame j <-> t = j * dt (dt = the task's physical seconds per reference frame). Observation frame k
<-> t = 4 dt + (k - k_c) dt_obs, k_c = the video's condition frame (4 for references, 0 for generated videos), dt_obs =
dt for references and playback_vs_physics / fps for generated videos (they keep the reference's playback convention,
T06/T09/T10 0.6x slow motion; issue log E2). A free continuous time shift d (|d| <= 20 sim frames, step 0.25) covers
the unknown onset. Pixels: simulated visible-part boxes (camera pixels, common.visible_boxes, cached per library
simulation) are mapped into the video by x' = a x + b (references: pure resolution scaling; generated videos: the
registration of the condition image onto their first frame); then the per-object condition-frame offset calibration.
Per object: Huber loss of the box residuals over the frames inside its predictability window [4, start + (h - start) k]
(k = min(1, sqrt(g_truth / g)) for gravity, else 1; visible >= MIN_VIS in the simulation; SAM box present), normalised by
its noise level 2 (sigma / d0)^2; objects with fewer than MIN_FRAMES frames at zero shift are not used, and a shift that
drops a used object below MIN_FRAMES is not allowed. Loss(v) = min over shifts of the sum over objects; estimate(): values
within 1 of the minimum are indistinguishable (point estimate / interval / bound / unidentifiable).
Library: lib3 (libs3/LIB3_<lib>_<chunk>.json), truth never in it; --with-truth adds the true-parameter replays (generated
videos only). Usage:
  python evaluator.py ref [CLIP ...]          known-answer test on the reference videos (lean SAM tracks) -> results3/ref_*.json
  (generated videos: see eval_generated.py, which calls evaluate())"""
import glob, json, math, os, sys
from multiprocessing import get_context
from pathlib import Path
import numpy as np
import common as c2

B = c2.B
ns = {'np': np}
_src = open(c2.CODE / 'projection.py').read()
exec(_src[_src.index('def huber('):_src.index('def rmse3d(')], ns)
exec(_src[_src.index('def estimate('):_src.index('SIGMA_PX = ')], ns)
huber, estimate = ns['huber'], ns['estimate']
SIGMA_PX, MIN_FRAMES, MIN_VIS = 1.5, 3, 0.5
_cal = B / 'results3' / 'band_calibration.json'
DELTA = json.load(open(_cal))['delta'] if _cal.exists() else 1.0   # identifiability threshold (D13: empirical calibration)
E_BEYOND = 1.0   # per-frame loss of frames inside the truth window but beyond a value's own (shorter) window
OBJ_MAX = 5.0    # at the joint optimum an object above this is inconsistent with the others: drop the worst, re-fit
KSCALE = os.environ.get('PHYSPROBE_KSCALE', '0') == '1'   # D26: every library value is compared on the same (truth) window; 1 = old sqrt(g_truth/g) shortening
REF_OUT = os.environ.get('PHYSPROBE_REF_OUT', 'results3')   # output directory of the reference run
GATE = 10.0   # an object whose best fit over the whole library exceeds this (~3 sigma rms) is not explained by any value
SHIFTS = np.arange(-20, 20.01, 0.25)
HZ = json.load(open(B / ('horizons33.json' if (B / 'horizons33.json').exists() else 'horizons32.json')))
RD = {json.loads(l)['clip_id']: json.loads(l) for l in open(c2.W.parent / 'core100_known_condition_readiness_20261021_v1/readiness100.jsonl')}
LIBS = json.load(open(B / 'lib3_libraries.json'))['libraries']
LIBMAP = {(m, L['param']): L for L in LIBS for m in L['members']}
CACHE = B / 'libbox3'; CACHE.mkdir(exist_ok=True)


def estimate_band(vs, ys, delta=1.0):
    """Noise-calibrated identifiability (D13, D25). Every library value whose loss is within delta of the minimum is
    indistinguishable from it, wherever it lies: a chaotic or multimodal loss curve gives a wide band, never a sharp
    spurious minimum from one lucky simulation. On the continuous axis the band is that set's extent, extended by a
    quadratic in log(value) fitted at the minimum where it stays within delta, and clipped to the nearest grid values
    beyond the set that exceed the threshold. Set touching the low / high grid edge -> upper / lower bound; both edges
    -> unidentifiable; band wider than x1.25 -> interval; otherwise point = vertex of the quadratic."""
    vs, ys = np.asarray(vs, float), np.asarray(ys, float)
    o = np.argsort(vs); vs, ys = vs[o], ys[o]; n = len(vs)
    i = int(np.argmin(ys)); m = ys <= ys[i] + delta; idx = np.where(m)[0]; jlo, jhi = int(idx.min()), int(idx.max())
    if m[0] and m[-1]: return dict(kind='unidentifiable', est=None, band=(float(vs[0]), float(vs[-1])))
    if m[0]: return dict(kind='upper_bound', est=None, band=(float(vs[0]), float(vs[min(jhi + 1, n - 1)])))
    if m[-1]: return dict(kind='lower_bound', est=None, band=(float(vs[max(jlo - 1, 0)]), float(vs[-1])))
    lo_lim, hi_lim = float(vs[jlo - 1]), float(vs[jhi + 1])
    sel = np.arange(max(i - 2, 0), min(i + 3, n))
    x = np.log(vs[sel]); w = np.exp(-(ys[sel] - ys[i]) / (4 * delta))        # weight the points near the minimum
    a, b, c = np.polyfit(x, ys[sel], 2, w=w)
    llo, lhi = math.log(lo_lim), math.log(hi_lim)
    if a > 0 and np.isfinite([a, b]).all():
        x0 = -b / (2 * a); hw = math.sqrt(delta / a)          # clip in log space before exp (a flat curve gives a huge half width)
        est = math.exp(min(max(x0, llo), lhi)); qlo, qhi = math.exp(min(max(x0 - hw, llo), lhi)), math.exp(min(max(x0 + hw, llo), lhi))
    else:
        est = float(vs[i]); qlo, qhi = float(vs[jlo]), float(vs[jhi])
    band = (max(min(qlo, float(vs[jlo])), lo_lim), min(max(qhi, float(vs[jhi])), hi_lim))
    est = min(max(est, band[0]), band[1])
    kind = 'interval' if band[1] / band[0] > 1.25 else 'point'
    return dict(kind=kind, est=est if kind == 'point' else None, center=est, band=(float(band[0]), float(band[1])))


def clock(clip):
    r = RD[clip]; return float(r['physical_seconds_per_frame']), float(r['playback_vs_physics'])


def generated_dt(clip, fps, mode='realtime'):
    """physical seconds per frame of a generated video (E2). realtime: 1 / fps — the prompts give physical values
    (m/s^2, m/s) and never ask for slow motion, so the clip is judged at its playback speed; reference: the reference
    video's playback convention (T06/T09/T10 are 0.6x slow motion), used for synthetic videos resampled from references"""
    _, pvp = clock(clip)
    return (pvp if mode == 'reference' else 1.0) / fps


def usable(clip):
    """uniform object rule (as make_sam_jobs2): >= 2 usable frames and >= 2x the horizon threshold of motion in the window"""
    return [n for n, o in HZ[clip]['objects'].items() if o['usable_frames'] >= 2 and o['moved_in_window_cm'] * 10 >= 2 * o['threshold_mm']]


def carrier_of(clip, param):
    """the object that carries the parameter: the object given the initial speed (v), the moving object of the main
    contact pair (mu); gravity has none"""
    L = LIBMAP.get((clip, param))
    if not L: return None
    if param == 'v': return L.get('speed_object')
    if param == 'mu' and L.get('friction_objects'): return L['friction_objects'].split(',')[0]
    return None


def apply_carrier_rule(res):
    """D23 majority rule, then D22: a result whose carrier object was observable but rejected (not explained / inconsistent) does not measure the
    parameter's main effect -> kind not_explained; a carrier that is not usable at all (no motion in its window) leaves
    the result as measured through the other objects (flag indirect)"""
    car = carrier_of(res['clip'], res['param']); res['carrier'] = car
    diag = res.get('object_diagnostics') or {}
    st = diag.get(car, {}).get('status') if car else None
    n_rej = sum(d['status'] in ('not_explained', 'inconsistent') for d in diag.values())
    n_use = sum(d['status'] == 'used' for d in diag.values())
    if n_use and n_rej >= n_use and res.get('kind') not in ('not_explained', 'no_observation'):
        # D23: an estimate must be supported by at least as many objects as reject it
        res.update(kind_before_object_rules=res['kind'], kind='not_explained', est=None, truth_in_band=False, rejected_by='majority')
        res.pop('err_pct', None)
        return res
    if car and st in ('not_explained', 'inconsistent') and res.get('kind') not in ('not_explained', 'no_observation'):
        res.update(kind_before_object_rules=res['kind'], kind='not_explained', est=None, truth_in_band=False, rejected_by='carrier')
        res.pop('err_pct', None)
    elif car and st not in ('used', None) and res.get('kind') not in ('not_explained', 'no_observation'):
        res['indirect'] = True
    elif car and st is None:
        res['indirect'] = True
    return res


def truth_of(clip, param):
    L = LIBMAP[(clip, param)]
    return L['truths'][L['members'].index(clip)]


def _boxes_job(args):
    clip, tag, v, names, poses = args
    f = CACHE / f'{tag}__{v}.npz'
    if f.exists(): return
    cam = c2.camera(clip)
    vb = c2.visible_boxes(clip, cam, {n: np.array(p) for n, p in poses.items()})
    np.savez_compressed(f, **{f'{n}__frac': vb[n][0] for n in names if n in vb}, **{f'{n}__box': vb[n][1] for n in names if n in vb})


def library(clip, param, with_truth=False, workers=8):
    """[(value, {name: (frac (F,), box (F, 4))})] for the task's library, visible boxes cached in libbox3/"""
    L = LIBMAP[(clip, param)]
    names = sorted({n for m in L['members'] for n in usable(m)})
    files = sorted(glob.glob(str(B / 'libs3' / f"LIB3_{L['lib']}_*.json")))   # main chunks 00.., half steps h*, bisection b*
    if with_truth:
        files += sorted(glob.glob(str(B / 'g0' / f'G0b2_{clip}.json')))
    todo, items = [], []
    for f in files:
        tag = Path(f).stem
        for v, r in json.load(open(f)).items():
            if r.get('poses') is None: continue
            val = float(v) if not tag.startswith('G0') else truth_of(clip, param)
            items.append((val, tag, v)); todo.append((clip, tag, v, names, r['poses']))
    todo = [t for t in todo if not (CACHE / f'{t[1]}__{t[2]}.npz').exists()]
    if todo:
        with get_context("fork").Pool(workers) as p: p.map(_boxes_job, todo, chunksize=1)   # fork: entry scripts need no main guard
    out = []
    for val, tag, v in sorted(items):
        z = np.load(CACHE / f'{tag}__{v}.npz')
        out.append((val, {n: (z[f'{n}__frac'], z[f'{n}__box']) for n in names if f'{n}__frac' in z.files}))
    return out


def load_tracks_indexed(path, clip):
    """{name: boxes (frames, 4)} indexed by video frame (NaN = missing), for reference tracks 'CLIP__NAME'"""
    out = {}
    for line in open(path):
        r = json.loads(line); c, n = r['id'].split('__', 1)
        if c != clip: continue
        tr = r['tracks'][n]; a = np.full((max(tr['frames']) + 1, 4), np.nan)
        for f, b in zip(tr['frames'], tr['xyxy']):
            if b is not None: a[f] = b
        out[n] = a
    return out


def load_obs(path, video_id):
    """{name: (frame indices (K,), boxes (K, 4) NaN = missing)}, condition frame index"""
    out, kc = {}, None
    for line in open(path):
        r = json.loads(line); vid, n = r['id'].split('__', 1)
        if vid != video_id: continue
        tr = r['tracks'][n]; kc = r.get('prompt_frame', 4) if kc is None else kc
        out[n] = (np.array(tr['frames']), np.array([b if b is not None else [np.nan] * 4 for b in tr['xyxy']], float))
    return out, kc


def refine_library(lib, names, n_sub=7, max_rel=0.5):
    """Parameter-space interpolation between adjacent library simulations (the predictability windows are, by the D7 rule,
    where trajectories depend smoothly on the parameter): n_sub log-spaced values inside each interval, visible boxes and
    visible fractions blended linearly. An interval is only filled when the two neighbouring box tracks differ by at most
    max_rel of their own motion amplitude for every object (no bifurcation between them); otherwise it stays a gap."""
    lib = sorted(lib, key=lambda t: t[0]); out = []
    for (v0, b0), (v1, b1) in zip(lib, lib[1:]):
        out.append((v0, b0))
        common = [n for n in names if n in b0 and n in b1]
        if not common: continue
        ok = True
        for n in common:
            F = min(len(b0[n][1]), len(b1[n][1])); x0, x1 = b0[n][1][:F], b1[n][1][:F]
            amp = max(np.nanmax(np.abs(x0 - x0[4])), np.nanmax(np.abs(x1 - x1[4])), 4.0)
            if np.nanmax(np.abs(x0 - x1)) > max_rel * amp + 2.0: ok = False; break
        if not ok: continue
        for j in range(1, n_sub + 1):
            lam = j / (n_sub + 1); v = math.exp((1 - lam) * math.log(v0) + lam * math.log(v1))
            bb = {}
            for n in common:
                F = min(len(b0[n][1]), len(b1[n][1]))
                bb[n] = ((1 - lam) * b0[n][0][:F] + lam * b1[n][0][:F], (1 - lam) * b0[n][1][:F] + lam * b1[n][1][:F])
            out.append((v, bb))
    if lib: out.append(lib[-1])
    return out


def evaluate(clip, param, obs, kc, dt_obs, scale, lib, truth, offset=(0.0, 0.0), interp=True):
    """loss curve over the library and the identifiability estimate. scale/offset: camera pixel -> video pixel."""
    dt, _ = clock(clip); hz = HZ[clip]['objects']
    a = np.array([scale[0], scale[1], scale[0], scale[1]]); b = np.array([offset[0], offset[1], offset[0], offset[1]])
    use = [n for n in usable(clip) if n in obs]
    prep = {}
    for n in use:
        k, ob = obs[n]
        if kc not in set(k.tolist()): continue
        i0 = int(np.where(k == kc)[0][0])
        if np.isnan(ob[i0, 0]): continue
        prep[n] = (4 + (k - kc) * dt_obs / dt, ob, i0, float(np.linalg.norm(ob[i0, 2:] - ob[i0, :2])))
    if interp: lib = refine_library(lib, list(prep))
    # per-object loss tables L[n][value index, shift index] (inf where the object lacks MIN_FRAMES frames)
    tables, vals = {}, []
    for vi, (v, boxes) in enumerate(lib):
        kf = min(1.0, math.sqrt(truth / v)) if (param == 'g' and KSCALE) else 1.0
        vals.append(v)
        for n, (s0, ob, i0, d0) in prep.items():
            row = np.full(len(SHIFTS), np.inf)
            if n in boxes and d0 > 0:
                frac, sb = boxes[n]
                sbv = np.where((frac >= MIN_VIS)[:, None], sb * a + b, np.nan); F = len(sbv)
                if not np.isnan(sbv[4, 0]):
                    o = ob - (ob[i0] - sbv[4])
                    hi_t = min(int(hz[n]['horizon']), F - 1)                                   # the truth's window: same frames for every value
                    hi = min(int(hz[n]['start'] + (hz[n]['horizon'] - hz[n]['start']) * kf), F - 1)
                    S = s0[None, :] + SHIFTS[:, None]
                    in_t = (S >= 4) & (S <= hi_t) & ~np.isnan(o[:, 0])[None, :]
                    in_v = in_t & (S <= hi)
                    Sc = np.clip(S, 0, F - 1); f0 = np.floor(Sc).astype(int); w = (Sc - f0)[..., None]; f1 = np.minimum(f0 + 1, F - 1)
                    pred = (1 - w) * sbv[f0] + w * sbv[f1]
                    good = in_v & ~np.isnan(pred[..., 0])
                    beyond = in_t & ~in_v                                                    # value cannot predict here: counted at noise level
                    rr = np.where(good[..., None], (pred - o[None]) / d0, 0.0)
                    lf = huber(rr).sum(-1) / (2 * (SIGMA_PX / d0) ** 2)
                    cnt = good.sum(1) + beyond.sum(1)
                    per = (np.where(good, lf, 0.0).sum(1) + E_BEYOND * beyond.sum(1)) / np.maximum(cnt, 1)
                    moving = (good & (S >= max(hz[n]['start'], 4))).sum(1)                  # frames after motion start
                    row = np.where((cnt >= MIN_FRAMES) & (moving >= MIN_FRAMES), per, np.inf)
                    z = np.argmin(np.abs(SHIFTS))
                    if moving[z] < MIN_FRAMES and moving.max() < MIN_FRAMES: row[:] = np.inf
            tables.setdefault(n, []).append(row)
    tables = {n: np.array(t) for n, t in tables.items()}
    vals = np.array(vals)
    # objects: observable (finite somewhere) and explainable (best fit over the whole library within GATE)
    diag = {}
    for n, t in tables.items():
        best = float(np.min(t)) if np.isfinite(t).any() else float('inf')
        diag[n] = dict(best_loss=round(best, 2), status='used' if best <= GATE else ('not_observable' if not np.isfinite(best) else 'not_explained'))
    used_objs = [n for n in tables if diag[n]['status'] == 'used']
    def joint(objs):
        tot = sum(tables[n] for n in objs); keep = np.isfinite(tot).any(1)
        return tot, keep
    while len(used_objs) >= 2:                                    # drop objects inconsistent with the joint optimum
        tot, keep = joint(used_objs)
        if not keep.any(): break
        vi, di = np.unravel_index(np.argmin(np.where(np.isfinite(tot), tot, np.inf)), tot.shape)
        per = {n: float(tables[n][vi, di]) for n in used_objs}
        worst = max(per, key=per.get)
        if per[worst] <= OBJ_MAX: break
        used_objs = [n for n in used_objs if n != worst]; diag[worst]['status'] = 'inconsistent'; diag[worst]['loss_at_joint'] = round(per[worst], 2)
    vals_out, losses, shifts = [], [], []
    if used_objs:
        tot, keep = joint(used_objs)
        for vi in np.where(keep)[0]:
            i = int(np.argmin(tot[vi])); vals_out.append(float(vals[vi])); losses.append(float(tot[vi, i])); shifts.append(float(SHIFTS[i]))
    vals = vals_out
    res = dict(clip=clip, param=param, truth=truth, objects=used_objs or [], object_diagnostics=diag, n_lib=len(vals), delta=DELTA)
    if len(vals) >= 3 and np.isfinite(losses).any():
        vs, ys = np.array(vals), np.array(losses)
        e = estimate_band(vs, np.where(np.isfinite(ys), ys, np.nanmax(ys[np.isfinite(ys)]) + 1e6), DELTA)
        res.update(e, curve=[[float(x), float(y), float(s)] for x, y, s in zip(vs, ys, shifts)])
        if e.get('est') is not None and truth: res['err_pct'] = 100 * (e['est'] - truth) / truth
        lo, hi = e['band']
        if e['kind'] == 'upper_bound': lo = 0.0                       # one-sided: value <= hi
        if e['kind'] == 'lower_bound': hi = float('inf')              # one-sided: value >= lo
        res['truth_in_band'] = bool(truth and lo <= truth <= hi)
    else:
        unexplained = any(d['status'] in ('not_explained', 'inconsistent') for d in diag.values())
        res.update(kind='not_explained' if unexplained else 'no_observation', est=None, band=None)   # no value explains the observed motion
    return apply_carrier_rule(res)


def ref_meta(clip):
    import cv2
    v = B / 'sam_lean' / 'ref99' / 'videos' / f'{clip}.mp4'
    cap = cv2.VideoCapture(str(v)); W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT); cap.release()
    cam = c2.camera(clip); dt, _ = clock(clip)
    return dict(dt_obs=dt, scale=(W / cam[5], H / cam[6]))


if __name__ == '__main__' and sys.argv[1] == 'ref':
    tracks = B / 'sam_lean' / 'ref99' / 'tracks_lean.jsonl'
    clips = sys.argv[2:] or sorted({m for L in LIBS for m in L['members']})
    (B / REF_OUT).mkdir(exist_ok=True); rows = []
    for clip in clips:
        obs, kc = load_obs(tracks, clip)
        if not obs: print(clip, 'no tracks'); continue
        meta = ref_meta(clip)
        for param in ('g', 'mu', 'v'):
            if (clip, param) not in LIBMAP: continue
            lib = library(clip, param)
            if len(lib) < 3: print(f'{clip} {param}: library has {len(lib)} values so far'); continue
            r = evaluate(clip, param, obs, kc, meta['dt_obs'], meta['scale'], lib, truth_of(clip, param))
            json.dump(r, open(B / REF_OUT / f'ref_{clip}_{param}.json', 'w'), indent=1)
            band = f"[{r['band'][0]:.4g}, {r['band'][1]:.4g}]" if r.get('band') else '-'
            print(f"{clip} {param:2s} truth {r['truth']:<8.4g} {r['kind']:15s} est {r['est'] if r['est'] is None else round(r['est'], 4)!s:9s} "
                  f"err {r.get('err_pct', float('nan')):+6.1f}% band {band} in_band {r.get('truth_in_band')} lib {r['n_lib']} objs {len(r['objects'])}", flush=True)
