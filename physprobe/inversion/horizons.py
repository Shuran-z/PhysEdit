"""Uniform predictability horizons for all integrated tasks under the ORIGINAL simulator settings (32-bit, original
seeds), rule D7 of the issue log. For every moving object (> 1 cm):
  (1) reproducibility  d_rep(t): max pairwise distance among all true-parameter replays, plus the recorded reference
      trajectory when one exists (faithfulness to the dataset's own run);
  (2) smoothness       d2(t)  : |P(g(1+1e-4)) + P(g(1-1e-4)) - 2 mean(truth)|, O(delta^2) for smooth dynamics;
  horizon = first frame where max(d_rep, d2) exceeds what the camera can resolve: SIGMA_PX (1.5 px, the observation noise
  of the SAM boxes) converted to metres at the object's distance (depth / focal length), never below 1 mm. A first version
  used a fixed 1 mm and cut tasks at mm-level discrete effects (stick-slip or contact onset landing one time step
  earlier: T19_C01 3 mm, T12_C03 0.6 mm) that are far below what any video can show.
  The first difference (sensitivity) is reported, never used to cut.
Frames where an object is below z = -1 m (fell through a missing floor collider, B16) are ignored.
Inputs: existing replays (runs_for() of integration_report.py), g0h32/H32R_<clip>.json (extra truth repeats),
g0h32/H32P_<clip>.json (perturbed pair). Usage: python horizons.py [--fetch] -> horizons32.json + summary"""
import collections, json, subprocess, sys
from pathlib import Path
import numpy as np

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
fetch = '--fetch' in sys.argv
argv_clips = [a for a in sys.argv[1:] if not a.startswith('--')]
sys.argv = ['x']
exec(open(CODE / 'integration_report.py').read().split("audit = json.load")[0])   # runs_for(), recorded(), man
R = '/home/wangzijun_p25/zhangshuran/core100_inversion'
(B / 'g0h32').mkdir(exist_ok=True)
jobs = json.load(open(B / 'h32_jobs.json'))
if fetch:
    for j in jobs:
        dst = B / 'g0h32' / f"{j['tag']}.json"
        if not dst.exists():
            subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', f"nscc-wangzijun-4090:{R}/{j['tag']}/{j['param']}_poses.json", str(dst)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import os
SIGMA_PX, MIN_THRESH, FLOOR = float(os.environ.get("HORIZON_PX", 1.5)), 1e-3, -1.0


def camera_scale(clip):
    """focal length in px and eye position of the task's fixed camera (config render.fixed_view)"""
    import math
    f = B / 'cfg' / f'{clip}.json'
    cfg = json.load(open(f)) if f.exists() else json.load(open(B / 't15' / f'{clip}_config.json'))
    fv = cfg['render']['fixed_view']; H = (fv.get('resolution') or cfg['render']['resolution'])[1]
    return (H / 2) / math.tan(math.radians(fv['fov_deg']) / 2), np.array(fv['position'], float)
