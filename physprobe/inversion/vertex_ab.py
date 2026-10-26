"""Offline A/B of the estimator at the loss minimum (D41 candidate), from the loss curves stored in known-truth results:
estimate_band with the quadratic fitted to the 5 library values nearest the minimum ('local5', official) or to the whole
indistinguishable set ('set'). A denser library makes 5 neighbours span a narrower range, so the local vertex follows
sub-threshold loss wiggles; the set-wide fit does not depend on the library density. Checks first that 'local5'
reproduces the stored results exactly, then per set and parameter: point / measured (point + interval) |error| and the
kind and truth-in-band changes. T19/T20 friction is left out (B20).
Usage: python vertex_ab.py RESULT [RESULT ...]   (result directories with ref_*.json or synthetic .jsonl, relative to WORK)"""
import glob, json, math, os, sys
import numpy as np

import evaluator as ev

MEAS = ('point', 'interval')


def load(d):
    d = d if os.path.isabs(d) else str(ev.B / d)
    rs = [json.loads(l) for l in open(d)] if d.endswith('.jsonl') else \
        [json.load(open(f)) for f in glob.glob(os.path.join(d, 'ref_*.json')) if not f.endswith('_summary.json')]
    return [r for r in rs if r.get('curve') and not (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))]


def redo(r, mode):
    ev.VERTEX = mode
    vs = np.array([c[0] for c in r['curve']]); ys = np.array([c[1] for c in r['curve']], float)
    ys = np.where(np.isfinite(ys), ys, np.nanmax(ys[np.isfinite(ys)]) + 1e6)
    e = ev.estimate_band(vs, ys, r.get('delta', ev.DELTA)); t = r['truth']; lo, hi = e['band']
    if e['kind'] == 'upper_bound': lo = 0.0
    if e['kind'] == 'lower_bound': hi = math.inf
    c = e.get('center') if e['kind'] in MEAS else None
    return dict(kind=e['kind'], est=e.get('est'), center=c, band=e['band'], in_band=lo <= t <= hi,
                err=None if c is None else 100 * (c - t) / t)


q = lambda x, f: float(np.percentile(x, f)) if len(x) else float('nan')
for name in sys.argv[1:]:
    R = load(name); A = [redo(r, 'local5') for r in R]; Bv = [redo(r, 'set') for r in R]
    bad = sum(1 for r, a in zip(R, A) if a['kind'] != r['kind'] or (r.get('est') is not None and abs(a['est'] / r['est'] - 1) > 1e-9))
    print(f'=== {name}: {len(R)} results with a curve, local5 reproduces the stored result: {len(R) - bad}/{len(R)}')
    for p in ('g', 'mu', 'v'):
        for tag, X in (('local5', A), ('set', Bv)):
            x = [a for r, a in zip(R, X) if r['param'] == p]
            pts = np.abs([a['err'] for a in x if a['kind'] == 'point']); m = np.abs([a['err'] for a in x if a['kind'] in MEAS])
            print(f"{p:3s} {tag:6s} points {len(pts):3d} median {q(pts, 50):.2f}% p90 {q(pts, 90):.1f}% | measured {len(m):3d} "
                  f"median {q(m, 50):.2f}% p90 {q(m, 90):.1f}% within 10 % {100 * np.mean(m <= 10) if len(m) else 0:.0f}% | "
                  f"in band {sum(a['in_band'] for a in x)}")
    for r, a, b in zip(R, A, Bv):
        if a['kind'] != b['kind'] or a['in_band'] != b['in_band'] or (a['err'] is not None and b['err'] is not None and abs(a['err'] - b['err']) > 3):
            f = lambda v: '—' if v is None else f'{v:+.1f}%'
            print(f"  {r['clip']} {r['param']:2s} {a['kind']} -> {b['kind']}  err {f(a['err'])} -> {f(b['err'])}  in band {a['in_band']} -> {b['in_band']}")
