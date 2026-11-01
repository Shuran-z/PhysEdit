"""Common reference-comparison metrics of generated videos, next to the benchmark's own parameter metrics (user request
2026-10-26: reuse the meaningful PhysEdit V/P metrics, in the form common in papers). Each generated video is compared with
the reference continuation of its task (the same scene and prompted physics, from the condition frame on), on physical
time (generated: realtime clock, E2; synthetic sets: --clock reference) and in reference pixels (the generated video is
mapped back with its registration, as in the evaluation).
- Trajectory (PhysEdit 'trajectory error' -> ADE / FDE): per tracked object, the displacement from its position at the
  condition time, generated vs reference, error normalised by the image diagonal; ADE = mean over the time grid, FDE = at
  the last common time; ade_static = the ADE of a video in which nothing moves (scale of the reference motion).
  Camera-compensated SAM 3.1 boxes (box centres), linear interpolation only between adjacent valid frames.
- Motion agreement (PhysEdit 'motion-region IoU' -> Physics-IQ, Motamed et al. 2025): binary motion masks from frame
  differences on a 10 Hz grid; spatial IoU (where motion happens), spatiotemporal IoU (where and when), weighted spatial
  IoU (where and how much), MSE of the frames (RGB in [0, 1]). No camera compensation: the prompts ask for a fixed camera.
- Video fidelity (PhysEdit SSIM / PSNR of the reference continuation, user 2026-10-26: video, not the condition image):
  PSNR and SSIM of every grid frame after the condition time (RGB at the mask resolution 427x240, scikit-image 0.24 SSIM
  with a Gaussian window, sigma 1.5), averaged over the video; identical frames are capped at 100 dB.
Window: from the condition time to min(5 s, end of either video).
--frozen: the no-motion baseline instead of the generated videos, one row per clip of SET: the condition frame (reference
frame 4) held still for the whole reference window (what a model scores by not moving anything). Usage:
python common_metrics.py SET TRACKS.jsonl [...] --out NAME [--video-dir DIR] [--clock realtime|reference] [--workers N]
python common_metrics.py SET --frozen --out frozen
  (SET: sam_gen/<SET>/items.json; videos DIR/<key>.mp4, default the item's path) -> results_gen/common_<NAME>.jsonl"""
import argparse, collections, json, math
from multiprocessing import get_context
from pathlib import Path
import cv2
import numpy as np
from skimage.metrics import structural_similarity

import evaluator as ev
from paths import gt

T_MAX, GRID_HZ = 5.0, 10.0
REF = ev.B / 'sam_lean' / 'reference'


def read_frames(path, wanted):
    """{index: BGR frame} for the wanted native frame indices"""
    cap = cv2.VideoCapture(str(path)); out = {}; i = 0; last = max(wanted) if wanted else -1
    while i <= last:
        ok, im = cap.read()
        if not ok: break
        if i in wanted: out[i] = im
        i += 1
    cap.release(); return out


def tracks(paths, keep):
    out = collections.defaultdict(dict)
    for p in paths:
        for line in open(p):
            r = json.loads(line); vid, n = r['id'].split('__', 1)
            if vid not in keep: continue
            tr = r['tracks'][n]
            out[vid][n] = (np.array(tr['frames']), np.array([b if b is not None else [np.nan] * 4 for b in tr['xyxy']], float))
    return out


def centre_at(fr, bx, t, dt, k0):
    """box centre at physical time t (frames k0 + t / dt), linear between adjacent valid frames, else NaN"""
    ok = np.isfinite(bx).all(1); fr, bx = fr[ok], bx[ok]
    if not len(fr): return np.full(2, np.nan)
    x = k0 + t / dt; c = np.stack([(bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2], 1)
    j = np.searchsorted(fr, x)
    if j < len(fr) and abs(fr[j] - x) < 1e-6: return c[j]
    if j == 0 or j == len(fr) or fr[j] - fr[j - 1] > 1: return np.full(2, np.nan)
    w = (x - fr[j - 1]) / (fr[j] - fr[j - 1]); return (1 - w) * c[j - 1] + w * c[j]


def trajectory(gen, ref, to_ref, dt_g, dt_r, T, diag):
    """{ade, fde, ade_static, n_obj}; gen boxes in generated pixels (frame 0 = condition), ref boxes in reference pixels"""
    grid = np.arange(1, int(T * GRID_HZ * 3) + 1) / (GRID_HZ * 3)            # 30 Hz grid after the condition time
    per = []
    for n in sorted(set(gen) & set(ref)):   # fixed order: the means are then bit-reproducible across processes
        (fg, bg), (fr, br) = gen[n], ref[n]
        g0, r0 = centre_at(fg, bg, 0.0, dt_g, 0), centre_at(fr, br, 0.0, dt_r, 4)
        if not (np.isfinite(g0).all() and np.isfinite(r0).all()): continue
        e, s = [], []
        for t in grid:
            g, r = centre_at(fg, bg, t, dt_g, 0), centre_at(fr, br, t, dt_r, 4)
            if not (np.isfinite(g).all() and np.isfinite(r).all()): continue
            dg = to_ref(g) - to_ref(g0); dr = r - r0
            e.append(np.linalg.norm(dg - dr) / diag); s.append(np.linalg.norm(dr) / diag)
        if len(e) >= 3: per.append((np.mean(e), e[-1], np.mean(s)))
    if not per: return dict(n_obj=0)
    a = np.array(per); return dict(ade=float(a[:, 0].mean()), fde=float(a[:, 1].mean()), ade_static=float(a[:, 2].mean()), n_obj=len(per))


def motion_masks(frames):
    g = [cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255, (5, 5), 0) for f in frames]
    m = [(np.abs(b - a) > A.motion_thr).astype(np.uint8) for a, b in zip(g, g[1:])]
    if A.open: m = [cv2.morphologyEx(x, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) for x in m]
    return [x.astype(bool) for x in m]