out = {}
for clip in sorted({j['clip'] for j in jobs}):
    if argv_clips and clip not in argv_clips: continue
    pf = B / 'g0h32' / f'H32P_{clip}.json'
    if not pf.exists(): out[clip] = dict(status='MISSING_PERTURBED'); continue
    truths = runs_for(clip)
    rf = B / 'g0h32' / f'H32R_{clip}.json'
    if rf.exists(): truths += [v['poses'] for v in json.load(open(rf)).values() if v.get('poses')]
    pert = [v['poses'] for v in json.load(open(pf)).values() if v.get('poses')]
    if len(pert) < 2 or not truths: out[clip] = dict(status='RUN_FAILED', n_truth=len(truths), n_pert=len(pert)); continue
    meta = recorded(clip) if (man[clip].get('metadata') or man[clip].get('metadata_local')) else None
    fps = man[clip].get('fps') or 30
    focal, eye = camera_scale(clip)
    objs = {}
    for n in truths[0]:
        P = [np.array(r[n])[:, :3] for r in truths if n in r]
        Q = [np.array(r[n])[:, :3] for r in pert]
        m = min(len(x) for x in P + Q)
        rec = None
        if meta is not None:
            try:
                rec = np.array([next(o['position'] for o in fr['objects'] if o['name'] == n) for fr in meta['frames']]); m = min(m, len(rec))
            except StopIteration: rec = None
        P = [x[:m] for x in P]; Q = [x[:m] for x in Q]
        mv = np.linalg.norm(P[0] - P[0][0], axis=1)
        if mv.max() < 0.01: continue
        start = int(np.argmax(mv > 1e-3))
        group = P + ([rec[:m]] if rec is not None else [])
        ok = np.all([x[:, 2] > FLOOR for x in group + Q], axis=0)
        d_rep = np.max([np.linalg.norm(group[a] - group[b], axis=1) for a in range(len(group)) for b in range(a + 1, len(group))], axis=0) if len(group) > 1 else np.zeros(m)
        Pt = np.mean(P, axis=0)
        d2 = np.linalg.norm(Q[0] + Q[1] - 2 * Pt, axis=1)
        d1 = np.maximum(np.linalg.norm(Q[0] - Pt, axis=1), np.linalg.norm(Q[1] - Pt, axis=1))
        d = np.where(ok, np.maximum(d_rep, d2), 0.0)
        depth = np.linalg.norm(P[0] - eye, axis=1)                     # distance to the camera, per frame
        thr = np.maximum(SIGMA_PX * depth / focal, MIN_THRESH)          # 1.5 px at that distance, in metres
        over = d > thr
        h = int(np.argmax(over)) if over.any() else m
        cause = None if h >= m else ('not reproducible' if d_rep[h] > thr[h] else 'not smooth in g')
        objs[n] = dict(start=start, horizon=h, full=h >= m, cause=cause, usable_frames=max(0, h - max(start, 4)),
                       usable_s=round(max(0, h - max(start, 4)) / fps, 2), moved_in_window_cm=round(100 * float(mv[:max(h, 1)].max()), 1),
                       sensitivity_mm_per_1em4=round(1000 * float(np.where(ok, d1, 0)[:max(h, 1)].max()), 3), n_truth=len(P), with_record=rec is not None,
                       threshold_mm=round(1000 * float(thr[max(start, 4)]), 2), max_uncertainty_mm=round(1000 * float(d.max()), 1))
    if not objs: out[clip] = dict(status='STATIC'); continue
    best = max(objs, key=lambda k: (objs[k]['full'], objs[k]['usable_frames'] * objs[k]['moved_in_window_cm']))
    zero_sens = all(o['sensitivity_mm_per_1em4'] == 0 for o in objs.values())
    out[clip] = dict(status='GRAVITY_OVERRIDE_NO_EFFECT' if zero_sens else 'OK', objects=objs, best=dict(object=best, **objs[best]))
json.dump(out, open(B / 'horizons32.json', 'w'), indent=1)
groups = collections.defaultdict(list)
for clip, v in out.items():
    if v.get('status') != 'OK': groups[v.get('status')].append(clip); continue
    b = v['best']
    k = 'full video' if b['full'] else ('>= 1 s' if b['usable_s'] >= 1 else ('0.3-1 s' if b['usable_s'] >= 0.3 else '< 0.3 s'))
    groups[k].append(clip if b['full'] else f"{clip}[{b['object'].split('_', 1)[1][:14]} {b['start']}->{b['horizon']} {b['cause']}]")
for k in ['full video', '>= 1 s', '0.3-1 s', '< 0.3 s', 'STATIC', 'GRAVITY_OVERRIDE_NO_EFFECT', 'MISSING_PERTURBED', 'RUN_FAILED']:
    if groups[k]: print(f'== {k}: {len(groups[k])}\n   ' + '\n   '.join(groups[k]))
