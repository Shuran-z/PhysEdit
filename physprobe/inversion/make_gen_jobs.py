"""Generated videos -> SAM 3.1 lean jobs + per-item metadata for eval_generated.py.
Per item (seed / annotation / model / anonymous clip): task from FORMAL_V3_ITEM_VERIFIED.json, video = resized.mp4 (the
model output resized back to the reference resolution), native fps from the item record. Pixel mapping = affine ECC
registration of the condition image onto the first frame (gen_register.py); an item whose registration fails uses its
model's median mapping and is flagged. Prompts: visible-part boxes of every non-fixed object at the condition state
(camera pixels -> condition image -> video), prompt frame 0. Tracking stops at the frame where the last predictability
window of the task ends plus the 20-frame shift margin (later frames are never used).
Prompt-corrected deliveries (v6, 31 scenes, 2026-10-25) keep the same layout with V6_ITEM_VERIFIED.json: --gen-dir.
Usage: python make_gen_jobs.py NAME REMOTE_DIR [--gen-dir DIR] [--workers N] [--skip NAME1,NAME2] [--models m1,m2] [--seeds 0,1,2] [--annotations 1,2,3] [--limit N]
  -> sam_gen/<NAME>/jobs.jsonl (videos REMOTE_DIR/videos/<item key>.mp4), items.json, upload list"""
import argparse, json, math, statistics as st
from multiprocessing import get_context
from pathlib import Path
import cv2
import numpy as np
import common as c2
import gen_register as gr

G = Path(c2.gt('/Users/zhangshuran/data/projects/PhysProbe/data/generated/author_core100_english_three_variants_v3_20261020'))
CI = c2.W.parent / 'author_core100_preparation_20261019_v1/condition_images'
HZ = json.load(open(c2.B / ('horizons33.json' if (c2.B / 'horizons33.json').exists() else 'horizons32.json')))
RD = {json.loads(l)['clip_id']: json.loads(l) for l in open(c2.W.parent / 'core100_known_condition_readiness_20261021_v1/readiness100.jsonl')}


def _register(x):
    r = gr.register(CI / f"{x['item']}.png", x['path'])
    cap = cv2.VideoCapture(x['path']); fps, frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    return r, fps, frames