def iou(a, b):
    u = np.logical_or(a, b).sum(); return 1.0 if u == 0 else float(np.logical_and(a, b).sum() / u)


def physics_iq(gs, rs):
    mg, mr = motion_masks(gs), motion_masks(rs)
    sp = iou(np.any(mg, 0), np.any(mr, 0))
    st = [iou(a, b) for a, b in zip(mg, mr) if np.logical_or(a, b).any()]
    wg, wr = np.sum(mg, 0).astype(float), np.sum(mr, 0).astype(float); den = np.maximum(wg, wr).sum()
    mse = float(np.mean([np.mean(((a.astype(np.float32) - b.astype(np.float32)) / 255) ** 2) for a, b in zip(gs[1:], rs[1:])]))
    return dict(spatial_iou=sp, spatiotemporal_iou=float(np.mean(st)) if st else 1.0,
                weighted_spatial_iou=1.0 if den == 0 else float(np.minimum(wg, wr).sum() / den), mse=mse,
                motion_area_gen=float(np.mean(mg)), motion_area_ref=float(np.mean(mr)))   # mean share of moving pixels per step


def fidelity(gs, rs):
    """video PSNR / SSIM over the continuation (the grid frames after the condition time)"""
    ps = [min(float(cv2.PSNR(g, c)), 100.0) for g, c in zip(gs[1:], rs[1:])]
    ss = [float(structural_similarity(g, c, channel_axis=2, gaussian_weights=True, sigma=1.5, use_sample_covariance=False,
                                      data_range=255)) for g, c in zip(gs[1:], rs[1:])]
    return dict(video_psnr=float(np.mean(ps)), video_ssim=float(np.mean(ss)))


def ref_clip(clip):
    meta = ev.ref_meta(clip); cap = cv2.VideoCapture(str(REF / 'videos' / f'{clip}.mp4')); n_ref = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
    ref_tr = {n: (np.arange(len(b)), b) for n, b in ev.load_tracks_indexed(REF / 'tracks_lean.jsonl', clip).items()}
    return meta['dt_obs'], np.array(meta['scale']), n_ref, W, H, ref_tr


def run_frozen(job):
    """no-motion baseline: the condition frame held still for the whole reference window"""
    clip, _ = job
    dt_r, _, n_ref, W, H, ref_tr = ref_clip(clip); diag = math.hypot(W, H)
    T = min(T_MAX, (n_ref - 1 - 4) * dt_r); r = dict(key=f'frozen_{clip}', clip=clip, model='frozen', window_s=round(T, 3))
    try:
        K = int(T / dt_r) + 2
        still = {n: (np.arange(K), np.repeat(b[4:5], K, 0)) for n, (_, b) in ref_tr.items() if len(b) > 4}
        r.update(trajectory(still, ref_tr, lambda p: p, dt_r, dt_r, T, diag))
        ir = [4 + int(math.floor(t / dt_r + 0.5 - 1e-9)) for t in np.arange(0, int(T * GRID_HZ) + 1) / GRID_HZ]
        fr = read_frames(REF / 'videos' / f'{clip}.mp4', set(ir))
        rs = [cv2.resize(fr[i], tuple(A.mask_size), interpolation=cv2.INTER_AREA) for i in ir]; gs = [rs[0]] * len(rs)
        r.update(physics_iq(gs, rs)); r.update(fidelity(gs, rs))
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {str(e)[:160]}'
    return [r]


