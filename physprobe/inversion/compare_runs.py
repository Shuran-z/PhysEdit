"""Sensitivity of the generated-video results to an evaluation setting: two gated result files (validation_gate.py) of the
same videos, e.g. the official run and one with the noise level doubled (PHYSPROBE_SIGMA_PX=3). Per model and parameter:
share 'not explained', share whose band contains the prompted value (among results with a band), share with a point
estimate; then the Spearman rank correlation of the models between the two runs for each of these measures.
T19/T20 friction is left out (B20); not_validated items are left out.
Usage: python compare_runs.py NAME_A NAME_B -> results_gen/compare_<NAME_A>__<NAME_B>.md"""
import collections, json, sys
import numpy as np

from paths import WORK as B


def load(name):
    R = [json.loads(l) for l in open(B / 'results_gen' / f'{name}.jsonl')]
    return [r for r in R if 'param' in r and r['kind'] != 'not_validated' and not (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))]


def measures(R):
    by = collections.defaultdict(list)
    for r in R: by[(r['model'], r['param'])].append(r)
    out = {}
    for k, rs in by.items():
        nb = [r for r in rs if r.get('band') and r['kind'] != 'not_explained' and r.get('truth')]
        out[k] = dict(ne=sum(r['kind'] == 'not_explained' for r in rs) / len(rs), inband=sum(bool(r.get('truth_in_band')) for r in nb) / max(1, len(nb)),
                      point=sum(r['kind'] == 'point' for r in rs) / len(rs))
    return out


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y)); return float(np.corrcoef(rx, ry)[0, 1])


a, b = sys.argv[1], sys.argv[2]
A, Bm = measures(load(a)), measures(load(b))
lines = [f'# {a} vs {b}', '', '| model | param | not explained A | not explained B | prompt in band A | prompt in band B | point A | point B |', '|---|---|---|---|---|---|---|---|']
for k in sorted(A):
    if k not in Bm: continue
    lines.append(f"| {k[0]} | {k[1]} | {A[k]['ne']:.0%} | {Bm[k]['ne']:.0%} | {A[k]['inband']:.0%} | {Bm[k]['inband']:.0%} | {A[k]['point']:.1%} | {Bm[k]['point']:.1%} |")
lines += ['', '| param | measure | Spearman rho of the model ranking |', '|---|---|---|']
for p in ('g', 'mu', 'v'):
    ks = sorted(k for k in A if k[1] == p and k in Bm)
    for m in ('ne', 'inband'):
        lines.append(f"| {p} | {m} | {spearman([A[k][m] for k in ks], [Bm[k][m] for k in ks]):.2f} |")
for name, M in ((a, A), (b, Bm)):
    tot = collections.Counter()
    for r in load(name): tot[r['kind']] += 1
    lines.append(f"\n{name}: not explained {tot['not_explained'] / sum(tot.values()):.1%} of {sum(tot.values())} validated results; point {tot['point']}, interval {tot['interval']}")
out = B / 'results_gen' / f'compare_{a}__{b}.md'
out.write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))
