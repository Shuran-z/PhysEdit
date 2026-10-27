"""Collect finished library chunks of a plan from a simulation host's run directory into libraries/<chunk>.json, on the host
itself (fetch_library.py does the same over SSH from another machine). Chunks already collected are skipped.
Usage: python collect_library.py PLAN.json [OUT_DIR=libraries] [RUN_DIR=/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion]"""
import json, shutil, sys
from pathlib import Path

from paths import WORK as B, chunk_name

plan = json.load(open(sys.argv[1]))
run = Path(sys.argv[3] if len(sys.argv) > 3 else '/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion')
out = B / (sys.argv[2] if len(sys.argv) > 2 else 'libraries'); out.mkdir(exist_ok=True); n_new = n_missing = 0
for j in plan:
    dst = out / f"{chunk_name(j['tag'])}.json"
    if dst.exists(): continue
    src = run / j['tag'] / f"{j['param']}_poses.json"
    if src.exists(): shutil.copyfile(src, dst); n_new += 1
    else: n_missing += 1
print(f'collected {n_new} chunks, {n_missing} not finished, plan has {len(plan)}')
