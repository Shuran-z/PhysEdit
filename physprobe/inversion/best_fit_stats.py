"""How precise is the best-fit value (D35), and what does it say about the generated videos?
A. Known truth (reference results3 and the synthetic generated-like sets): |best / truth - 1| per result kind and parameter
   (median, 75th / 90th percentile, share within 5 / 10 / 25 %), and by the fit residual (best_rms_px_max).
B. Generated videos (gated file): per model and parameter, over the measured results (point and interval: a finite band whose
   best value is meaningful; a one-sided bound's best value sits at a grid edge),
   the median ratio best / prompt (geometric), the median |best / prompt - 1| and the share within 10 / 25 % of the prompt;
   gravity prompt response C01 / C02 / C03 (1.62 / 3.71 / 9.81) from the same results.
T19/T20 friction is left out (B20). Usage: python best_fit_stats.py [GENERATED_NAME=all_cc_gated]
  -> results_gen/best_fit_stats.md and .json"""
import collections, glob, json, math, sys
import numpy as np

from paths import WORK as B

KINDS = ('point', 'interval', 'upper_bound', 'lower_bound', 'unidentifiable', 'not_explained')
MEAS = ('point', 'interval')
skip = lambda r: r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20')


def err_stats(errs):
    e = np.abs(np.array(errs, float))
    if not len(e): return None
    return dict(n=len(e), median=float(np.median(e)), p75=float(np.percentile(e, 75)), p90=float(np.percentile(e, 90)),
                within5=float(np.mean(e <= 5)), within10=float(np.mean(e <= 10)), within25=float(np.mean(e <= 25)))


def fmt(s):
    return '—' if s is None else f"{s['n']} | {s['median']:.1f}% | {s['p75']:.1f}% | {s['p90']:.1f}% | {100 * s['within10']:.0f}% | {100 * s['within25']:.0f}%"


name = sys.argv[1] if len(sys.argv) > 1 else 'all_cc_gated'
sets = {'reference': [json.load(open(f)) for f in glob.glob(str(B / 'results3' / 'ref_*.json')) if not f.endswith('_summary.json')]}
for s in ('s15v', 's30f121', 's10f16'):
    sets[s] = [json.loads(l) for l in open(B / 'results_gen' / f'{s}.jsonl')]
out, lines = {}, ['# Best-fit value (D35): precision and generated-video results', '',
                  '## A. Known truth: |best / truth - 1| by result kind', '',
                  '| set | parameter | kind | n | median | 75th pct | 90th pct | within 10 % | within 25 % |', '|---|---|---|---|---|---|---|---|---|']
for sname, R in sets.items():
    R = [r for r in R if 'param' in r and not skip(r) and r.get('best_err_pct') is not None]
    for p in ('g', 'mu', 'v'):
        for k in KINDS + ('all',):
            x = [r['best_err_pct'] for r in R if r['param'] == p and (k == 'all' or r.get('kind') == k)]
            st = err_stats(x); out[f'{sname}|{p}|{k}'] = st
            if st: lines.append(f'| {sname} | {p} | {k} | {fmt(st)} |')
lines += ['', '## A2. Known truth (reference + synthetic): |best / truth - 1| by the fit residual', '',
          '| parameter | best_rms_px_max | n | median | 75th pct | 90th pct | within 10 % | within 25 % |', '|---|---|---|---|---|---|---|---|']
allk = [r for R in sets.values() for r in R if 'param' in r and not skip(r) and r.get('best_err_pct') is not None and r.get('best_rms_px_max') is not None]
for p in ('g', 'mu', 'v'):
    for lo, hi in ((0, 1.5), (1.5, 3), (3, 6), (6, 1e9)):
        x = [r['best_err_pct'] for r in allk if r['param'] == p and lo <= r['best_rms_px_max'] < hi]
        st = err_stats(x); out[f'known_by_rms|{p}|{lo}-{hi}'] = st
        lines.append(f"| {p} | {lo}–{hi if hi < 1e9 else '∞'} px | {fmt(st)} |")

G = [json.loads(l) for l in open(B / 'results_gen' / f'{name}.jsonl')]
G = [r for r in G if 'param' in r and r['kind'] != 'not_validated' and not skip(r)]
lines += ['', '## B. Generated videos: best / prompt over the measured results (point and interval)', '',
          '| model | parameter | n | median best / prompt | median abs deviation | within 10 % | within 25 % |', '|---|---|---|---|---|---|---|']
by = collections.defaultdict(list)
for r in G:
    if r['kind'] in MEAS and r.get('best') and r.get('truth'): by[(r['model'], r['param'])].append(r)
for (m, p), rs in sorted(by.items()):
    ratio = np.array([r['best'] / r['truth'] for r in rs]); dev = np.abs(ratio - 1) * 100
    d = dict(n=len(rs), median_ratio=float(np.exp(np.median(np.log(ratio)))), median_dev=float(np.median(dev)),
             within10=float(np.mean(dev <= 10)), within25=float(np.mean(dev <= 25)))
    out[f'gen|{m}|{p}'] = d
    lines.append(f"| {m} | {p} | {d['n']} | {d['median_ratio']:.3f} | {d['median_dev']:.1f}% | {100 * d['within10']:.1f}% | {100 * d['within25']:.1f}% |")
lines += ['', '## C. Gravity prompt response (best g of the measured results; median, 25th-75th pct, n)', '',
          '| model | prompt 1.62 | prompt 3.71 | prompt 9.81 |', '|---|---|---|---|']
for m in sorted({r['model'] for r in G}):
    cells = []
    for g in (1.62, 3.71, 9.81):
        xs = np.array([r['best'] for r in G if r['model'] == m and r['param'] == 'g' and r['clip'][4:] in ('C01', 'C02', 'C03')
                       and abs(r['truth'] - g) < 0.01 and r['kind'] in MEAS and r.get('best')])
        out[f'gravity|{m}|{g}'] = dict(n=len(xs), median=float(np.median(xs)) if len(xs) else None)
        cells.append(f'{np.median(xs):.2f} [{np.percentile(xs, 25):.2f}, {np.percentile(xs, 75):.2f}] ({len(xs)})' if len(xs) else '— (0)')
    lines.append(f'| {m} | ' + ' | '.join(cells) + ' |')
(B / 'results_gen' / 'best_fit_stats.md').write_text('\n'.join(lines) + '\n')
json.dump(out, open(B / 'results_gen' / 'best_fit_stats.json', 'w'), indent=1)
print('\n'.join(lines))