def build(items, name, remote, workers=1):
    OUT = c2.B / 'sam_gen' / name; OUT.mkdir(parents=True, exist_ok=True)
    # registration (per item, model median as fallback)
    if workers > 1:
        cv2.setNumThreads(1)
        with get_context('fork').Pool(workers) as pool: regs = pool.map(_register, items, chunksize=4)
    else: regs = [_register(x) for x in items]
    for x, (r, fps, frames) in zip(items, regs): x['registration'] = r; x['fps'] = fps; x['frames'] = frames
    med = {}
    for m in {x['model'] for x in items}:
        ok = [x['registration'] for x in items if x['model'] == m and x['registration'].get('ok')]
        if ok: med[m] = dict(scale=(st.median(r['scale'][0] for r in ok), st.median(r['scale'][1] for r in ok)), offset=(st.median(r['offset'][0] for r in ok), st.median(r['offset'][1] for r in ok)))
    jobs = []
    cache = {}
    for x in items:
        clip = x['clip']; r = x['registration']
        if r.get('ok'): x['map'] = dict(scale=r['scale'], offset=r['offset'], source='item')
        elif x['model'] in med: x['map'] = dict(med[x['model']], source='model_median')
        else: x['map'] = None; continue
        cam = c2.camera(clip)
        W, H = r.get('condition_size') or (cam[5], cam[6])
        sx, sy = W / cam[5], H / cam[6]
        ax, ay = x['map']['scale']; bx, by = x['map']['offset']
        x['cam_to_video'] = dict(scale=(sx * ax, sy * ay), offset=(bx, by))
        if clip not in cache:
            poses = c2.initial_poses(clip); movers = {}
            for n, p in poses.items():
                try: sp = c2.spec(clip, n)
                except KeyError: continue
                if not sp.get('fixed'): movers[n] = np.array([p])
            cache[clip] = c2.visible_boxes(clip, cam, movers)
        Wv, Hv = r.get('video_size') or (W, H)
        objs = {}
        for n, (frac, box) in cache[clip].items():
            if frac[0] < 0.2 or np.isnan(box[0, 0]): continue
            b = box[0]
            b = [max(0, round(b[0] * sx * ax + bx)), max(0, round(b[1] * sy * ay + by)), min(Wv - 1, round(b[2] * sx * ax + bx)), min(Hv - 1, round(b[3] * sy * ay + by))]
            if b[2] - b[0] >= 2 and b[3] - b[1] >= 2: objs[n] = b
        dt = float(RD[clip]['physical_seconds_per_frame']); pvp = float(RD[clip]['playback_vs_physics'])
        x['dt_obs'] = pvp / x['fps']
        h_end = max(o['horizon'] for o in HZ[clip]['objects'].values()) + 21          # simulation frames
        last = math.ceil((h_end - 4) * dt / x['dt_obs']) + 1                            # generated frames after the condition frame
        jobs.append(dict(id=x['key'], video=f"{remote}/videos/{x['key']}.mp4", prompt_frame=0, last_frame=min(x['frames'] - 1, last), objects=objs))
    (OUT / 'jobs.jsonl').write_text(''.join(json.dumps(j) + '\n' for j in jobs))
    json.dump(dict(items=items, model_median_map=med), open(OUT / 'items.json', 'w'), indent=1)
    (OUT / 'upload.txt').write_text(''.join(f"{x['path']}\t{x['key']}.mp4\n" for x in items if x.get('map')))
    bad = [x['key'] for x in items if not x['registration'].get('ok')]
    print(len(items), 'items,', len(jobs), 'jobs,', len(bad), 'registrations fell back to the model median:', bad[:8])
    print('frames tracked: mean', round(st.mean(j['last_frame'] + 1 for j in jobs), 1), 'of', round(st.mean(x['frames'] for x in items), 1))
    return items, jobs


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('remote')
    ap.add_argument('--models'); ap.add_argument('--seeds', default='0,1,2'); ap.add_argument('--annotations', default='1,2,3'); ap.add_argument('--limit', type=int)
    ap.add_argument('--gen-dir', help='generation delivery root (default: the v3 three-variant run)')
    ap.add_argument('--workers', type=int, default=1, help='parallel registration processes')
    ap.add_argument('--skip', help='comma-separated job names (sam_gen/<name>/items.json) whose keys are already tracked (incremental deliveries)')
    a = ap.parse_args()
    if a.gen_dir: G = Path(c2.gt(a.gen_dir))
    items = []
    for s in a.seeds.split(','):
        for an in a.annotations.split(','):
            for md in sorted((G / f'seed{s}' / f'annotation{an}').iterdir()):
                if a.models and md.name not in a.models.split(','): continue
                for it in sorted((md / 'generated').iterdir()):
                    f = next((it / n for n in ('FORMAL_V3_ITEM_VERIFIED.json', 'V6_ITEM_VERIFIED.json') if (it / n).exists()), None)
                    if f is None or not (it / 'resized.mp4').exists(): continue
                    meta = json.load(open(f)); clip = meta['clip_id']
                    if clip == 'T06_C04' or HZ.get(clip, {}).get('status') != 'OK': continue
                    items.append(dict(key=f"s{s}a{an}_{md.name}_{clip}", seed=int(s), annotation=int(an), model=md.name, clip=clip, item=it.name, path=str(it / 'resized.mp4')))
    if a.skip:
        done = {x['key'] for n in a.skip.split(',') for x in json.load(open(c2.B / 'sam_gen' / n / 'items.json'))['items']}
        items = [x for x in items if x['key'] not in done]
    if a.limit: items = items[:a.limit]
    build(items, a.name, a.remote, a.workers)
