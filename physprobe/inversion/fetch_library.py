"""Fetch finished library chunks (and the new hosts' consistency replays) from every host queue into libraries/<chunk>.json.
One tar stream per host; chunks already fetched are skipped. Also writes library_done_tags.json (for library_split.py rebalancing).
Usage: python fetch_library.py [HOST ...]"""
import io, json, subprocess, sys, tarfile
from pathlib import Path

from paths import WORK as B, CODE, gt, chunk_name   # data dir (outside git) / code dir
OUT = B / 'libraries'; OUT.mkdir(exist_ok=True)
ROOT = {'nscc-wangzijun-4090': '/home/wangzijun_p25/zhangshuran/core100_inversion'}
DEF = '/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion'
by_host = {}
for f in sorted(B.glob('library_queues*/*.json')):   # main, half-step and bisection queues
    host = 'nscc-' + f.stem.rsplit('_gpu', 1)[0]
    by_host.setdefault(host, []).extend(json.load(open(f)))
have = {p.stem for p in OUT.glob('*.json')}
only = sys.argv[1:]
for host, jobs in by_host.items():
    if only and host not in only: continue
    want = [(j['tag'], j['param']) for j in jobs if chunk_name(j['tag']) not in have]
    if not want: continue
    root = ROOT.get(host, DEF)
    lst = '\n'.join(f"{t}/{p}_poses.json" for t, p in want)
    cmd = f"cd {root} && printf '%s\\n' \"$(cat)\" | while read f; do [ -e \"$f\" ] && echo \"$f\"; done | tar -cf - -T - 2>/dev/null"
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=60', host, cmd], input=lst.encode(), capture_output=True, timeout=1800)
    n = 0
    if r.stdout:
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
            for m in tf.getmembers():
                if not m.isfile(): continue
                tag = m.name.split('/')[0]
                (OUT / f'{chunk_name(tag)}.json').write_bytes(tf.extractfile(m).read()); n += 1
    print(f'{host}: fetched {n} new chunk files ({len(want)} not yet local)')
done = sorted(p.stem for p in OUT.glob('*.json'))
json.dump(done, open(B / 'library_done_tags.json', 'w'))
print('local chunks', len(done))
