"""Precision refinement of the libraries (D36): parameter-space interpolation between two adjacent library simulations is
only trusted when their projected tracks are close. For every library, every adjacent pair of values whose visible-box
tracks (camera pixels) of the task's usable objects differ by more than TOL_PX at any frame of the objects' predictability
windows gets its geometric midpoint simulated, down to MIN_RATIO. Truth-agnostic (it looks at the simulations only, never at
the truth or a video), so the known-answer test stays fair; every generated video of the task benefits.
--count only reports how many midpoints each tolerance would need (round 1, and the expected later rounds: a pair that
differs by D needs about log2(D / TOL) levels). Otherwise writes queue files like library_bisect.py.
Usage: python library_refine_plan.py [--tol 4.5] [--min-ratio 1.01] [--round 1] [--count] [--workers 24]"""
import argparse, json, math
from multiprocessing import get_context
import numpy as np
import evaluator as ev

ap = argparse.ArgumentParser(); ap.add_argument('--tol', type=float, default=4.5); ap.add_argument('--min-ratio', type=float, default=1.01)
ap.add_argument('--round', type=int, default=1); ap.add_argument('--count', action='store_true'); ap.add_argument('--workers', type=int, default=24)
ap.add_argument('--max-diff', type=float, default=1e9, help='skip pairs that differ by more (bifurcations do not converge)')
ap.add_argument('--libs', help='comma-separated library names (default: all)'); ap.add_argument('--out', help='write one flat plan file instead of per-queue files')
a = ap.parse_args()
B = ev.B


def pairs(L):
    """[(v0, v1, max track difference inside the windows, px)] for one library"""
    names = sorted({n for m in L['members'] for n in ev.usable(m)})
    hz = {n: max(ev.HZ[m]['objects'][n]['horizon'] for m in L['members'] if n in ev.HZ[m].get('objects', {})) for n in names}
    lib = sorted(ev.library(L['clip'], L['param'], workers=1), key=lambda t: t[0]); out = []
    for (v0, b0), (v1, b1) in zip(lib, lib[1:]):
        d = 0.0
        for n in names:
            if n not in b0 or n not in b1: continue
            F = min(len(b0[n][1]), len(b1[n][1]), int(hz[n]) + 1)
            if F <= 4: continue
            vis = (b0[n][0][4:F] >= ev.MIN_VIS) & (b1[n][0][4:F] >= ev.MIN_VIS)
            if not vis.any(): continue
            diff = np.abs(b0[n][1][4:F] - b1[n][1][4:F])[vis]
            if np.isfinite(diff).any(): d = max(d, float(np.nanmax(diff)))
        out.append((v0, v1, d))
    return L['lib'], L['clip'], L['param'], out


LIBS = [L for L in ev.LIBS if not a.libs or L['lib'] in a.libs.split(',')]
with get_context('fork').Pool(a.workers) as pool:
    res = pool.map(pairs, LIBS, chunksize=1)
if a.count:
    for tol in (2.25, 4.5, 9.0):
        r1 = sum(1 for _, _, _, ps in res for v0, v1, d in ps if tol < d <= a.max_diff and v1 / v0 >= a.min_ratio)
        tot = sum(min(math.ceil(math.log2(d / tol)), max(0, math.floor(math.log(v1 / v0) / math.log(a.min_ratio))))
                  for _, _, _, ps in res for v0, v1, d in ps if tol < d <= a.max_diff and v1 / v0 >= a.min_ratio)
        print(f'tol {tol} px: {r1} midpoints in round 1, about {tot} pair-levels in total (an upper estimate of later rounds)')
    worst = sorted(((d, lib, p, v0, v1) for lib, c, p, ps in res for v0, v1, d in ps), reverse=True)[:15]
    for d, lib, p, v0, v1 in worst: print(f'  {lib} {p}: {v0:.4g} - {v1:.4g} differ by {d:.1f} px')
    by = {}
    for lib, c, p, ps in res: by[p] = by.get(p, 0) + sum(1 for v0, v1, d in ps if a.tol < d <= a.max_diff and v1 / v0 >= a.min_ratio)
    print('round-1 midpoints by parameter at tol', a.tol, by)
else:
    plan = {j['tag']: j for j in json.load(open(B / 'lib3_plan.json'))}
    owner = {}
    for f in (B / 'lib3_queues').glob('*.json'):
        for j in json.load(open(f)): owner[j['tag']] = f.stem
    out, n = {}, 0
    for lib, clip, p, ps in res:
        mids = [round(math.sqrt(v0 * v1), 6) for v0, v1, d in ps if a.tol < d <= a.max_diff and v1 / v0 >= a.min_ratio]
        if not mids: continue
        tags = [t for t in plan if plan[t]['lib'] == lib]; base = plan[tags[0]]; n += len(mids)
        step = 1 if (clip.startswith('T15') and p == 'mu') else 6
        for i in range(0, len(mids), step):
            out.setdefault(owner[tags[0]], []).append(dict(base, tag=f"LIB3_{lib}_p{a.round}{i // step:03d}", values=mids[i:i + step]))
    if a.out:
        json.dump([j for jobs in out.values() for j in jobs], open(a.out, 'w'), indent=1); print(f'{n} midpoints at tol {a.tol} px -> {a.out}'); raise SystemExit
    D = B / f'lib3_queues_refine{a.round}'; D.mkdir(exist_ok=True)
    for q, jobs in out.items():
        json.dump(jobs, open(D / f'{q}.json', 'w'), indent=1)
        print(q, len(jobs), 'jobs', sum(len(j['values']) for j in jobs), 'sims')
    print(f'{n} midpoints at tol {a.tol} px -> {D}')
