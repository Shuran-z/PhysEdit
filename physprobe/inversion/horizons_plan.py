"""Plan the uniform predictability-horizon runs for all integrated tasks (original 32-bit settings, original seeds):
per task, enough true-parameter repeats to have >= 3 (existing replays count) and one run each at g*(1+1e-4) and
g*(1-1e-4). Writes horizon_jobs.json (run_batch jobs, or t15 runner jobs for T15)."""
import json, sys
from pathlib import Path
from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
sys.argv = ['x']
exec(open(CODE / 'integration_report.py').read().split("audit = json.load")[0])   # runs_for(), man, rows
jobs = []; summary = {}
for clip in sorted(man):
    if clip == 'T06_C04': continue
    cfg = json.load(open(B / 'cfg' / f'{clip}.json')) if (B / 'cfg' / f'{clip}.json').exists() else json.load(open(B / 't15' / f'{clip}_config.json'))
    g = -float(cfg['scene_overrides']['gravity'][2])
    have = len(runs_for(clip)); need = max(0, 3 - have)
    m = man[clip]; t15 = m.get('runner') == 't15'
    base = dict(clip=clip, config=m['remote_config'], renderer=m.get('renderer'), renderer_args=m.get('renderer_args', ''), movers=m['movers'])
    if m.get('wrapper_args'): base['wrapper_args'] = m['wrapper_args']
    if t15: base.update(runner='t15', physics=m['remote_physics'])
    jobs.append(dict(base, tag=f'perturbed_{clip}', param='g', values=[round(g * (1 + 1e-4), 8), round(g * (1 - 1e-4), 8)]))
    if need: jobs.append(dict(base, tag=f'repeats_{clip}', param='none', values=list(range(10, 10 + need))))
    summary[clip] = dict(g=g, existing_truth_runs=have, new_repeats=need)
slow = ('T03', 'T04', 'T08', 'T11', 'T14', 'T18')
jobs.sort(key=lambda j: (j['clip'][:3] not in slow, j['clip']))
json.dump(jobs, open(B / 'horizon_jobs.json', 'w'), indent=1); json.dump(summary, open(B / 'horizon_plan_summary.json', 'w'), indent=1)
print(len(jobs), 'jobs,', sum(len(j['values']) for j in jobs), 'simulations;', sum(v['new_repeats'] for v in summary.values()), 'new truth repeats')
