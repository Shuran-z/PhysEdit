"""Evaluate generated (or synthetic generated-like) videos with evaluator.evaluate(): items.json from make_gen_jobs.py /
make_synth.py, SAM 3.1 lean tracks, library v3. Each item, each applicable parameter (g; mu; v where the task inverts
speed) -> estimate (point / interval / bound / unidentifiable / no_observation) with band, loss curve and per-object
diagnostics. Generated and synthetic videos are scored with the same library as the validated known-answer tests (D30:
without the true-parameter replays; --with-truth adds them and is kept only for comparison). Parallel over tasks (fork
pool); library boxes are cached first.
Usage: python eval_generated.py NAME TRACKS.jsonl [TRACKS2.jsonl ...] [--with-truth] [--workers 8] [--clock realtime|reference] [--out OUT]
  -> results_gen/<OUT or NAME>.jsonl + summary per model and parameter"""
import argparse, collections, json, statistics as st
from multiprocessing import get_context
import numpy as np
import evaluator as ev

ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('tracks', nargs='+'); ap.add_argument('--with-truth', action='store_true')
ap.add_argument('--params', default='g,mu,v'); ap.add_argument('--workers', type=int, default=8); ap.add_argument('--out', help='output name (default NAME)')
ap.add_argument('--clock', choices=['realtime', 'reference'], default='realtime', help='E2: realtime for generated videos, reference for synthetic ones')
a = ap.parse_args()
D = ev.B / 'sam_gen' / a.name
items = [x for x in json.load(open(D / 'items.json'))['items'] if x.get('map')]
OBS = collections.defaultdict(dict); KC = {}
for path in a.tracks:
    for line in open(path):
        r = json.loads(line); vid, n = r['id'].split('__', 1); tr = r['tracks'][n]
        OBS[vid][n] = (np.array(tr['frames']), np.array([b if b is not None else [np.nan] * 4 for b in tr['xyxy']], float)); KC[vid] = r.get('prompt_frame', 0)
by_clip = collections.defaultdict(list)
for x in items: by_clip[x['clip']].append(x)
params = a.params.split(',')
for clip in by_clip:                                       # warm the visible-box cache (parallel inside library())
    for p in params:
        if (clip, p) in ev.LIBMAP: ev.library(clip, p, with_truth=a.with_truth, workers=a.workers)


def run_clip(clip):
    out = []
    libs = {p: ev.library(clip, p, with_truth=a.with_truth, workers=1) for p in params if (clip, p) in ev.LIBMAP}
    for x in by_clip[clip]:
        obs = OBS.get(x['key'])
        if not obs: out.append(dict(key=x['key'], clip=clip, model=x['model'], status='no_tracks')); continue
        for p, lib in libs.items():
            if len(lib) < 3: continue
            m = x['cam_to_video']
            try:
                r = ev.evaluate(clip, p, obs, KC[x['key']], ev.generated_dt(clip, x['fps'], a.clock), m['scale'], lib, ev.truth_of(clip, p), offset=m['offset'])
            except Exception as e:   # one bad item must not stop 30k evaluations
                r = dict(clip=clip, param=p, kind='error', est=None, band=None, error=f'{type(e).__name__}: {str(e)[:200]}')
            r.pop('curve', None)   # 30k results: keep estimate, band, diagnostics only
            r.update(key=x['key'], model=x['model'], seed=x['seed'], annotation=x['annotation'], map_source=x['map']['source'])
            out.append(r)
    return out


with get_context('fork').Pool(a.workers) as pool:
    results = [r for rs in pool.map(run_clip, sorted(by_clip), chunksize=1) for r in rs]
(ev.B / 'results_gen').mkdir(exist_ok=True)
with open(ev.B / 'results_gen' / f'{a.out or a.name}.jsonl', 'w') as f:
    for r in results: f.write(json.dumps(r, default=float) + '\n')
summ = collections.defaultdict(list)
for r in results:
    if 'param' in r: summ[(r['model'], r['param'])].append(r)
print(f"{'model':26s} {'param':5s} {'n':>5s} {'point':>5s} {'|err| med':>9s} {'in band':>7s} {'interval':>8s} {'bound':>5s} {'unident':>7s} {'no obs':>6s}")
for (m, p), rs in sorted(summ.items()):
    pts = [abs(r['err_pct']) for r in rs if r.get('kind') == 'point' and 'err_pct' in r]
    cnt = collections.Counter(r.get('kind') for r in rs)
    print(f"{m:26s} {p:5s} {len(rs):5d} {cnt['point']:5d} {st.median(pts) if pts else float('nan'):8.1f}% {sum(bool(r.get('truth_in_band')) for r in rs):7d} "
          f"{cnt['interval']:8d} {cnt['upper_bound'] + cnt['lower_bound']:5d} {cnt['unidentifiable']:7d} {cnt['no_observation']:6d}")
