"""Empirical calibration of the identifiability threshold (issue log D13). For every reference known-answer result
(results3/ref_*.json) with an interior minimum, the loss at the truth is interpolated on the loss curve (log-linear between
the neighbouring library values) and delta_needed = L(truth) - L(min) is the threshold that would just include the truth.
The calibrated threshold is the COVERAGE quantile of delta_needed over all results (one per task and parameter), so that
the band covers the truth in that fraction of the known-answer cases; it replaces the theoretical value 1 (sigma = 1.5 px,
independent frames), which ignores the frame-to-frame correlation of SAM errors and replay noise.
Usage: python calibrate_band.py [--coverage 0.9] -> results3/band_calibration.json"""
import argparse, glob, json, math
import numpy as np
from paths import WORK as B

ap = argparse.ArgumentParser(); ap.add_argument('--coverage', type=float, default=0.9); ap.add_argument('--dir', default='results3')
a = ap.parse_args()
need, rows = [], []
for f in sorted(glob.glob(str(B / a.dir / 'ref_*.json'))):
    r = json.load(open(f))
    if f.endswith('_summary.json') or not r.get('curve') or not r.get('truth'): continue
    c = np.array(r['curve']); v, y = c[:, 0], c[:, 1]
    o = np.argsort(v); v, y = v[o], y[o]
    if not (v[0] < r['truth'] < v[-1]): continue
    i = int(np.argmin(y))
    if i in (0, len(v) - 1): continue
    lt = float(np.interp(math.log(r['truth']), np.log(v), y))
    d = max(0.0, lt - float(y[i])); need.append(d); rows.append((f.split('/')[-1][4:-5], round(d, 2)))
need = np.array(need)
q = float(np.quantile(need, a.coverage)) if len(need) else 1.0
cal = dict(coverage_target=a.coverage, n=len(need), delta=max(1.0, q), delta_needed_quantiles={str(p): float(np.quantile(need, p)) for p in (0.5, 0.75, 0.9, 0.95)} if len(need) else {},
           coverage_at_delta1=float(np.mean(need <= 1.0)) if len(need) else None)
json.dump(dict(cal, cases=rows), open(B / a.dir / 'band_calibration.json', 'w'), indent=1)
print(json.dumps(cal, indent=1))
