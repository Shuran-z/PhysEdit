"""Split lib3_plan.json over the evaluation hosts (one queue per GPU). GPU-heavy families only go to MPS hosts (issue log
F15); every job's cost = its task's per-simulation wall time on the 4090 x (frames / 210) x number of values; jobs are taken
nearest-to-truth chunk first (chunk 00 of every library, then 01, ...) and given to the queue with the least load per
concurrent simulation. New hosts get the 14 true-parameter consistency replays (issue log D10) at the head of their first
queue. Jobs already finished (tags listed in lib3_done_tags.json, if present) are skipped, so re-running rebalances.
Queues listed with --pin keep their existing lib3_queues file unchanged (they are already running); only jobs not in any
pinned file are distributed over the other queues.
Usage: python library_split.py [--pin FILE_STEM ...] -> lib3_queues/<host>_gpu<k>.json + summary"""
import sys
import json, statistics as st
from pathlib import Path

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
plan = json.load(open(B / 'lib3_plan.json'))
walls = json.load(open(B / 'sim_walls_4090.json'))
fam = {}
for k, v in walls.items(): fam.setdefault(k[:3], []).append(v)
HEAVY = {'T03', 'T04', 'T08', 'T01', 'T11', 'T18'}
# host alias, gpu, concurrent sims, MPS, needs consistency check
QUEUES = [('nscc-xdliang3-h100-1', 0, 13, True, True), ('nscc-xdliang3-h100-1', 1, 13, True, False),
          ('nscc-xdliang3-a800', 0, 6, True, False),
          ('nscc-xdliang3-a800-7', 0, 6, True, True), ('nscc-xdliang3-a800-7', 1, 6, True, False),
          ('nscc-wangzijun-4090', 0, 6, False, False), ('nscc-wangzijun-4090', 2, 6, False, False)]
SPEED = {True: 2.5, False: 1.0}   # MPS host vs the 4090's time-sliced walls (first guess; F15 benchmarks)
done = set(json.load(open(B / 'lib3_done_tags.json'))) if (B / 'lib3_done_tags.json').exists() else set()
g0 = json.load(open(B / 'a800_g0_plan.json'))


def cost(j):
    w = walls.get(j['clip']) or st.mean(fam.get(j['clip'][:3], [300]))
    fr = next((int(x) for x, y in zip(j.get('wrapper_args', '').split()[1:], j.get('wrapper_args', '').split()) if y == '--frames'), 210)
    return w * fr / 210 * len(j['values'])


pinned = set(sys.argv[sys.argv.index('--pin') + 1:]) if '--pin' in sys.argv else set()
stem = lambda q: f"{q[0].replace('nscc-', '')}_gpu{q[1]}"
owned = {j['tag'] for q in QUEUES if stem(q) in pinned for j in json.load(open(B / 'lib3_queues' / f'{stem(q)}.json'))}
todo = sorted((j for j in plan if j['tag'] not in done and j['tag'] not in owned), key=lambda j: (int(j['tag'].rsplit('_', 1)[1]), -cost(j)))
load = [0.0] * len(QUEUES); out = [[] for _ in QUEUES]
for i, q in enumerate(QUEUES):
    if stem(q) in pinned:
        out[i] = json.load(open(B / 'lib3_queues' / f'{stem(q)}.json')); load[i] = float('inf'); continue
    if q[4]:
        host = q[0].replace('nscc-xdliang3-', '').replace('-', '')
        out[i] += [dict(j, tag=f"G0{host.upper()}_{j['clip']}") for j in g0]
        load[i] += sum(cost(j) for j in g0) / q[2] / SPEED[q[3]]
for j in todo:
    ok = [i for i, q in enumerate(QUEUES) if q[3] or j['clip'][:3] not in HEAVY]
    i = min(ok, key=lambda i: load[i])
    out[i].append(j); load[i] += cost(j) / QUEUES[i][2] / SPEED[QUEUES[i][3]]
(B / 'lib3_queues').mkdir(exist_ok=True)
for q, jobs, l in zip(QUEUES, out, load):
    (h, g, n, mps, chk) = q; f = B / 'lib3_queues' / f'{stem(q)}.json'
    if stem(q) in pinned: print(f"{f.name:28s} pinned (running) | jobs {len(jobs):4d} sims {sum(len(j['values']) for j in jobs):5d}"); continue
    json.dump(jobs, open(f, 'w'), indent=1)
    print(f"{f.name:28s} max-sims {n:2d} MPS {'y' if mps else 'n'} | jobs {len(jobs):4d} sims {sum(len(j['values']) for j in jobs):5d} | est. {l / 3600:5.1f} h")
print('total sims', sum(len(j['values']) for jobs in out for j in jobs))
