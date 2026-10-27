"""Known-answer statistics of the reference results (results_reference/ref_*.json, or another directory): per parameter the
number of results by kind, point-estimate |error| median / p90 / max, and the share of bands that contain the truth.
Friction of T19/T20 is left out (issue log B20). Also takes a synthetic set's .jsonl.
Usage: python ref_stats.py [RESULT_DIR | SET.jsonl] [--compare OTHER_DIR]"""
import collections, glob, json, os, statistics as st, sys
import evaluator as ev

d = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else str(ev.B / 'results_reference')
R = [json.loads(l) for l in open(d)] if d.endswith('.jsonl') else [json.load(open(f)) for f in glob.glob(os.path.join(d, 'ref_*.json')) if not f.endswith('_summary.json')]
R = [r for r in R if 'param' in r]
R = [r for r in R if not (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))]
for p in ('g', 'mu', 'v'):
    rs = [r for r in R if r['param'] == p]; k = collections.Counter(r.get('kind') for r in rs)
    pts = sorted(abs(r['err_pct']) for r in rs if r.get('kind') == 'point' and 'err_pct' in r)
    nb = [r for r in rs if r.get('band')]
    q = lambda f: pts[min(len(pts) - 1, int(f * len(pts)))] if pts else float('nan')
    print(f"{p:3s} n={len(rs):3d} " + ' '.join(f'{kk}={k[kk]}' for kk in ('point', 'interval', 'upper_bound', 'lower_bound', 'unidentifiable', 'not_explained', 'no_observation') if k[kk]) +
          f" | point |err| median {st.median(pts) if pts else float('nan'):.2f}% p90 {q(0.9):.1f}% max {max(pts) if pts else float('nan'):.1f}% | truth in band {sum(bool(r.get('truth_in_band')) for r in nb)}/{len(nb)}")
if '--compare' in sys.argv:
    o = sys.argv[sys.argv.index('--compare') + 1]; same = diff = 0
    for f in glob.glob(os.path.join(d, 'ref_*.json')):
        g = os.path.join(o, os.path.basename(f))
        if f.endswith('_summary.json') or not os.path.exists(g): continue
        a, b = json.load(open(f)), json.load(open(g)); ea, eb = a.get('est') or a.get('center'), b.get('est') or b.get('center')
        ok = a.get('kind') == b.get('kind') and ((ea is None and eb is None) or (ea is not None and eb is not None and abs(ea / eb - 1) < 1e-6))
        same += ok; diff += not ok
    print(f'compare with {o}: identical {same}, different {diff}')
