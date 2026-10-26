"""Generated-video metrics (definitions agreed with the user, 2026-10-25, issue log E3):
A. evaluability per model: share of the validated results that give a value (point / interval), a one-sided bound, are
   unidentifiable, not explained, or no observation (the 'cannot evaluate' share is to be checked against human scores);
B. inversion error, from the results with a value: |best / prompt - 1| (median, 75th pct, within 10 / 25 %), g, mu, v;
C. parameter response, g and v (mu: error only; its prompt changes within a task only in T07/T14/T18). Rank agreement
   between the prompted and the measured value, counted only between one model's videos of the same task with different
   prompted values (a different scene is a different experiment, and the mu / v grid of each task is centred on that
   task's prompt, so a ranking across tasks follows the prompt by construction, D42). One-sided bounds count: every
   result with a band (point / interval: its band; upper bound: (0, bound]; lower bound: [bound, inf)) is compared with
   the others, and a pair is decided when the two bands do not overlap. tau = (concordant - discordant) / decided pairs,
   95 % CI from a bootstrap over (model, task) groups, with the decided pairs and the groups they come from (a CI from
   one or two groups is degenerate).
   Appendix: the same tau from the best values of the results with a value only.
The same B and C on the known-truth videos (reference, synthetic sets) give the instrument's floor / ceiling.
Also writes results_gen/per_video_status.csv (one row per generated video: key = s<seed>a<prompt variant>_<model>_<clip>,
the anonymous clip id, the video path under data/generated/, and the kind / value / prompt of each parameter) for the
comparison with human scores. T19/T20 friction is left out (B20); not_validated results are left out.
Usage: python response_metrics.py [GENERATED_NAME=all_cc_gated] -> results_gen/response_metrics.md / .json
(another name, e.g. a rule variant all_cc_sigma3_gated: response_metrics_<NAME>.md / .json, no per-video table)"""
import collections, csv, glob, json, math, sys
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
    if rs[0]['param'] == 'g' and d['n_prompts'] >= 2 and len(rs) >= 5: d['rho_pooled'] = float(stats.spearmanr(t, b)[0])
    d.update(within_task_tau(rs, lambda a, b: np.sign(a['best'] - b['best']), 'tau_within', 'tau_ci'))
    return d


def within_task_tau(rs, order, key, ci_key):
    """pairs within one model's videos of one task with different prompted values; order(a, b) = sign of the measured
    a - b (0 = undecided). tau = (concordant - discordant) / decided pairs, CI from a bootstrap over (model, task)"""
    by = collections.defaultdict(list)
    for r in rs: by[(r.get('model'), r['clip'][:3])].append(r)
    per = {}                                                    # (model, task) -> (concordant - discordant, decided, pairs)
    for task, xs in by.items():
        cd = dec = npair = 0
        for i in range(len(xs)):
            for j in range(i + 1, len(xs)):
                dt = xs[i]['truth'] - xs[j]['truth']
                if abs(dt) < 1e-9: continue
                o = order(xs[i], xs[j]); npair += 1; dec += o != 0; cd += np.sign(dt) * o
        if npair: per[task] = (cd, dec, npair)
    d = dict(pairs=int(sum(v[2] for v in per.values())), decided=int(sum(v[1] for v in per.values())), tasks_with_pairs=len(per),
             tasks_decided=sum(1 for v in per.values() if v[1]))
    if d['decided'] >= 5:
        d[key] = float(sum(v[0] for v in per.values()) / d['decided'])
        ks = list(per); bs = []
        for _ in range(1000):
            smp = [per[ks[k]] for k in rng.integers(0, len(ks), len(ks))]; n_ = sum(v[1] for v in smp)
            if n_: bs.append(sum(v[0] for v in smp) / n_)
        d[ci_key] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return d


def band_of(r):
    lo, hi = r['band']
    return (0.0 if r['kind'] == 'upper_bound' else lo, math.inf if r['kind'] == 'lower_bound' else hi)


def response_bands(rs):
    rs = [r for r in rs if r['kind'] in MEAS + ('upper_bound', 'lower_bound') and r.get('band') and r.get('truth')]
    def order(a, b):
        (alo, ahi), (blo, bhi) = band_of(a), band_of(b)
        return 1 if alo > bhi else -1 if ahi < blo else 0
    d = dict(n=len(rs)); d.update(within_task_tau(rs, order, 'tau_band', 'tau_band_ci')); return d


