"""Camera-motion compensation for generated videos (the inversion assumes the reference's fixed camera; many video models
add camera motion, which makes every object 'not explained'). Per tracked frame k: ECC affine from frame k onto frame 0 on
the BACKGROUND (tracked objects' boxes at frames 0 and k, dilated, masked out; 427x240 grey), initialised with frame k-1's
estimate; each object box at frame k is mapped into frame-0 coordinates (box of the 4 mapped corners). Frames whose ECC fails
or correlates < MIN_CORR keep NaN boxes. Output: tracks in the same format with mode 'lean+camcomp' and per-video motion
statistics. Usage: python cam_comp.py ITEMS_JSON TRACKS.jsonl [...] --out OUT.jsonl [--workers 9] [--keys KEYFILE]"""
import argparse, collections, json
from multiprocessing import get_context
import cv2
import numpy as np

SZ = (427, 240); MIN_CORR = 0.85


def mask_for(boxes, W, H):
    m = np.full((SZ[1], SZ[0]), 255, np.uint8); sx, sy = SZ[0] / W, SZ[1] / H
    for b in boxes:
        if b is None or np.isnan(b[0]): continue
        x0, y0, x1, y1 = b; pad = 0.15 * max(x1 - x0, y1 - y0) + 6
        cv2.rectangle(m, (int((x0 - pad) * sx), int((y0 - pad) * sy)), (int((x1 + pad) * sx), int((y1 + pad) * sy)), 0, -1)
    return m


def camera_mats(path, tracks):
    """per tracked frame f: 2x3 matrix mapping frame-f pixels into frame-0 pixels, ECC correlation, frame size"""
    cap = cv2.VideoCapture(path); W, H = cap.get(3), cap.get(4)
    frames = sorted({f for fr, _ in tracks.values() for f in fr})
    imgs = {}; k = 0; last = max(frames) if frames else 0
    while k <= last:
        ok, im = cap.read()
        if not ok: break
        if k in frames or k == 0: imgs[k] = cv2.cvtColor(cv2.resize(im, SZ, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        k += 1
    cap.release()
    box_at = {n: dict(zip(fr, xy)) for n, (fr, xy) in tracks.items()}
    ref = imgs.get(0); M = np.eye(2, 3, dtype=np.float32); mats = {0: np.eye(2, 3)}; corr = {0: 1.0}
    b0 = [box_at[n].get(0) for n in tracks]
    for f in frames:
        if f == 0 or f not in imgs or ref is None: continue
        msk = mask_for(b0 + [box_at[n].get(f) for n in tracks], W, H)
        try:
            cc, M2 = cv2.findTransformECC(ref, imgs[f], M.copy(), cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5), msk, 3)
        except cv2.error:
            corr[f] = 0.0; continue
        M = M2; corr[f] = float(cc)
        # M maps frame-0 coords -> frame-f coords (small size); invert to map frame f -> frame 0, in full-resolution pixels
        S = np.diag([SZ[0] / W, SZ[1] / H, 1.0]); A = np.vstack([M, [0, 0, 1]])
        mats[f] = (np.linalg.inv(S) @ np.linalg.inv(A) @ S)[:2]
    return mats, corr, W, H, frames


def compensate(args):
    key, path, tracks = args          # tracks: {name: (frames list, xyxy list)}
    mats, corr, W, H, frames = camera_mats(path, tracks)
    out, shifts = {}, []
    for n, (fr, xy) in tracks.items():
        nxy = []
        for f, b in zip(fr, xy):
            if b is None or f not in mats or corr.get(f, 0) < MIN_CORR: nxy.append(None); continue
            T = mats[f]; P = np.array([[b[0], b[1], 1], [b[2], b[1], 1], [b[0], b[3], 1], [b[2], b[3], 1]]) @ T.T
            nxy.append([float(P[:, 0].min()), float(P[:, 1].min()), float(P[:, 0].max()), float(P[:, 1].max())])
        out[n] = (fr, nxy)
    for f, T in mats.items():
        c = T @ np.array([W / 2, H / 2, 1]); shifts.append(float(np.hypot(c[0] - W / 2, c[1] - H / 2)))
    stats = dict(max_shift_px=round(max(shifts), 1) if shifts else 0.0, frames_failed=sum(1 for f in frames if corr.get(f, 0) < MIN_CORR), frames=len(frames))
    return key, out, stats


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('items'); ap.add_argument('tracks', nargs='+'); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=9); ap.add_argument('--keys')
    a = ap.parse_args()
    items = {x['key']: x for x in json.load(open(a.items))['items'] if x.get('map')}
    keys = set(open(a.keys).read().split()) if a.keys else None
    T = collections.defaultdict(dict); meta = {}
    for p in a.tracks:
        for l in open(p):
            r = json.loads(l); v, n = r['id'].split('__', 1)
            if v not in items or (keys and v not in keys): continue
            T[v][n] = (r['tracks'][n]['frames'], r['tracks'][n]['xyxy']); meta[v] = r.get('prompt_frame', 0)
    import common as c2
    jobs = [(v, c2.gt(items[v]['path']), T[v]) for v in T]
    with get_context('fork').Pool(a.workers) as pool, open(a.out, 'w') as f, open(a.out.replace('.jsonl', '_stats.jsonl'), 'w') as fs:
        for v, out, stats in pool.imap_unordered(compensate, jobs, chunksize=4):
            for n, (fr, xy) in out.items():
                f.write(json.dumps(dict(id=f'{v}__{n}', prompt_frame=meta[v], tracks={n: dict(frames=fr, xyxy=xy)}, mode='lean+camcomp')) + '\n')
            fs.write(json.dumps(dict(key=v, **stats)) + '\n')
    print('compensated', len(jobs), 'videos ->', a.out)
