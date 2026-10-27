"""Contact sheet of a reference video: SAM 3.1 box (green) and the box the TRUE replay predicts (red, visible part, frame-4
offset calibration as in evaluator.evaluate, zero time shift), for every usable object, on 8 frames from the condition
frame to the end of the longest predictability window; object names are written next to the green boxes.
Usage: python ref_overlay.py OUT_DIR CLIP PARAM [CLIP PARAM ...]"""
import os, sys
import cv2
import numpy as np
import evaluator as ev

out = sys.argv[1]; args = sys.argv[2:]; os.makedirs(out, exist_ok=True)
tracks = ev.B / 'sam_lean' / 'ref99' / 'tracks_lean.jsonl'
for clip, param in zip(args[::2], args[1::2]):
    obs, kc = ev.load_obs(tracks, clip); meta = ev.ref_meta(clip); truth = ev.truth_of(clip, param)
    lib = ev.library(clip, param, with_truth=True, workers=1)
    _, boxes = min(lib, key=lambda t: abs(np.log(t[0] / truth)))
    a = np.array([meta['scale'][0], meta['scale'][1]] * 2); hz = ev.HZ[clip]['objects']; dt, _ = ev.clock(clip)
    names = [n for n in ev.usable(clip) if n in obs]
    h_end = max([hz[n]['horizon'] for n in names] or [60])
    kmax = int((h_end - 4) * dt / meta['dt_obs']) + kc
    ks = sorted({int(round(kc + i * (kmax - kc) / 7)) for i in range(8)})
    cap = cv2.VideoCapture(str(ev.B / 'sam_lean' / 'ref99' / 'videos' / f'{clip}.mp4')); imgs = {}; k = 0
    while k <= max(ks):
        ok, im = cap.read()
        if not ok: break
        if k in ks: imgs[k] = im
        k += 1
    cap.release()
    tiles = []
    for k in ks:
        im = imgs.get(k)
        if im is None: continue
        im = im.copy(); s = int(round(4 + (k - kc) * meta['dt_obs'] / dt))
        for n in names:
            fr, ob = obs[n]; i = np.where(fr == k)[0]; i0 = np.where(fr == kc)[0]
            if n in boxes and len(i0):
                frac, sb = boxes[n]; sbv = sb * a
                if s < len(sbv) and frac[min(s, len(frac) - 1)] >= ev.MIN_VIS and frac[4] >= ev.MIN_VIS and np.isfinite(ob[i0[0], 0]):
                    pb = sbv[s] + (ob[i0[0]] - sbv[4])
                    if np.all(np.isfinite(pb)): cv2.rectangle(im, (int(pb[0]), int(pb[1])), (int(pb[2]), int(pb[3])), (40, 40, 230), 2)
            if len(i) and np.all(np.isfinite(ob[i[0]])):
                b = ob[i[0]]; cv2.rectangle(im, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (60, 220, 60), 1)
                cv2.putText(im, n.split('_', 1)[-1][:12], (int(b[0]), max(12, int(b[1]) - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 220, 60), 1)
        cv2.putText(im, f'k={k} sim frame {s} ({"in" if s <= h_end else "past"} window)', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        tiles.append(cv2.resize(im, (480, 270)))
    while len(tiles) < 8: tiles.append(np.zeros((270, 480, 3), np.uint8))
    sheet = np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:8])])
    hdr = np.full((40, sheet.shape[1], 3), 255, np.uint8)
    cv2.putText(hdr, f'{clip} {param} truth {truth}: green = SAM 3.1, red = true replay (visible part)', (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    cv2.imwrite(os.path.join(out, f'ref_{clip}_{param}.jpg'), np.vstack([hdr, sheet]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print('wrote', clip, param)
