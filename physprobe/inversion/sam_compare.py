"""Compare two SAM 3.1 tracks files job by job: frames present in only one of them, and per-frame box
differences (max |dx| over the four xyxy coordinates, px) on the common frames. Used to check that a new tracking host
reproduces the reference host (A800 vs hupanwen, issue log F8).
Usage: python sam_compare.py REF.jsonl NEW.jsonl   -> prints a table"""
import json, sys
import numpy as np


def load(p):
    out = {}
    for l in open(p):
        t = json.loads(l)
        for n, v in t['tracks'].items():
            out[(t['id'], n)] = {f: b for f, b in zip(v['frames'], v['xyxy']) if b is not None}
    return out


ref, new = load(sys.argv[1]), load(sys.argv[2])
worst = 0.0
for k in sorted(set(ref) | set(new)):
    if k not in ref or k not in new:
        print(f"{k[0]}: only in {'REF' if k in ref else 'NEW'}"); continue
    a, b = ref[k], new[k]
    common = sorted(set(a) & set(b))
    d = np.array([np.max(np.abs(np.array(a[f], float) - np.array(b[f], float))) for f in common]) if common else np.zeros(0)
    d = d[np.isfinite(d)]
    if len(d): worst = max(worst, float(d.max()))
    print(f"{k[0]}: frames ref {len(a)} new {len(b)} common {len(common)} | only-ref {len(set(a) - set(b))} only-new {len(set(b) - set(a))} | "
          f"box diff max {d.max() if len(d) else float('nan'):.2f} px, mean {d.mean() if len(d) else float('nan'):.3f} px, frames > 1 px {int((d > 1).sum())}")
print(f'worst box difference {worst:.2f} px')
