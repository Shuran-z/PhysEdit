"""Is the noise model (sigma = 1.5 px per box edge) right for generated videos? Per evaluated object, the frame-to-frame
noise of the SAM 3.1 box is estimated from the second difference d2[k] = x[k+1] - 2 x[k] + x[k-1] of each box edge inside
the predictability window (in the video's own frames): robust std 1.4826 MAD(d2) / sqrt(6) (white noise of std s gives
std(d2) = s sqrt(6); smooth motion adds little except at impacts, which the MAD ignores). Compares generated models with
the synthetic generated-like sets, where the physics is exact and only tracking noise remains.
Usage: python track_noise.py NAME:TRACKS.jsonl:ITEMS_SET[:CLOCK] [...]   (e.g. all:sam_gen/all/tracks/all_camcomp.jsonl:all)
  -> per group (model) median and 90th percentile of the per-object noise, printed and written to results_gen/track_noise.json"""
import collections, json, sys
import numpy as np
import evaluator as ev

out = {}
for spec in sys.argv[1:]:
    name, tracks, iset = spec.split(':')[:3]; clk = (spec.split(':') + ['realtime'])[3]
    items = {x['key']: x for x in json.load(open(ev.B / 'sam_gen' / iset / 'items.json'))['items'] if x.get('map')}
    per = collections.defaultdict(list)
    for line in open(tracks if tracks.startswith('/') else ev.B / tracks):
        r = json.loads(line); vid, n = r['id'].split('__', 1); x = items.get(vid)
        if x is None or n not in ev.usable(x['clip']): continue
        tr = r['tracks'][n]; k = np.array(tr['frames']); ob = np.array([b if b is not None else [np.nan] * 4 for b in tr['xyxy']], float)
        kc = r.get('prompt_frame', 0); dt, _ = ev.clock(x['clip']); DT = ev.generated_dt(x['clip'], x['fps'], clk)
        h = ev.HZ[x['clip']]['objects'][n]['horizon']
        s = 4 + (k - kc) * dt / DT; sel = (s >= 4) & (s <= h)
        o = ob[sel]
        if len(o) < 6: continue
        d2 = o[2:] - 2 * o[1:-1] + o[:-2]; d2 = d2[np.isfinite(d2).all(1)]
        if len(d2) < 4: continue
        mad = np.median(np.abs(d2 - np.median(d2, 0)), 0)
        per[x['model']].append(float(np.median(1.4826 * mad / np.sqrt(6))))
    for m, v in sorted(per.items()):
        v = np.array(v); out[f'{name}|{m}'] = dict(n=len(v), median=round(float(np.median(v)), 2), p90=round(float(np.percentile(v, 90)), 2))
        print(f"{name:8s} {m:26s} objects={len(v):5d} noise median={np.median(v):.2f} px  p90={np.percentile(v, 90):.2f} px")
json.dump(out, open(ev.B / 'results_gen' / 'track_noise.json', 'w'), indent=1)
