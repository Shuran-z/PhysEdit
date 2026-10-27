"""Why does a reference video fail its own known answer? Per object: the SAM 3.1 box vs the box the TRUE replay predicts
(the with-truth library entry, visible part, scaled into video pixels, frame-4 offset calibration as in evaluator.evaluate),
at zero time shift, frame by frame inside the predictability window. Prints per object: window, frames compared, median /
90th pct / max of the largest box-edge residual (px), the frames where it exceeds THRESH_PX, and which edge is off.
Usage: python ref_residuals.py CLIP PARAM [CLIP PARAM ...]"""
import sys
import numpy as np
import evaluator as ev

THRESH_PX = 5.0
args = sys.argv[1:]
tracks = ev.B / 'sam_lean' / 'reference' / 'tracks_lean.jsonl'
for clip, param in zip(args[::2], args[1::2]):
    obs, kc = ev.load_obs(tracks, clip); meta = ev.ref_meta(clip); truth = ev.truth_of(clip, param)
    lib = ev.library(clip, param, with_truth=True, workers=1)
    v, boxes = min(lib, key=lambda t: abs(np.log(t[0] / truth)))
    a = np.array([meta['scale'][0], meta['scale'][1]] * 2); hz = ev.HZ[clip]['objects']; dt, _ = ev.clock(clip)
    print(f'== {clip} {param} truth {truth} (library entry {v})')
    for n in ev.usable(clip):
        if n not in obs or n not in boxes: print(f'  {n}: no observation or no prediction'); continue
        k, ob = obs[n]; frac, sb = boxes[n]
        if kc not in set(k.tolist()): print(f'  {n}: condition frame not tracked'); continue
        i0 = int(np.where(k == kc)[0][0]); sbv = np.where((frac >= ev.MIN_VIS)[:, None], sb * a, np.nan)
        if np.isnan(sbv[4, 0]) or np.isnan(ob[i0, 0]): print(f'  {n}: not visible at the condition frame'); continue
        o = ob - (ob[i0] - sbv[4]); s = np.round(4 + (k - kc) * meta['dt_obs'] / dt).astype(int)
        h = int(hz[n]['horizon']); sel = (s >= 4) & (s <= min(h, len(sbv) - 1))
        r = np.abs(o[sel] - sbv[s[sel]]); ok = np.isfinite(r).all(1)
        if not ok.any(): print(f'  {n}: window {hz[n]["start"]}-{h}: no comparable frame'); continue
        rm = r[ok].max(1); fr = s[sel][ok]; bad = fr[rm > THRESH_PX]
        edge = ['x0', 'y0', 'x1', 'y1'][int(np.argmax(np.nanmedian(r[ok], 0)))]
        print(f'  {n}: window {hz[n]["start"]}-{h} frames {ok.sum()} | max-edge residual median {np.median(rm):.1f} p90 {np.percentile(rm, 90):.1f} '
              f'max {rm.max():.1f} px | > {THRESH_PX:.0f} px in {len(bad)} frames {bad[:12].tolist()}{"..." if len(bad) > 12 else ""} | worst edge {edge}')
