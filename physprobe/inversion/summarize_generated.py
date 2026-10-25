"""Per-model summary of the generated-video inversions (results_gen/<NAME>.jsonl from eval_generated.py).
For each model and parameter: videos evaluated, share with a point estimate, median |est / prompt value - 1| over the point
estimates, share whose band contains the prompt value (the parameter the model was asked to show), share of videos where at
least one used-object candidate was 'not_explained' or 'inconsistent' (motion no parameter value can explain).
T19/T20 friction is left out (issue log B20). Usage: python summarize_generated.py NAME -> results_gen/<NAME>_by_model.md"""
import collections, json, statistics as st, sys
from pathlib import Path

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
name = sys.argv[1]
R = [json.loads(l) for l in open(B / 'results_gen' / f'{name}.jsonl')]
R = [r for r in R if 'param' in r and not (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))]
by = collections.defaultdict(list)
for r in R: by[(r['model'], r['param'])].append(r)
lines = ['| 模型 | 参数 | 视频数 | 点估计 | 区间 | 单侧界 | 不可辨识 | 无法解释 | 无观测 | 提示值在带内 | 点估计相对提示值偏差（中位数） |', '|---|---|---|---|---|---|---|---|---|---|---|']
pct = lambda a, n: f"{100 * a / max(1, n):.0f}%"
for (m, p), rs in sorted(by.items()):
    pts = [abs(r['est'] / r['truth'] - 1) * 100 for r in rs if r.get('kind') == 'point' and r.get('est') and r.get('truth')]
    k = collections.Counter(r.get('kind') for r in rs); n = len(rs)
    nb = [r for r in rs if r.get('band')]
    lines.append(f"| {m} | {p} | {n} | {pct(k['point'], n)} | {pct(k['interval'], n)} | {pct(k['upper_bound'] + k['lower_bound'], n)} | {pct(k['unidentifiable'], n)} | "
                 f"{pct(k['not_explained'], n)} | {pct(k['no_observation'], n)} | {pct(sum(bool(r.get('truth_in_band')) for r in nb), len(nb))} | {st.median(pts) if pts else float('nan'):.0f}% |")
# gravity prompt response: C01/C02/C03 ask for moon / Mars / Earth gravity; median of the estimate (point) or band centre
lines += ['', '重力提示响应（C01/C02/C03 分别提示 1.62 / 3.71 / 9.81 m/s²；取点估计或区间中心的中位数，括号内为样本数）', '',
          '| 模型 | 提示 1.62 | 提示 3.71 | 提示 9.81 |', '|---|---|---|---|']
for m in sorted({r['model'] for r in R}):
    cells = []
    for g in (1.62, 3.71, 9.81):
        xs = [r['est'] if r.get('kind') == 'point' else (r['band'][0] * r['band'][1]) ** 0.5 for r in R
              if r['model'] == m and r['param'] == 'g' and r['clip'][4:] in ('C01', 'C02', 'C03') and abs(r['truth'] - g) < 0.01 and r.get('kind') in ('point', 'interval')]
        cells.append(f"{st.median(xs):.2f} ({len(xs)})" if xs else '-')
    lines.append(f"| {m} | " + ' | '.join(cells) + ' |')
out = B / 'results_gen' / f'{name}_by_model.md'
out.write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
