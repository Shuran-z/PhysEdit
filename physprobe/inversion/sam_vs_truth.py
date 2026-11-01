"""Which of several SAM 3.1 tracks files is closer to the truth? For each tracked object: SAM box vs the visible-part box of
the recorded trajectory (common.visible_boxes, z-buffer over every scene object), after the frame-4 offset calibration,
on frames where >= MIN_VIS of the object is visible; reported inside the predictability window and over the whole video.
Used when two tracking hosts disagree (A800 vs hupanwen, issue log F8).
Usage: python sam_vs_truth.py CLIP TRACKS1.jsonl [TRACKS2.jsonl ...]"""
import json, sys
import numpy as np
import common as c2
sys.argv, rest = sys.argv[:1], sys.argv[1:]
import evaluator as e2

clip, files = rest[0], rest[1:]
hz = json.load(open(c2.B / 'horizons.json'))[clip]['objects']
meta, cam = c2.recorded(clip), c2.camera(clip)
obs = {f: e2.load_tracks_indexed(f, clip) for f in files}
names = sorted(n for n in set().union(*obs.values()) if n in hz)   # moving objects only
traj = {}
for n in names:
    q0 = c2.initial_poses(clip)[n][3:]
    traj[n] = np.array([[*o['position'], *(o.get('quaternion_xyzw') or q0)]
                        for o in (next(o for o in fr['objects'] if o['name'] == n) for fr in meta['frames'])])
vb = c2.visible_boxes(clip, cam, traj)
for n in names:
    frac, pb = vb[n]; s, h = hz[n]['start'], hz[n]['horizon']
    print(f"{clip} {n}: window {s}-{h}, visible fraction at frame 4 {frac[4]:.2f}, min {np.nanmin(frac[4:]):.2f}")
    for f in files:
        o = obs[f].get(n)
        if o is None: print(f"   {f.split('/')[-1]:28s} not tracked"); continue
        m = min(len(o), len(pb)); o = o[:m] - (o[4] - pb[4]); fr = np.arange(4, m)
        good = fr[(frac[fr] >= e2.MIN_VIS) & ~np.isnan(o[fr, 0]) & ~np.isnan(pb[fr, 0])]
        e = np.abs(o[good] - pb[good]).max(axis=1)
        inw = (good >= max(4, s)) & (good < h)
        q = lambda x: f"median {np.median(x):6.2f} 90% {np.percentile(x, 90):6.2f} max {x.max():6.1f} px ({len(x)} fr)" if len(x) else "no frames"
        print(f"   {f.split('/')[-1]:28s} window: {q(e[inw])} | whole video: {q(e)}")
