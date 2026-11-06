"""Server-side sequential queue for library chunks: one chunk (<= 6 simulations) at a time on one GPU.
Idempotent (skips chunks whose <tag>/<param>_poses.json exists), can be restricted to a subset of tags by prefix, and
can wait for a running process to exit first (hand-over from another queue without overlapping simulations).
With --max-sims N, several small chunks run at once as long as the total number of simulations stays <= N.
Usage: python refine_queue.py PLAN GPU NAME [--prefix P1,P2] [--wait-pid PID] [--max-sims N]"""
import argparse, json, os, subprocess, time
from pathlib import Path

D = Path('/home/wangzijun_p25/zhangshuran/core100_inversion')
PY = '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
ap = argparse.ArgumentParser(); ap.add_argument('plan'); ap.add_argument('gpu'); ap.add_argument('name')
ap.add_argument('--prefix', default=''); ap.add_argument('--wait-pid', type=int); ap.add_argument('--max-sims', type=int, default=0)
a = ap.parse_args()
plan = [j for j in json.load(open(a.plan)) if not a.prefix or any(j['tag'].startswith(p) for p in a.prefix.split(','))]
prog = D / 'queue' / f'{a.name}_progress.json'; done = []; t0 = time.time()
if a.wait_pid:
    while os.path.exists(f'/proc/{a.wait_pid}'):
        prog.write_text(json.dumps(dict(waiting_for_pid=a.wait_pid, elapsed_s=round(time.time() - t0), total=len(plan)))); time.sleep(20)
def free_mib(gpu):   # shared machine (shuan 2026-11-04: never push others into OOM): free memory of our GPU before each launch
    try: return int(subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits', '-i', str(gpu)], stdout=subprocess.PIPE, universal_newlines=True).stdout.split()[0])
    except Exception: return 0


NEED = int(os.environ.get('QUEUE_FREE_MIB', '2048'))   # margin on top of about 1 GB per simulation (shuan 2026-11-05: free memory decides, 2 GiB margin)


def launch(j):
    # live check before every launch (F55; rule of shuan 2026-11-05: free memory now >= what we need + 2 GiB, others' use no longer decides)
    while subprocess.run(['python3', str(D / 'gpu_guard.py'), a.gpu, '--need', str(1000 * len(j['values']))]).returncode != 0:
        prog.write_text(json.dumps(dict(gpu_refused=True, gpu=a.gpu, job=j['tag']))); time.sleep(60)
    while free_mib(a.gpu) < NEED + 1000 * len(j['values']):
        prog.write_text(json.dumps(dict(waiting_for_memory=True, free_mib=free_mib(a.gpu), job=j['tag']))); time.sleep(60)
    env = dict(os.environ, RENDERER=j['renderer'], RENDERER_ARGS=j['renderer_args'])
    if j.get('friction_objects'): env['FRICTION_OBJECTS'] = j['friction_objects']
    if j.get('wrapper_args'): env['WRAPPER_ARGS'] = j['wrapper_args']
    cmd = [PY, str(D / 'run_batch.py'), j['tag'], j['config'], j['param'], a.gpu, ','.join(j['movers']), *[str(v) for v in j['values']]]
    if j.get('runner') == 't15':   # T15: original batched physics (deploy/t15_runner.py), GPU chosen via CUDA_VISIBLE_DEVICES
        env['CUDA_VISIBLE_DEVICES'] = a.gpu
        cmd = [PY, str(D / 'deploy/t15_runner.py'), j['tag'], j['config'], j['physics'], j['param'], *[str(v) for v in j['values']]]
    return subprocess.Popen(cmd, stdout=open(D / 'queue' / f"{j['tag']}.out", 'w'), stderr=subprocess.STDOUT, env=env, cwd=D)


todo = []
for j in plan:
    if (D / j['tag'] / f"{j['param']}_poses.json").exists(): done.append(dict(tag=j['tag'], rc=None, wall_s=0, skipped=True))
    else: todo.append(j)
running = []   # (job, process, start time)
while todo or running:
    while todo and (not running or sum(len(r[0]['values']) for r in running) + len(todo[0]['values']) <= (a.max_sims or 0)):
        j = todo.pop(0); running.append((j, launch(j), time.time()))
        if not a.max_sims: break
    prog.write_text(json.dumps(dict(elapsed_s=round(time.time() - t0), running=[r[0]['tag'] for r in running], queued=len(todo), total=len(plan), done=done), indent=1))
    time.sleep(10)
    for r in list(running):
        if r[1].poll() is not None:
            running.remove(r); done.append(dict(tag=r[0]['tag'], rc=r[1].returncode, wall_s=round(time.time() - r[2])))
prog.write_text(json.dumps(dict(elapsed_s=round(time.time() - t0), running=None, index=len(plan), total=len(plan), done=done), indent=1))
(D / 'queue' / f'{a.name}_done.json').write_text(json.dumps(done, indent=1))
