"""A/B of two reference known-answer runs (results_reference and a variant such as results_reference_<TAG>) on the results both contain:
per parameter the number of point estimates and their |error| median / p90, the measured results (point + interval) with
the best-fit |error| median / p90 / share within 10 %, truth in band, not explained; then every result whose kind changed.
Also takes two synthetic generated-like sets (results_gen/<set>.jsonl). T19/T20 friction is left out (B20).
Usage: python ref_ab.py VARIANT [BASE=results_reference] [--out FILE.json]   (directories or .jsonl files, relative to WORK or absolute)"""
import glob, json, os, sys
import numpy as np

from paths import WORK as B

MEAS = ('point', 'interval')


def load(d):
    """a result directory (ref_*.json) or a synthetic set's .jsonl (one known-truth result per clip and parameter)"""
    if d.endswith('.jsonl'): rs = [json.loads(l) for l in open(d)]
    else: rs = [json.load(open(f)) for f in glob.glob(os.path.join(d, 'ref_*.json')) if not f.endswith('_summary.json')]
    return {(r['clip'], r['param']): r for r in rs if 'param' in r and not (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))}


args = sys.argv[1:]; out_file = None
if '--out' in args: i = args.index('--out'); out_file = args[i + 1]; del args[i:i + 2]
var = load(args[0] if os.path.isabs(args[0]) else str(B / args[0]))
base = load(args[1] if len(args) > 1 and os.path.isabs(args[1]) else str(B / (args[1] if len(args) > 1 else 'results_reference')))
keys = sorted(set(var) & set(base)); out = dict(n=len(keys), params={}, changed=[])
print(f'compared {len(keys)} results')
q = lambda x, f: float(np.percentile(x, f)) if len(x) else float('nan')
for p in ('g', 'mu', 'v'):
    for name, R in (('base', base), ('variant', var)):
        x = [R[k] for k in keys if k[1] == p]
        pts = np.abs([r['err_pct'] for r in x if r['kind'] == 'point' and r.get('err_pct') is not None])
        m = np.abs([r['best_err_pct'] for r in x if r['kind'] in MEAS and r.get('best_err_pct') is not None])
        s = dict(n=len(x), points=len(pts), point_median=q(pts, 50), point_p90=q(pts, 90), measured=len(m),
                 measured_median=q(m, 50), measured_p90=q(m, 90), measured_within10=float(np.mean(m <= 10)) if len(m) else None,
                 in_band=sum(bool(r.get('truth_in_band')) for r in x), not_explained=sum(r['kind'] == 'not_explained' for r in x))
        out['params'][f'{p}|{name}'] = s
        print(f"{p:3s} {name:8s} n {s['n']:3d} | points {s['points']:3d} median {s['point_median']:.2f}% p90 {s['point_p90']:.1f}% | "
              f"measured {s['measured']:3d} median {s['measured_median']:.2f}% p90 {s['measured_p90']:.1f}% within 10 % "
              f"{100 * (s['measured_within10'] or 0):.0f}% | in band {s['in_band']} | not explained {s['not_explained']}")
for k in keys:
    a, b = base[k], var[k]
    if a['kind'] != b['kind'] or bool(a.get('truth_in_band')) != bool(b.get('truth_in_band')):
        c = dict(clip=k[0], param=k[1], kind=[a['kind'], b['kind']], best_err_pct=[a.get('best_err_pct'), b.get('best_err_pct')],
                 in_band=[a.get('truth_in_band'), b.get('truth_in_band')]); out['changed'].append(c)
        f = lambda v: '—' if v is None else f'{v:+.1f}%'
        print(f"  {k[0]} {k[1]:2s} {a['kind']} -> {b['kind']}  best {f(c['best_err_pct'][0])} -> {f(c['best_err_pct'][1])}  "
              f"in band {c['in_band'][0]} -> {c['in_band'][1]}")
if out_file: json.dump(out, open(out_file, 'w'), indent=1)
