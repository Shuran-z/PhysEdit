"""Jobs for the SAM 3.1 lean tracker (server_code/sam_tracker.py) on reference videos: one job per video, every non-fixed
scene object prompted at the condition frame (index 4) with the box of its VISIBLE part (z-buffer over all scene objects
at the known initial poses, common.visible_boxes), scaled from the camera resolution to the video's; objects less than
20 % visible are not prompted. Usage: python make_lean_jobs.py NAME REMOTE_DIR CLIP [CLIP ...] | --all
  -> sam_lean/<NAME>/jobs.jsonl (video paths under REMOTE_DIR/videos) + videos/ (local copies to upload)"""
import json, shutil, sys
from pathlib import Path
import cv2
import numpy as np
import common as c2

name, remote, clips = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3:]
hz = json.load(open(c2.B / 'horizons.json'))
if clips == ['--all']: clips = sorted(c for c, h in hz.items() if h.get('status') == 'OK' and c != 'T06_C04')
LOCAL = c2.B / 'sam_lean' / name; (LOCAL / 'videos').mkdir(parents=True, exist_ok=True)
s1 = {x['clip']: x['path'] for x in json.load(open(c2.READY / 'reference_videos.json'))}
jobs = []
for clip in clips:
    cam = c2.camera(clip); poses = c2.initial_poses(clip)
    dst = LOCAL / 'videos' / f'{clip}.mp4'
    if not dst.exists(): shutil.copy(s1[clip], dst)
    cap = cv2.VideoCapture(str(dst)); W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
    sx, sy = W / cam[5], H / cam[6]
    movers = {}
    for n, p in poses.items():
        try: s = c2.spec(clip, n)
        except KeyError: continue
        if not s.get('fixed'): movers[n] = np.array([p])
    vb = c2.visible_boxes(clip, cam, movers)
    objs = {}
    for n, (frac, box) in vb.items():
        if frac[0] < 0.2 or np.isnan(box[0, 0]): continue
        b = box[0]; b = [max(0, round(b[0] * sx)), max(0, round(b[1] * sy)), min(W - 1, round(b[2] * sx)), min(H - 1, round(b[3] * sy))]
        if b[2] - b[0] >= 2 and b[3] - b[1] >= 2: objs[n] = b
    jobs.append(dict(id=clip, video=f'{remote}/videos/{clip}.mp4', prompt_frame=4, objects=objs))
    print(clip, len(objs), 'objects prompted of', len(movers), 'non-fixed', flush=True)
(LOCAL / 'jobs.jsonl').write_text(''.join(json.dumps(j) + '\n' for j in jobs))
print(len(jobs), 'jobs ->', LOCAL / 'jobs.jsonl')