name = sys.argv[1] if len(sys.argv) > 1 else 'all_cc_gated'
suffix = '' if name == 'all_cc_gated' else f'_{name}'
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
err = lambda d: f"{d['n']} | {d['err_median']:.1f}% | {100 * d['within25']:.0f}%" if d.get('n') else '— | — | —'
tau = lambda d, k='tau_band', c='tau_band_ci': (f"{d[k]:+.2f} [{d[c][0]:+.2f}, {d[c][1]:+.2f}] ({d['decided']} / {d['tasks_decided']})" if k in d
                                               else f"— ({d.get('decided', 0)} / {d.get('tasks_decided', 0)})")
sets = list(known.items()) + [(m, [r for r in V if m == 'all' or r['model'] == m]) for m in models + ['all']]
out['bands'] = {}
for s, R in sets:
    R = [r for r in R if 'param' in r and not skip(r)]
    for p in ('g', 'mu', 'v'):
        (out['known'] if s in known else out['generated'])[f'{s}|{p}'] = response([r for r in R if r['param'] == p])
        out['bands'][f'{s}|{p}'] = response_bands([r for r in R if r['param'] == p])
rows = [(s, s in known) for s, _ in sets]
L += ['', '## B. Inversion error of the results with a value (|best / prompt - 1|; known-truth sets: |best / truth - 1|)', '',
      '| set / model | g: n | g: median | g: within 25 % | mu: n | mu: median | mu: within 25 % | v: n | v: median | v: within 25 % |', '|---|' + '---|' * 9]
L += [f"| {s} | " + ' | '.join(err((out['known'] if k else out['generated'])[f'{s}|{p}']) for p in ('g', 'mu', 'v')) + ' |' for s, k in rows]
L += ['', '## C. Parameter response: within-task Kendall tau from the bands, one-sided bounds included [95 % CI] (decided pairs / model-task groups)', '',
      '| set / model | g: results | g: tau | v: results | v: tau |', '|---|---|---|---|---|']
L += [f"| {s} | " + ' | '.join(f"{out['bands'][f'{s}|{p}']['n']} | {tau(out['bands'][f'{s}|{p}'])}" for p in ('g', 'v')) + ' |' for s, _ in rows]
L += ['', '## Appendix. Response from the best values of the results with a value only [95 % CI] (pairs / model-task groups)', '',
      '| set / model | g: tau | v: tau |', '|---|---|---|']
L += [f"| {s} | " + ' | '.join(tau((out['known'] if k else out['generated'])[f'{s}|{p}'], 'tau_within', 'tau_ci') for p in ('g', 'v')) + ' |' for s, k in rows]
(B / 'results_gen' / f'response_metrics{suffix}.md').write_text('\n'.join(L) + '\n')
json.dump(out, open(B / 'results_gen' / f'response_metrics{suffix}.json', 'w'), indent=1)
if suffix: print('\n'.join(L)); raise SystemExit
items = {it['key']: it for it in json.load(open(B / 'sam_gen' / 'all' / 'items.json'))['items']}   # anonymous clip id, video path
rel = lambda p: p.split('/data/generated/', 1)[-1] if p else None
vid = collections.OrderedDict()
for r in G:
    it = items.get(r['key'], {})
    k = vid.setdefault(r['key'], dict(key=r['key'], model=r['model'], clip=r['clip'], annotation=r.get('annotation'), seed=r.get('seed'),
                                      item=it.get('item'), video=rel(it.get('path'))))
    k[f"{r['param']}_kind"] = r['kind']; k[f"{r['param']}_best"] = r.get('best') if r['kind'] in MEAS else None; k[f"{r['param']}_prompt"] = r.get('truth')
cols = ['key', 'model', 'clip', 'annotation', 'seed', 'item', 'video'] + [f'{p}_{x}' for p in ('g', 'mu', 'v') for x in ('kind', 'best', 'prompt')]
with open(B / 'results_gen' / 'per_video_status.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); [w.writerow({c: v.get(c) for c in cols}) for v in vid.values()]
print('\n'.join(L)); print(f'{len(vid)} videos -> per_video_status.csv')
