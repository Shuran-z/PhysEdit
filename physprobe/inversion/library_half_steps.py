"""Half-step values for the truth-relative libraries (mu, v): truth x r^(+-0.5) (r = 1.15 for mu, 1.12 for v). The main
grid leaves k = 0 out, which made the interval containing the truth twice as wide as every other interval (r^2), i.e. the
known-answer video sat in the sparsest spot of its library; with the half steps the truth lies in the middle of a normal
interval [truth r^-0.5, truth r^0.5] (the least favourable position on a uniform grid). Each job goes to the host queue that
holds its library's chunk 00 (warm kernel cache). Usage: python library_half_steps.py -> lib3_queues_half/<queue>.json"""
import json
from pathlib import Path

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
L = json.load(open(B / 'lib3_libraries.json'))['libraries']
plan = {j['tag']: j for j in json.load(open(B / 'lib3_plan.json'))}
owner = {}
for f in (B / 'lib3_queues').glob('*.json'):
    for j in json.load(open(f)): owner[j['tag']] = f.stem
R = {'mu': 1.15, 'v': 1.12}
out = {}
for lib in L:
    if lib['param'] not in R: continue
    t = lib['truths'][0]; r = R[lib['param']]
    vals = [round(t * r ** -0.5, 6), round(t * r ** 0.5, 6)]
    if lib['param'] == 'mu':
        vals = [min(2.0, max(0.01, v)) for v in vals]
        if all(v > 1.0 for v in lib['values']): vals = [v for v in vals if v > 1.0]   # T19/T20: background plane at 1.0 (B20)
    if not vals: continue
    base = plan[f"LIB3_{lib['lib']}_00"]
    j = dict(base, tag=f"LIB3_{lib['lib']}_h0", values=vals)
    if lib['clip'].startswith('T15') and lib['param'] == 'mu':
        for k, v in enumerate(vals): out.setdefault(owner[base['tag']], []).append(dict(j, tag=f"LIB3_{lib['lib']}_h{k}", values=[v]))
    else:
        out.setdefault(owner[base['tag']], []).append(j)
(B / 'lib3_queues_half').mkdir(exist_ok=True)
for q, jobs in out.items():
    json.dump(jobs, open(B / 'lib3_queues_half' / f'{q}.json', 'w'), indent=1)
    print(q, len(jobs), 'jobs', sum(len(j['values']) for j in jobs), 'sims')
