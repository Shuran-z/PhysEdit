"""A800 evaluation-host consistency check (issue log F8). The A800 true-parameter replay of a task is treated as one more
truth repeat: it is added to the 4090 truth group (+ recorded reference) of rule D7 and the horizon is recomputed with the
same threshold (1.5 px at the object's distance, >= 1 mm) and the same perturbed pair. The A800 host is acceptable for a
task when no object's horizon moves earlier. Also reported: max distance of the A800 run to the 4090 truth runs / record
inside the original window, and over the whole video (0 for deterministic tasks).
The same check validates truncated runs (physics_only.py --frames N, compared on their N frames) and any new host.
Inputs: host_replays/<tag>.json (refine_queue output, fetched with --fetch), horizons.json, the 4090 replays.
Usage: python host_consistency.py [--fetch] [--plan host_check_plan.json] [--host nscc-xdliang3-a800] [--out host_check.json] [CLIP ...]
       -> prints a table, writes the --out json"""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
import argparse
ap = argparse.ArgumentParser(); ap.add_argument('clips', nargs='*'); ap.add_argument('--fetch', action='store_true')
ap.add_argument('--plan', default='host_check_plan.json'); ap.add_argument('--host', default='nscc-xdliang3-a800')
ap.add_argument('--out', default='host_check.json')
args = ap.parse_args(); fetch, argv_clips = args.fetch, args.clips
sys.argv = ['x']
exec(open(CODE / 'integration_report.py').read().split("audit = json.load")[0])   # runs_for(), recorded(), man
SIGMA_PX, MIN_THRESH, FLOOR = float(os.environ.get('HORIZON_PX', 1.5)), 1e-3, -1.0
R = '/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion'
plan = json.load(open(B / args.plan))
H = json.load(open(B / 'horizons.json'))
(B / 'host_replays').mkdir(exist_ok=True)


def camera_scale(clip):   # same as horizons.py
    import math
    f = B / 'cfg' / f'{clip}.json'
    cfg = json.load(open(f)) if f.exists() else json.load(open(B / 't15' / f'{clip}_config.json'))
    fv = cfg['render']['fixed_view']; Hh = (fv.get('resolution') or cfg['render']['resolution'])[1]
    return (Hh / 2) / math.tan(math.radians(fv['fov_deg']) / 2), np.array(fv['position'], float)


out = {}
for j in plan:
    tag = j['tag']; clip = j['clip']
    if argv_clips and clip not in argv_clips: continue
    dst = B / 'host_replays' / f'{tag}.json'
    if fetch and not dst.exists():
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', f"{args.host}:{R}/{tag}/{j['param']}_poses.json", str(dst)],
                       stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not dst.exists(): out[clip] = dict(status='NO_A800_OUTPUT'); print(f'{clip}: NO A800 OUTPUT'); continue
    A = [v['poses'] for v in json.load(open(dst)).values() if v.get('poses')]
    if not A: out[clip] = dict(status='A800_RUN_FAILED'); print(f'{clip}: A800 RUN FAILED'); continue
    A = A[0]
    truths = runs_for(clip)
    rf = B / 'horizon_replays' / f'repeats_{clip}.json'
    if rf.exists(): truths += [v['poses'] for v in json.load(open(rf)).values() if v.get('poses')]
    pf = B / 'horizon_replays' / f'perturbed_{clip}.json'
    pert = [v['poses'] for v in json.load(open(pf)).values() if v.get('poses')] if pf.exists() else []
    meta = recorded(clip) if (man[clip].get('metadata') or man[clip].get('metadata_local')) else None
    focal, eye = camera_scale(clip)
    hz = H.get(clip, {}).get('objects', {})
    objs = {}
    for n, h0 in hz.items():
        if n not in A: objs[n] = dict(status='MISSING_IN_A800'); continue
        P = [np.array(r[n])[:, :3] for r in truths if n in r]
        Q = [np.array(r[n])[:, :3] for r in pert]
        a = np.array(A[n])[:, :3]
        m = min(len(x) for x in P + Q + [a])
        rec = None
        if meta is not None:
            try:
                rec = np.array([next(o['position'] for o in fr['objects'] if o['name'] == n) for fr in meta['frames']]); m = min(m, len(rec))
            except StopIteration: rec = None
        P = [x[:m] for x in P]; Q = [x[:m] for x in Q]; a = a[:m]
        group = P + ([rec[:m]] if rec is not None else [])
        ok = np.all([x[:, 2] > FLOOR for x in group + Q + [a]], axis=0)
        pair = lambda G: np.max([np.linalg.norm(G[i] - G[k], axis=1) for i in range(len(G)) for k in range(i + 1, len(G))], axis=0) if len(G) > 1 else np.zeros(m)
        Pt = np.mean(P, axis=0)
        d2 = np.linalg.norm(Q[0] + Q[1] - 2 * Pt, axis=1) if len(Q) >= 2 else np.zeros(m)
        thr = np.maximum(SIGMA_PX * np.linalg.norm(P[0] - eye, axis=1) / focal, MIN_THRESH)
        def horizon(G):
            over = np.where(ok, np.maximum(pair(G), d2), 0.0) > thr
            return int(np.argmax(over)) if over.any() else m
        h_old, h_new = horizon(group), horizon(group + [a])
        d_a = np.where(ok, np.max([np.linalg.norm(a - x, axis=1) for x in group], axis=0), 0.0)   # A800 to its farthest truth member
        lo, hi = max(h0['start'], 4), h0['horizon']
        win = d_a[lo:hi] if hi > lo else np.zeros(1)
        exact = float(np.where(ok, np.linalg.norm(a - P[0], axis=1), 0).max())
        objs[n] = dict(start=h0['start'], horizon_4090=h0['horizon'], horizon_recomputed=h_old, horizon_with_a800=h_new, frames=m,
                       max_in_window_mm=round(1000 * float(win.max()), 2), threshold_mm=h0['threshold_mm'],
                       max_full_video_vs_first_4090_mm=round(1000 * exact, 3),
                       ok=h_new >= h_old)
    good = all(o.get('ok') for o in objs.values()) if objs else None
    out[clip] = dict(status=('CONSISTENT' if good else 'HORIZON_SHORTENED') if objs else 'NO_OBJECTS', n_truth_4090=len(truths), with_record=meta is not None, objects=objs)
    print(f"{clip}: {out[clip]['status']:17s} truth={len(truths)} rec={'y' if meta is not None else 'n'} | " + ' | '.join(
        f"{n.split('_', 1)[1][:14]} h {o['horizon_recomputed']}->{o['horizon_with_a800']} win {o['max_in_window_mm']}/{o['threshold_mm']}mm full {o['max_full_video_vs_first_4090_mm']}mm"
        if 'horizon_with_a800' in o else f"{n}: {o['status']}" for n, o in objs.items()))
json.dump(out, open(B / args.out, 'w'), indent=1)
