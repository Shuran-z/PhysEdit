"""Visual QA of generated-video inversions: stratified sample (per model x result kind) -> one contact sheet per result.
Eight frames spread over the predictability windows; on each: SAM 3.1 box (green), the simulation at the PROMPTED value
(red: what the scene should do) and at the best-fitting value and shift (blue), all objects that the evaluation uses or
rejected (label = object, status). Predicted boxes are computed in the condition-frame coordinates the evaluation uses
(camera-compensated) and drawn back into frame k with the inverse camera transform. Header: model, task, parameter,
result kind, estimate, band, prompt value, per-object status. Runs on a server (needs the videos).
Usage: python qa_overlay.py RESULTS.jsonl ITEMS.json RAW_TRACKS.jsonl[,..] CAMCOMP_TRACKS.jsonl OUT_DIR --video-dirs D1,D2
       [--per-cell 2] [--seed 0] [--keys key|param,...] [--kinds point,not_explained,...]
(--kinds samples only those result kinds, e.g. to leave out the 'not_validated' items of a gated file.)"""
import argparse, collections, json, math, os, random
import cv2
import numpy as np
import evaluator as ev
import cam_comp as cc

ap = argparse.ArgumentParser(); ap.add_argument('results'); ap.add_argument('items'); ap.add_argument('raw'); ap.add_argument('comp'); ap.add_argument('out')
ap.add_argument('--video-dirs', required=True); ap.add_argument('--per-cell', type=int, default=2); ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--keys'); ap.add_argument('--clock', choices=['realtime', 'reference'], default='realtime'); ap.add_argument('--kinds')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
items = {x['key']: x for x in json.load(open(a.items))['items'] if x.get('map')}
dirs = a.video_dirs.split(',')
def video_of(key):
    for d in dirs:
        p = os.path.join(d, key + '.mp4')
        if os.path.exists(p): return p
    return None
R = [json.loads(l) for l in open(a.results)]
R = [r for r in R if 'param' in r and r['key'] in items and video_of(r['key'])]
if a.kinds: R = [r for r in R if r.get('kind') in a.kinds.split(',')]
if a.keys:
    want = set(a.keys.split(',')); sample = [r for r in R if f"{r['key']}|{r['param']}" in want]
else:
    random.seed(a.seed); cells = collections.defaultdict(list)
    for r in R: cells[(r['model'], r['kind'])].append(r)
    sample = [r for k in sorted(cells) for r in random.sample(cells[k], min(a.per_cell, len(cells[k])))]
def load(paths, keys):
    T = collections.defaultdict(dict)
    for p in paths.split(','):
        for l in open(p):
            r = json.loads(l); v, n = r['id'].split('__', 1)
            if v in keys: T[v][n] = (r['tracks'][n]['frames'], r['tracks'][n]['xyxy'])
    return T
