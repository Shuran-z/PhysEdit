"""Does anything move? For each generated result, the observed motion of each evaluated object (largest change of any box
edge from the condition frame, 3-frame median filter against single-frame SAM glitches) inside the predictability window,
next to the motion the simulation at the PROMPTED value shows in the same window (scaled into the video's pixels).
A 'not explained' result where no evaluated object moves more than STATIC_PX while the prompted scene moves at least
SHOULD_PX is a 'static' failure: the prompted event never happens. The rest are videos whose objects move, but in a way no
parameter value explains; they are split by observed / simulated motion: hardly moves (< 0.25), moves too little
(0.25-0.67), similar amount (0.67-1.5), moves too much (> 1.5). Also the motion onsets (first motion > STATIC_PX) of both.
Same clock and windows as evaluator.evaluate (realtime for generated, reference for synthetic).
Usage: python motion_check.py NAME TRACKS.jsonl [--items SET] [--clock realtime|reference] [--workers 24] [--with-truth]
  -> results_gen/<NAME>_motion.jsonl and a summary (per model, per task family) on stdout"""
import argparse, collections, json, math
from multiprocessing import get_context
import numpy as np
import evaluator as ev

STATIC_PX, SHOULD_PX = 3.0, 10.0
ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('tracks'); ap.add_argument('--items', default='all')
ap.add_argument('--clock', choices=['realtime', 'reference'], default='realtime'); ap.add_argument('--workers', type=int, default=24)
ap.add_argument('--with-truth', action='store_true')
a = ap.parse_args()
items = {x['key']: x for x in json.load(open(ev.B / 'sam_gen' / a.items / 'items.json'))['items'] if x.get('map')}
R = [json.loads(l) for l in open(ev.B / 'results_gen' / f'{a.name}.jsonl')]
R = [r for r in R if 'param' in r and r['key'] in items]
OBS = collections.defaultdict(dict); KC = {}
for line in open(a.tracks):
    r = json.loads(line); vid, n = r['id'].split('__', 1)
    if vid not in items: continue
    tr = r['tracks'][n]
    OBS[vid][n] = (np.array(tr['frames']), np.array([b if b is not None else [np.nan] * 4 for b in tr['xyxy']], float)); KC[vid] = r.get('prompt_frame', 0)
by_clip = collections.defaultdict(list)
for r in R: by_clip[r['clip']].append(r)


def medfilt3(x):
    y = x.copy()
    for i in range(1, len(x) - 1): y[i] = np.nanmedian(x[i - 1:i + 2], axis=0)
    return y


def run_clip(clip):
    dt, _ = ev.clock(clip); hz = ev.HZ[clip]['objects']; out = []; libs = {}
    for r in by_clip[clip]:
        p = r['param']
        if p not in libs: libs[p] = ev.library(clip, p, with_truth=a.with_truth, workers=1)
        lib = libs[p]; truth = ev.truth_of(clip, p)
        if not lib: continue
        _, boxes = min(lib, key=lambda t: abs(math.log(t[0] / truth)))
        x = items[r['key']]; m = x['cam_to_video']; DT = ev.generated_dt(clip, x['fps'], a.clock); kc = KC.get(r['key'], 0)
        sa = np.array([m['scale'][0], m['scale'][1]] * 2); sb_ = np.array([m['offset'][0], m['offset'][1]] * 2)
        per = {}
        for n in ev.usable(clip):
            if n not in OBS.get(r['key'], {}) or n not in boxes: continue
            k, ob = OBS[r['key']][n]
            if kc not in set(k.tolist()): continue
            i0 = int(np.where(k == kc)[0][0])
            if np.isnan(ob[i0, 0]): continue
            s = 4 + (k - kc) * dt / DT; h = int(hz[n]['horizon'])
            sel = (s >= 4) & (s <= h)
            o = medfilt3(ob)[sel]
            obs_px = float(np.nanmax(np.abs(o - ob[i0]))) if np.isfinite(o).any() else float('nan')
            frac, sb = boxes[n]; F = len(sb); sbv = sb * sa + sb_
            fr = [f for f in range(4, min(h, F - 1) + 1) if frac[f] >= ev.MIN_VIS]
            sim_px = float(np.max(np.abs(sbv[fr] - sbv[4]))) if fr and frac[4] >= ev.MIN_VIS else float('nan')
            # motion onset (s after the condition frame): first frame moved > STATIC_PX (whole video for the observation)
            mv = np.nanmax(np.abs(medfilt3(ob) - ob[i0]), 1) > STATIC_PX; ko = k[mv & (k >= kc)]
            on_obs = float((ko.min() - kc) * DT) if len(ko) else None
            fo = [f for f in fr if np.max(np.abs(sbv[f] - sbv[4])) > STATIC_PX]
            on_sim = float((fo[0] - 4) * dt) if fo and frac[4] >= ev.MIN_VIS else None
            per[n] = (round(obs_px, 1), round(sim_px, 1), on_obs, on_sim)
        if not per: continue
        mo = max((v[0] for v in per.values() if np.isfinite(v[0])), default=float('nan'))
        ms = max((v[1] for v in per.values() if np.isfinite(v[1])), default=float('nan'))
        static = bool(np.isfinite(mo) and np.isfinite(ms) and mo < STATIC_PX and ms >= SHOULD_PX)
        oo = [v[2] for v in per.values() if v[2] is not None]; os_ = [v[3] for v in per.values() if v[3] is not None]
        out.append(dict(key=r['key'], model=r['model'], clip=clip, param=p, kind=r['kind'], kind_before_gate=r.get('kind_before_gate'),
                        max_obs_px=mo, max_sim_px=ms, static=static, onset_obs_s=min(oo) if oo else None, onset_sim_s=min(os_) if os_ else None,
                        objects=per))
    return out


