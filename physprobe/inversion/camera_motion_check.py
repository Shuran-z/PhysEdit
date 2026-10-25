"""Camera-motion check on generated videos: ECC affine (whole frame, small size) between frame 0 and the frame half way
through the tracked range; reports translation (px at 854 width) and scale change. A fixed-camera assumption underlies the
inversion, so videos with camera motion cannot be explained by any simulated parameter. Usage: python camera_motion_check.py N_PER_MODEL"""
import json, random, sys, collections, statistics as st
from multiprocessing import get_context
import cv2, numpy as np
from paths import WORK as B, gt
items = json.load(open(B / 'sam_gen/all/items.json'))['items']
res = {json.loads(l)['key'] + '|' + json.loads(l)['param']: json.loads(l) for l in open(B / 'results_gen/all_cc.jsonl') if 'param' in json.loads(l)}
random.seed(0); by = collections.defaultdict(list)
for x in items: by[x['model']].append(x)
sample = [x for m in sorted(by) for x in random.sample(by[m], min(int(sys.argv[1]), len(by[m])))]
def motion(x):
    cap = cv2.VideoCapture(gt(x['path'])); n = int(cap.get(7)); ok, a = cap.read(); cap.set(1, n // 2); ok2, b = cap.read(); cap.release()
    if not (ok and ok2): return x['key'], None
    sz = (427, 240); A = cv2.cvtColor(cv2.resize(a, sz), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255; Bm = cv2.cvtColor(cv2.resize(b, sz), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    try: cc, M = cv2.findTransformECC(A, Bm, np.eye(2, 3, dtype=np.float32), cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), None, 5)
    except cv2.error: return x['key'], dict(fail=True)
    return x['key'], dict(shift=float(np.hypot(M[0, 2], M[1, 2]) * 854 / 427), scale=float(abs((M[0, 0] + M[1, 1]) / 2 - 1)), corr=float(cc))
with get_context('fork').Pool(8) as p: out = dict(p.map(motion, sample))
print(f"{'model':26s} {'n':>3s} {'median shift px':>15s} {'moving(>4px or >1%)':>19s} {'not_explained(g) moving vs static':>34s}")
for m in sorted(by):
    ks = [x['key'] for x in sample if x['model'] == m and out.get(x['key']) and not out[x['key']].get('fail')]
    mv = [k for k in ks if out[k]['shift'] > 4 or out[k]['scale'] > 0.01]
    ne = lambda kk: sum(res.get(k + '|g', {}).get('kind') == 'not_explained' for k in kk) / max(1, len(kk))
    st_ = [k for k in ks if k not in mv]
    print(f"{m:26s} {len(ks):3d} {st.median(out[k]['shift'] for k in ks) if ks else float('nan'):15.1f} {100 * len(mv) / max(1, len(ks)):18.0f}% {100 * ne(mv):16.0f}% vs {100 * ne(st_):3.0f}%")
json.dump(out, open(B / 'results_gen/camera_motion_sample.json', 'w'))