keys = {r['key'] for r in sample}
RAW, COMP = load(a.raw, keys), load(a.comp, keys)
libs = {}
COL = {'obs': (60, 220, 60), 'truth': (40, 40, 230), 'best': (230, 120, 30)}
index = []
for r in sample:
    x = items[r['key']]; clip, p = x['clip'], r['param']
    if (clip, p) not in libs: libs[(clip, p)] = (ev.library(clip, p), ev.library(clip, p, with_truth=True))
    lib, lib_t = libs[(clip, p)]          # scoring library (as validated, D30) / with the prompted-value replay for the red boxes
    obs = {n: (np.array(fr), np.array([b if b is not None else [np.nan] * 4 for b in xy], float)) for n, (fr, xy) in COMP[r['key']].items()}
    m = x['cam_to_video']; truth = ev.truth_of(clip, p); DT = ev.generated_dt(clip, x['fps'], a.clock)
    res = ev.evaluate(clip, p, obs, 0, DT, m['scale'], lib, truth, offset=m['offset'])
    curve = res.get('curve') or []
    def nearest(v, L=lib):
        return min(L, key=lambda t: abs(math.log(t[0] / v)))
    shift_of = lambda v: min(curve, key=lambda c: abs(math.log(c[0] / v)))[2] if curve else 0.0
    vbest = res.get('est') or res.get('center') or (min(curve, key=lambda c: c[1])[0] if curve else None)
    preds = {'truth': (nearest(truth, lib_t), shift_of(truth))}
    if vbest: preds['best'] = (nearest(vbest), shift_of(vbest))
    mats, corr, W, H, frames = cc.camera_mats(video_of(r['key']), RAW[r['key']])
    dt, _ = ev.clock(clip); hz = ev.HZ[clip]['objects']
    names = [n for n in ev.usable(clip) if n in obs]
    h_end = max([hz[n]['horizon'] for n in names] or [30])
    kmax = max(1, min(max(frames) if frames else 1, int((h_end - 4) * dt / DT)))
    ks = sorted({int(round(i * kmax / 7)) for i in range(8)})
    cap = cv2.VideoCapture(video_of(r['key'])); imgs = {}; k = 0
    while k <= max(ks):
        ok, im = cap.read()
        if not ok: break
        if k in ks: imgs[k] = im
        k += 1
    cap.release()
    a4 = np.array([m['scale'][0], m['scale'][1]] * 2); b4 = np.array([m['offset'][0], m['offset'][1]] * 2)
    tiles = []
    for k in ks:
        im = imgs.get(k)
        if im is None: continue
        im = im.copy(); inv = None
        if k in mats:
            A = np.vstack([mats[k], [0, 0, 1]]); inv = np.linalg.inv(A)[:2]
        for n in names:
            fr, ob = obs[n]; raw_fr = dict(zip(*RAW[r['key']][n]))
            rb = raw_fr.get(k)
            if rb is not None and np.all(np.isfinite(rb)): cv2.rectangle(im, (int(rb[0]), int(rb[1])), (int(rb[2]), int(rb[3])), COL['obs'], 2)
            i0 = np.where(fr == 0)[0]
            if not len(i0) or np.isnan(ob[i0[0], 0]): continue
            for tag, ((v, boxes), d) in preds.items():
                if n not in boxes: continue
                frac, sb = boxes[n]; sbv = sb * a4 + b4; s = 4 + k * DT / dt + d
                if s > len(sbv) - 1 or frac[min(int(s), len(frac) - 1)] < ev.MIN_VIS: continue
                f0 = int(math.floor(s)); w = s - f0; f1 = min(f0 + 1, len(sbv) - 1)
                pb = (1 - w) * sbv[f0] + w * sbv[f1] + (ob[i0[0]] - sbv[4])          # condition-frame offset calibration
                if inv is not None:
                    P = np.array([[pb[0], pb[1], 1], [pb[2], pb[3], 1]]) @ inv.T; pb = [P[0, 0], P[0, 1], P[1, 0], P[1, 1]]
                if not np.all(np.isfinite(pb)): continue
                cv2.rectangle(im, (int(pb[0]), int(pb[1])), (int(pb[2]), int(pb[3])), COL[tag], 1 if tag == 'best' else 2)
        cv2.putText(im, f'k={k} t={k * DT:.2f}s', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        tiles.append(cv2.resize(im, (427, 240)))
    while len(tiles) < 8: tiles.append(np.zeros((240, 427, 3), np.uint8))
    sheet = np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:8])])
    st = ', '.join(f"{n.split('_', 1)[-1][:14]}={d['status'][:9]}({d['best_loss']})" for n, d in res.get('object_diagnostics', {}).items())
    band = res.get('band')
    head = [f"{r['key']}  param={p}  kind={res.get('kind')}  est={res.get('est') and round(res['est'], 4)}  band={band and [round(band[0], 4), round(band[1], 4)]}  prompt={truth}",
            f"objects: {st}"[:230], "green = SAM 3.1 box | red = simulation at the prompted value | blue = best-fitting value & shift"]
    hdr = np.full((70, sheet.shape[1], 3), 255, np.uint8)
    for i, t in enumerate(head): cv2.putText(hdr, t, (8, 20 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    fn = f"{r['model']}__{res.get('kind')}__{r['key']}__{p}.jpg"
    cv2.imwrite(os.path.join(a.out, fn), np.vstack([hdr, sheet]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    index.append(dict(file=fn, key=r['key'], param=p, model=r['model'], kind=res.get('kind'), est=res.get('est'), band=band, prompt=truth,
                      objects=res.get('object_diagnostics')))
json.dump(index, open(os.path.join(a.out, 'index.json'), 'w'), indent=1, default=float)
print('sheets', len(index), '->', a.out)
