#!/bin/bash
# Throughput benchmark on an evaluation host: N concurrent true-parameter replays of one task (the job of batch2/a800_g0_plan.json),
# sampled after SECONDS (covering start-up, kernel compile and part of the stepping), then stopped by PID. Reports per-sim physics
# step rate (median of Genesis' own "Running at X FPS" over the last 200 reports), progress, and the total over all sims.
# Run from the core100_inversion dir with the host environment sourced (. batch2/genesis_env.sh; plus MPS variables when testing MPS).
# Usage: gpu_bench.sh CLIP N LABEL SECONDS [GPU]
set -u
C=$1; N=$2; LB=$3; S=$4; G=${5:-0}
python3 - "$C" "$N" "$LB" <<'EOF'
import json, sys
c, n, lb = sys.argv[1], int(sys.argv[2]), sys.argv[3]
j = [j for j in json.load(open('batch2/a800_g0_plan.json')) if j['clip'] == c][0]
json.dump([dict(j, tag=f'BENCH_{lb}_{i}_{c}') for i in range(n)], open(f'batch2/bench_{lb}_plan.json', 'w'), indent=1)
EOF
rm -rf BENCH_${LB}_* batch1/BENCH_${LB}_* batch1/bench_${LB}_*
python3 batch1/refine_queue.py batch2/bench_${LB}_plan.json $G bench_${LB} --max-sims $N > batch2/bench_${LB}.log 2>&1 &
Q=$!
sleep $S
python3 - "$LB" "$S" <<'EOF'
import glob, re, statistics as st, sys
lb, s = sys.argv[1], sys.argv[2]; r = []
for f in sorted(glob.glob(f'BENCH_{lb}_*/none_0.log')):
    t = re.sub(r'\x1b\[[0-9;]*m', '', open(f, errors='ignore').read())
    v = [float(x) for x in re.findall(r'Running at ([0-9.]+) FPS', t)]
    prog = re.findall(r'rendering progress: (\d+)/', t)
    r.append((f.split('/')[0], round(st.median(v[-200:]), 1) if v else None, prog[-1] if prog else '-', len(v)))
for x in r: print('  ', *x)
ok = [x[1] for x in r if x[1]]
print(f'{lb}: {len(r)} sims, {len(ok)} stepping after {s} s | median steps/s per sim {st.median(ok) if ok else 0:.1f} | total steps/s {sum(ok):.1f}')
EOF
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader | sed -n "$((G+1))p"
desc() { local k; for k in $(ps -eo pid=,ppid= | awk -v p=$1 '$2==p{print $1}'); do desc $k; echo $k; done; }
L="$(desc $Q) $Q"; kill $L 2>/dev/null; sleep 3; kill -9 $L 2>/dev/null
rm -rf BENCH_${LB}_* batch1/BENCH_${LB}_*
