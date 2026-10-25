"""File closure for moving the evaluation to another host: run one physics-only replay per listed task under strace
(open/openat), at most MAXP at once on one GPU, each capped at TIMEOUT s (assets are loaded while the scene is built),
then collect every successfully opened regular file under /home/wangzijun_p25 or /data_cached (outside our own work
dir and the conda env, which are copied whole). Also adds every absolute path string found in the task configs.
Usage (server): python batch2/trace_closure.py GPU CLIP [CLIP ...]  -> batch2/closure/{trace_<clip>.txt, closure.json}"""
import json, os, re, subprocess, sys, time
from pathlib import Path

D = Path('/home/wangzijun_p25/zhangshuran/core100_inversion'); OUT = D / 'batch2/closure'; OUT.mkdir(parents=True, exist_ok=True)
PY = '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
MAXP, TIMEOUT = 6, 600
gpu, clips = sys.argv[1], sys.argv[2:]
man = json.load(open(D / 'batch2/manifest2.json'))
procs = []
for clip in clips:
    m = man[clip]; tr = OUT / f'trace_{clip}.txt'; run = OUT / f'run_{clip}'
    if m.get('runner') == 't15':
        cmd = [PY, str(D / 'batch2/t15_runner.py'), f'TRACE_{clip}', m['remote_config'], m['remote_physics'], 'none', '0']
    else:
        cmd = [PY, str(D / 'physics_only.py'), '--renderer', m['renderer'], '--config', m['remote_config'], '--out', str(run)]
        cmd += [f'--renderer-arg={x}' for x in m.get('renderer_args', '').split() if x] + m.get('wrapper_args', '').split()
    full = ['timeout', str(TIMEOUT), 'strace', '-f', '-qq', '-e', 'trace=open,openat', '-o', str(tr)] + cmd
    while sum(p.poll() is None for _, p in procs) >= MAXP: time.sleep(5)
    procs.append((clip, subprocess.Popen(full, stdout=open(OUT / f'log_{clip}.txt', 'w'), stderr=subprocess.STDOUT, env=dict(os.environ, CUDA_VISIBLE_DEVICES=gpu), cwd=D)))
for clip, p in procs: p.wait()
pat = re.compile(r'open(?:at)?\((?:AT_FDCWD|\d+), "([^"]+)"|open\("([^"]+)"')
files = set()
for clip in clips:
    for line in open(OUT / f'trace_{clip}.txt', errors='replace'):
        if '= -1' in line: continue
        m = pat.search(line)
        if m: files.add(m.group(1) or m.group(2))
for cfgf in list((D / 'batch2/cfg').glob('*.json')) + list((D / 'batch2/t15').glob('*_config.json')):   # every task, traced or not
    for s in re.findall(r'"(/(?:home/wangzijun_p25|data_cached)/[^"]+)"', open(cfgf).read()): files.add(s)
keep = sorted(f for f in files if (f.startswith('/home/wangzijun_p25/') or f.startswith('/data_cached/'))
              and not f.startswith(str(D)) and '/miniconda3/' not in f and os.path.isfile(f))
json.dump(keep, open(OUT / 'closure.json', 'w'), indent=0)
print(len(keep), 'files,', round(sum(os.path.getsize(f) for f in keep) / 1e9, 2), 'GB')
(OUT / 'done').write_text('ok')