with get_context('fork').Pool(a.workers) as pool:
    res = [o for xs in pool.map(run_clip, sorted(by_clip), chunksize=1) for o in xs]
with open(ev.B / 'results_gen' / f'{a.name}_motion.jsonl', 'w') as f:
    for o in res: f.write(json.dumps(o) + '\n')


def table(group):
    c = collections.defaultdict(collections.Counter)
    for o in res:
        if o['kind'] == 'not_validated': continue
        g = group(o); c[g]['n'] += 1
        if o['kind'] == 'not_explained':
            c[g]['ne'] += 1; c[g]['ne_static'] += o['static']
        else: c[g]['other_static'] += o['static']
    for g, v in sorted(c.items()):
        print(f"{g:28s} n={v['n']:5d} not_explained={v['ne'] / max(1, v['n']):.2f}  of which static={v['ne_static'] / max(1, v['ne']):.2f}  "
              f"static among the other kinds={v['other_static'] / max(1, v['n'] - v['ne']):.2f}")


AMP = (('hardly moves', 0, 0.25), ('moves too little', 0.25, 0.67), ('similar amount', 0.67, 1.5), ('moves too much', 1.5, float('inf')))


def amplitude(group):
    """'not explained' results by observed / prompted-simulation motion (prompted scene moves >= SHOULD_PX)"""
    c = collections.defaultdict(collections.Counter)
    for o in res:
        if o['kind'] != 'not_explained' or not (np.isfinite(o['max_obs_px']) and np.isfinite(o['max_sim_px'])) or o['max_sim_px'] < SHOULD_PX: continue
        q = o['max_obs_px'] / o['max_sim_px']; c[group(o)][next(lab for lab, lo, hi in AMP if lo <= q < hi)] += 1
    print(f"{'':28s} " + '  '.join(f'{lab:>16s}' for lab, _, _ in AMP))
    for g, v in sorted(c.items()):
        n = sum(v.values()); print(f'{g:28s} ' + '  '.join(f'{v[lab] / n:16.2f}' for lab, _, _ in AMP) + f'   (n={n})')


print('== per model'); table(lambda o: o['model'])
print('== per task family'); table(lambda o: o['clip'][:3])
print('== all'); table(lambda o: 'all')
print('== not explained by motion amplitude (observed / prompted simulation), per model'); amplitude(lambda o: o['model'])
print('== per task family'); amplitude(lambda o: o['clip'][:3])
print('== all'); amplitude(lambda o: 'all')
# onset: observed motion start minus the prompted simulation's (both > STATIC_PX), per task family; the evaluation allows +-20
# reference frames of time shift
print('== onset difference (observed - simulated, s), not explained vs other kinds')
for fam in sorted({o['clip'][:3] for o in res}):
    for lab, sel in (('not_explained', lambda o: o['kind'] == 'not_explained'), ('other', lambda o: o['kind'] not in ('not_explained', 'not_validated'))):
        d = np.array([o['onset_obs_s'] - o['onset_sim_s'] for o in res if o['clip'][:3] == fam and sel(o) and o['onset_obs_s'] is not None and o['onset_sim_s'] is not None])
        if len(d): print(f"{fam} {lab:14s} n={len(d):5d} median={np.median(d):+.2f}  |d|>0.67 s: {np.mean(np.abs(d) > 0.67):.2f}  |d|>1.5 s: {np.mean(np.abs(d) > 1.5):.2f}")
