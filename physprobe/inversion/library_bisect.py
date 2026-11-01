"""Adaptive refinement of the libraries where the dynamics bifurcate: for every library whose main grid is complete locally,
adjacent simulations whose visible-box tracks of the task's usable objects differ by more than half of their motion
amplitude (the same test evaluator.refine_library uses before interpolating) get their geometric midpoint simulated, until
the interval ratio is below MIN_RATIO. Video-independent (part of the library), so every generated video benefits.
Usage: python library_bisect.py [--round K] [--min-ratio 1.03] -> library_queues_bisect<K>/<queue>.json + summary"""
import argparse, json, math
from pathlib import Path
import numpy as np
import evaluator as ev

ap = argparse.ArgumentParser(); ap.add_argument('--round', type=int, default=1); ap.add_argument('--min-ratio', type=float, default=1.03)
a = ap.parse_args()
B = ev.B
from paths import chunk_name
plan = {j['tag']: j for j in json.load(open(B / 'library_plan.json'))}
owner = {}
for f in (B / 'library_queues').glob('*.json'):
    for j in json.load(open(f)): owner[j['tag']] = f.stem
local = {p.stem for p in (B / 'libraries').glob('*.json')}
out, n_int, n_lib = {}, 0, 0
for L in ev.LIBS:
    tags = [t for t in plan if plan[t]['lib'] == L['lib']]
    if not all(chunk_name(t) in local for t in tags): continue           # main grid not complete yet
    clip = L['clip']; names = sorted({n for m in L['members'] for n in ev.usable(m)})
    lib = sorted(ev.library(clip, L['param']), key=lambda t: t[0])
    mids = []
    for (v0, b0), (v1, b1) in zip(lib, lib[1:]):
        if v1 / v0 < a.min_ratio: continue
        for n in names:
            if n not in b0 or n not in b1: continue
            F = min(len(b0[n][1]), len(b1[n][1])); x0, x1 = b0[n][1][:F], b1[n][1][:F]
            amp = max(np.nanmax(np.abs(x0 - x0[4])), np.nanmax(np.abs(x1 - x1[4])), 4.0)
            if np.nanmax(np.abs(x0 - x1)) > 0.5 * amp + 2.0:
                mids.append(round(math.sqrt(v0 * v1), 6)); break
    n_lib += 1
    if not mids: continue
    n_int += len(mids)
    base = plan[tags[0]]
    step = 1 if (clip.startswith('T15') and L['param'] == 'mu') else 6
    for i in range(0, len(mids), step):
        out.setdefault(owner[tags[0]], []).append(dict(base, tag=f"{L['lib']}_b{a.round}{i // step}", values=mids[i:i + step]))
D = B / f'library_queues_bisect{a.round}'; D.mkdir(exist_ok=True)
for q, jobs in out.items():
    json.dump(jobs, open(D / f'{q}.json', 'w'), indent=1)
    print(q, len(jobs), 'jobs', sum(len(j['values']) for j in jobs), 'sims')
print(f'{n_lib} complete libraries checked, {n_int} bifurcating intervals -> midpoints')
