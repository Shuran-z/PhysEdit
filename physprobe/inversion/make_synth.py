"""Known-answer test of the GENERATED-video path: synthetic 'generated' videos made from the reference videos (truth known).
Starting at the condition frame (index 4) every STEP-th reference frame is kept (playback fps = reference fps / STEP, so the
clock is exact), at most N frames, and every frame is warped by x' = AX x + BX, y' = AY y + BY (default: the VideoGPA
mapping measured by gen_register.py, x 1.0264 / -11.3 px). The items go through the same make_gen_jobs.build() as real
generated videos (registration, prompts, tracking range). Usage:
  python make_synth.py NAME REMOTE_DIR [--step 2] [--frames 81] [--ax 1.0264 --bx -11.3 --ay 1 --by 0] [CLIP ...]"""
import argparse, json
from pathlib import Path
import cv2
import numpy as np
import common as c2
import make_gen_jobs as mg

ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('remote'); ap.add_argument('clips', nargs='*')
ap.add_argument('--step', type=int, default=2); ap.add_argument('--frames', type=int, default=81)
ap.add_argument('--ax', type=float, default=1.0264); ap.add_argument('--bx', type=float, default=-11.3)
ap.add_argument('--ay', type=float, default=1.0); ap.add_argument('--by', type=float, default=0.0)
a = ap.parse_args()
RD = mg.RD
clips = a.clips or sorted(c for c, h in mg.HZ.items() if h.get('status') == 'OK' and c != 'T06_C04')
OUT = c2.B / 'sam_gen' / a.name / 'synth_videos'; OUT.mkdir(parents=True, exist_ok=True)
M = np.float32([[a.ax, 0, a.bx], [0, a.ay, a.by]])
items = []
for clip in clips:
    src = c2.B / 'sam_lean' / 'ref99' / 'videos' / f'{clip}.mp4'
    cap = cv2.VideoCapture(str(src)); fps = cap.get(cv2.CAP_PROP_FPS); W, H = int(cap.get(3)), int(cap.get(4))
    frames = []
    k = 0
    while True:
        ok, im = cap.read()
        if not ok: break
        if k >= 4 and (k - 4) % a.step == 0 and len(frames) < a.frames: frames.append(cv2.warpAffine(im, M, (W, H), borderMode=cv2.BORDER_REPLICATE))
        k += 1
    cap.release()
    key = f'synth_{a.name}_{clip}'; dst = OUT / f'{key}.mp4'
    vw = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*'mp4v'), fps / a.step, (W, H))
    for im in frames: vw.write(im)
    vw.release()
    items.append(dict(key=key, seed=-1, annotation=-1, model=f'synth_{a.name}', clip=clip, item=RD[clip]['anonymous_id'], path=str(dst),
                      synthetic=dict(step=a.step, frames=len(frames), map=dict(scale=(a.ax, a.ay), offset=(a.bx, a.by)))))
    print(clip, len(frames), 'frames at', fps / a.step, 'fps', flush=True)
mg.build(items, a.name, a.remote)