def run_clip(job):
    clip, xs = job
    dt_r, sr, n_ref, W, H, ref_tr = ref_clip(clip); diag = math.hypot(W, H)
    ref_cache = {}; out = []
    for x in xs:
        r = dict(key=x['key'], clip=clip, model=x['model'], seed=x.get('seed'), annotation=x.get('annotation'))
        try:
            m = x['cam_to_video']; sg, og = np.array(m['scale']), np.array(m['offset'])
            to_ref = lambda p: (p - og) / sg * sr                                    # generated pixels -> reference pixels
            dt_g = ev.generated_dt(clip, x['fps'], A.clock)
            T = min(T_MAX, (x['frames'] - 1) * dt_g, (n_ref - 1 - 4) * dt_r); r['window_s'] = round(T, 3)
            r.update(trajectory(TR.get(x['key'], {}), ref_tr, to_ref, dt_g, dt_r, T, diag))
            ts = np.arange(0, int(T * GRID_HZ) + 1) / GRID_HZ
            ig = [int(math.floor(t / dt_g + 0.5 - 1e-9)) for t in ts]; ir = [4 + int(math.floor(t / dt_r + 0.5 - 1e-9)) for t in ts]
            vg = read_frames(Path(A.video_dir) / f"{x['key']}.mp4" if A.video_dir else gt(x['path']), set(ig))
            need = set(ir) - set(ref_cache)
            if need: ref_cache.update(read_frames(REF / 'videos' / f'{clip}.mp4', need))
            if len(ts) >= 3 and all(i in vg for i in ig) and all(i in ref_cache for i in ir):
                Mi = np.array([[sg[0] / sr[0], 0, og[0]], [0, sg[1] / sr[1], og[1]]], np.float32)   # reference pixel -> generated pixel
                warp = lambda im: cv2.warpAffine(im, Mi, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
                small = lambda im: cv2.resize(im, tuple(A.mask_size), interpolation=cv2.INTER_AREA)
                gs, rs = [small(warp(vg[i])) for i in ig], [small(ref_cache[i]) for i in ir]
                r.update(physics_iq(gs, rs)); r.update(fidelity(gs, rs))
            else: r['video_status'] = 'frames_missing'
        except Exception as e:
            r['error'] = f'{type(e).__name__}: {str(e)[:160]}'
        out.append(r)
    return out


ap = argparse.ArgumentParser(); ap.add_argument('set'); ap.add_argument('tracks', nargs='*'); ap.add_argument('--out', required=True)
ap.add_argument('--video-dir'); ap.add_argument('--clock', choices=['realtime', 'reference'], default='realtime'); ap.add_argument('--workers', type=int, default=16)
ap.add_argument('--limit', type=int, help='first N items (tests)'); ap.add_argument('--sample', type=int, help='every N-th item (tests)')
ap.add_argument('--mask-size', type=int, nargs=2, default=[427, 240], help='motion-mask resolution (half of 854x480)')
ap.add_argument('--motion-thr', type=float, default=0.03, help='frame-difference threshold (grey level in [0, 1], 5x5 blur)')
ap.add_argument('--open', type=int, default=0, help='3x3 opening of the masks')
ap.add_argument('--frozen', action='store_true', help='no-motion baseline (condition frame held still), one row per clip of SET')
A = ap.parse_args()
ITEMS = [x for x in json.load(open(ev.B / 'sam_gen' / A.set / 'items.json'))['items'] if x.get('cam_to_video')][::A.sample or 1][:A.limit]
TR = tracks(A.tracks, {x['key'] for x in ITEMS})
if __name__ == '__main__':
    by = collections.defaultdict(list)
    for x in ITEMS: by[x['clip']].append(x)
    cv2.setNumThreads(1)
    with get_context('fork').Pool(A.workers) as pool:
        rows = [r for rs in pool.imap_unordered(run_frozen if A.frozen else run_clip, sorted(by.items()), chunksize=1) for r in rs]
    (ev.B / 'results_gen' / f'common_{A.out}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    keys = ('ade', 'fde', 'ade_static', 'spatial_iou', 'spatiotemporal_iou', 'weighted_spatial_iou', 'mse', 'video_psnr', 'video_ssim')
    by_m = collections.defaultdict(list)
    for r in rows: by_m[r['model']].append(r); by_m['all'].append(r)
    print(f"{'model':26s} {'n':>5s} " + ' '.join(f'{k:>10s}' for k in keys))
    for m, rs in sorted(by_m.items(), key=lambda t: (t[0] == 'all', t[0])):
        print(f'{m:26s} {len(rs):5d} ' + ' '.join(f"{np.median([r[k] for r in rs if k in r]) if any(k in r for r in rs) else float('nan'):10.4f}" for k in keys))
    print(f"errors: {sum('error' in r for r in rows)}, frames missing: {sum(r.get('video_status') == 'frames_missing' for r in rows)}")
