"""Known-answer test of cam_comp.py: the synthetic generated-like videos (sam_gen/s15v) get a camera move per frame k
(translation 1.2k, 0.4k px and zoom 1 + 0.002k about the centre); the boxes SAM would see are the original lean tracks moved
the same way. cam_comp must undo it: evaluation of the compensated tracks should match the unmoved one.
Usage: python make_pan_test.py -> sam_gen/s15v_pan/{items.json, tracks_moved.jsonl, videos/}"""
import json
from pathlib import Path
import cv2, numpy as np
from paths import WORK as B, gt
S = B / 'sam_gen/s15v'; D = B / 'sam_gen/s15v_pan'; (D / 'videos').mkdir(parents=True, exist_ok=True)
def Mk(k, W, H):
    s = 1 + 0.002 * k; return np.float32([[s, 0, (1 - s) * W / 2 + 1.2 * k], [0, s, (1 - s) * H / 2 + 0.4 * k]])
items = json.load(open(S / 'items.json'))
for x in items['items']:
    src = gt(x['path']); dst = D / 'videos' / Path(src).name
    cap = cv2.VideoCapture(src); W, H = int(cap.get(3)), int(cap.get(4)); fps = cap.get(5)
    vw = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H)); k = 0
    while True:
        ok, im = cap.read()
        if not ok: break
        vw.write(cv2.warpAffine(im, Mk(k, W, H), (W, H), borderMode=cv2.BORDER_REPLICATE)); k += 1
    vw.release(); x['path'] = str(dst); x['W'], x['H'] = W, H
json.dump(items, open(D / 'items.json', 'w'))
size = {x['key']: (x['W'], x['H']) for x in items['items']}
with open(D / 'tracks_moved.jsonl', 'w') as f:
    for l in open(S / 'tracks_lean.jsonl'):
        r = json.loads(l); v, n = r['id'].split('__', 1); W, H = size[v]; tr = r['tracks'][n]; xy = []
        for k, b in zip(tr['frames'], tr['xyxy']):
            if b is None: xy.append(None); continue
            M = Mk(k, W, H); P = np.array([[b[0], b[1], 1], [b[2], b[3], 1]]) @ M.T
            xy.append([float(P[0, 0]), float(P[0, 1]), float(P[1, 0]), float(P[1, 1])])
        tr['xyxy'] = xy; f.write(json.dumps(r) + '\n')
print('moved', len(items['items']), 'videos')
