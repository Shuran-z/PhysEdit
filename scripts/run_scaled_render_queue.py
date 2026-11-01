"""Run a disjoint render assignment with live GPU admission controls."""
import concurrent.futures
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(sys.argv[1])
lock = (root / 'scheduler.lock').open('w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
spec = importlib.util.spec_from_file_location('worker', root / 'worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
plan = json.loads((root / 'plan.json').read_text())
assigned = {r['sample'] for r in plan}
assert len(assigned) == len(plan)
for name in ['receipts', 'logs', 'locks']:
    (worker.O / name).mkdir(exist_ok=True)
active = {}
last = {}
pool = concurrent.futures.ThreadPoolExecutor(max_workers=24)
while True:
    for future in list(active):
        if future.done():
            future.result()
            del active[future]
    receipts = {p.stem: json.loads(p.read_text()) for p in (worker.O / 'receipts').glob('*.json') if p.stem in assigned}
    complete = {s for s, r in receipts.items() if r.get('media_complete')}
    failed = {s for s, r in receipts.items() if r.get('error')}
    running = {r['sample'] for r, g in active.values()}
    todo = [r for r in plan if r['sample'] not in complete | failed | running]
    control = json.loads((root / 'control.json').read_text())
    snapshot = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    gpu = [list(map(int, l.split(','))) for l in snapshot.splitlines()]
    status = dict(pid=os.getpid(), updated=time.time(), assigned=len(plan), completed_videos=3 * len(complete),
                  failed=len(failed), pending=len(todo), active=[dict(sample=r['sample'], gpu=g) for r, g in active.values()],
                  gpu=gpu, control=control, phase='RUNNING' if active or todo else 'COMPLETE')
    if failed and not active and (len(failed) >= 3 or not todo):
        status['phase'] = 'NEEDS_FAILURE_REPAIR'
    worker.save(root / 'status.json', status)
    if status['phase'] in ['COMPLETE', 'NEEDS_FAILURE_REPAIR']:
        break
    if len(failed) < 3:
        for g, memory, util in sorted(gpu, key=lambda x: -x[1]):
            count = sum(gg == g for r, gg in active.values())
            if (g in control['allowed_gpus'] and memory >= control['min_free_mib'] and
                count < control['per_gpu'] and len(active) < control['max_active'] and todo and time.time() - last.get(g, 0) >= 30):
                row = todo.pop(0)
                assert not (worker.O / 'locks' / row['sample']).exists(), 'Conflicting sample ownership'
                active[pool.submit(worker.run, row, g)] = (row, g)
                last[g] = time.time()
    time.sleep(10)
