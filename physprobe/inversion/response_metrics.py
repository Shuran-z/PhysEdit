"""Generated-video metrics on the results that give a value (user definition, 2026-10-25):
A. evaluability per model: share of the validated results that give a value (point / interval), a one-sided bound, are
   unidentifiable, not explained, or no observation (the 'cannot evaluate' share is to be checked against human scores);
B. inversion error of the results with a value: |best / prompt - 1| (median, 75th pct, within 10 / 25 %);
C. parameter response: Spearman rho and Kendall tau between the prompted and the measured value, with a bootstrap 95 % CI.
   g: C01-C03 prompt 1.62 / 3.71 / 9.81 in every task (C04/C05 9.81), so its response is within the same scenes;
   mu is the same in all conditions of a task except T07/T14/T18, so its response is mostly a ranking across scenes;
   v varies within and across tasks.
The same B and C on the known-truth videos (reference, synthetic sets) give the instrument's floor / ceiling.
Also writes results_gen/per_video_status.csv (one row per generated video: its key and the kind of each parameter) for the
comparison with human scores. T19/T20 friction is left out (B20); not_validated results are left out.
Usage: python response_metrics.py [GENERATED_NAME=all_cc_gated] -> results_gen/response_metrics.md / .json"""
import collections, csv, glob, json, sys
import numpy as np
from scipy import stats

from paths import WORK as B

MEAS = ('point', 'interval')
CATS = (('value', MEAS), ('bound', ('upper_bound', 'lower_bound')), ('unidentifiable', ('unidentifiable',)),
        ('not_explained', ('not_explained',)), ('no_observation', ('no_observation',)))
skip = lambda r: r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20')
rng = np.random.default_rng(0)


def response(rs):
    """n, error stats and rank correlation of prompt vs measured over results with a value"""
    rs = [r for r in rs if r['kind'] in MEAS and r.get('best') and r.get('truth')]
    if not rs: return dict(n=0)
    t = np.array([r['truth'] for r in rs]); b = np.array([r['best'] for r in rs]); e = np.abs(b / t - 1) * 100
    d = dict(n=len(rs), err_median=float(np.median(e)), err_p75=float(np.percentile(e, 75)),
             within10=float(np.mean(e <= 10)), within25=float(np.mean(e <= 25)), n_prompts=len(set(np.round(t, 4))))
    if d['n_prompts'] >= 2 and len(rs) >= 5:
        d['rho'] = float(stats.spearmanr(t, b)[0]); d['tau'] = float(stats.kendalltau(t, b)[0])
        bs = []
        for _ in range(1000):
            i = rng.integers(0, len(rs), len(rs))
            if len(set(t[i])) >= 2: bs.append(stats.spearmanr(t[i], b[i])[0])
        bs = np.array([x for x in bs if np.isfinite(x)])
        if len(bs): d['rho_ci'] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return d


def cell(d):
    if not d.get('n'): return '— | — | — | —'
    rho = f"{d['rho']:+.2f} [{d['rho_ci'][0]:+.2f}, {d['rho_ci'][1]:+.2f}]" if 'rho_ci' in d else '—'
    return f"{d['n']} | {d['err_median']:.1f}% | {100 * d['within25']:.0f}% | {rho}"


name = sys.argv[1] if len(sys.argv) > 1 else 'all_cc_gated'
known = {'reference': [json.load(open(f)) for f in glob.glob(str(B / 'results3' / 'ref_*.json')) if not f.endswith('_summary.json')]}
for s in ('s15v', 's30f121', 's10f16'):
    known[s] = [json.loads(l) for l in open(B / 'results_gen' / f'{s}.jsonl')]
G = [json.loads(l) for l in open(B / 'results_gen' / f'{name}.jsonl')]
G = [r for r in G if 'param' in r and not skip(r)]
V = [r for r in G if r['kind'] != 'not_validated']
out = dict(evaluability={}, known={}, generated={})
L = ['# Generated-video metrics: evaluability, inversion error, parameter response', '',
     f'Validated results: {len(V)} of {len(G)} (not_validated = the known-truth gate, D28). Results with a value = point or interval.', '',
     '## A. Evaluability per model (share of the validated results)', '',
     '| model | n | value (point / interval) | one-sided bound | unidentifiable | not explained | no observation |', '|---|---|---|---|---|---|---|']
models = sorted({r['model'] for r in V})
for m in models + ['all']:
    rs = [r for r in V if m == 'all' or r['model'] == m]; c = collections.Counter(r['kind'] for r in rs)
    sh = {k: sum(c[x] for x in kinds) / len(rs) for k, kinds in CATS}; out['evaluability'][m] = dict(n=len(rs), **sh)
    L.append(f"| {m} | {len(rs)} | " + ' | '.join(f'{100 * sh[k]:.1f}%' for k, _ in CATS) + ' |')
L += ['', '## B + C. Known-truth videos (instrument floor / ceiling): results with a value', '',
      '| set | parameter | n | median abs error | within 25 % | Spearman rho [95 % CI] |', '|---|---|---|---|---|---|']
for s, R in known.items():
    R = [r for r in R if 'param' in r and not skip(r)]
    for p in ('g', 'mu', 'v'):
        d = response([r for r in R if r['param'] == p]); out['known'][f'{s}|{p}'] = d
        L.append(f'| {s} | {p} | {cell(d)} |')
L += ['', '## B + C. Generated videos: results with a value, error and response relative to the prompted value', '',
      '| model | g: n | g: median abs error | g: within 25 % | g: rho [95 % CI] | mu: n | mu: median abs error | mu: within 25 % | mu: rho [95 % CI] '
      '| v: n | v: median abs error | v: within 25 % | v: rho [95 % CI] |', '|---|' + '---|' * 12]
for m in models + ['all']:
    cells = []
    for p in ('g', 'mu', 'v'):
        d = response([r for r in V if (m == 'all' or r['model'] == m) and r['param'] == p]); out['generated'][f'{m}|{p}'] = d
        cells.append(cell(d))
    L.append(f'| {m} | ' + ' | '.join(cells) + ' |')
(B / 'results_gen' / 'response_metrics.md').write_text('\n'.join(L) + '\n')
json.dump(out, open(B / 'results_gen' / 'response_metrics.json', 'w'), indent=1)
vid = collections.OrderedDict()
for r in G:
    k = vid.setdefault(r['key'], dict(key=r['key'], model=r['model'], clip=r['clip'], annotation=r.get('annotation'), seed=r.get('seed')))
    k[f"{r['param']}_kind"] = r['kind']; k[f"{r['param']}_best"] = r.get('best') if r['kind'] in MEAS else None; k[f"{r['param']}_prompt"] = r.get('truth')
cols = ['key', 'model', 'clip', 'annotation', 'seed'] + [f'{p}_{x}' for p in ('g', 'mu', 'v') for x in ('kind', 'best', 'prompt')]
with open(B / 'results_gen' / 'per_video_status.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); [w.writerow({c: v.get(c) for c in cols}) for v in vid.values()]
print('\n'.join(L)); print(f'{len(vid)} videos -> per_video_status.csv')
