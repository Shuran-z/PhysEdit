"""Integration (G0) verdict for all 100 Core100 tasks: can the original simulation be replayed at the true parameters?
Sources: batch-1 C03 replays (g0/, g0v2/, g0rep/), batch-2 replays (G0b2_*, follow-ups G0b2r_*), video-only overlays
(T06/T09/T10, visual check), the reference explosion audit. Primary object = moving object of the readiness table's
main-contact-friction pair. Writes INTEGRATION_STATUS.json and prints the table."""
import gzip, json, sys
from pathlib import Path
import numpy as np

from paths import WORK as B, CODE, gt   # data dir (outside git) / code dir
W = B.parents[1]
sys.argv = ['x']
exec(open(B / 'g0_compare2.py').read().split("prefix = sys.argv")[0])   # man, bound, recorded()
rows = {json.loads(l)['clip_id']: json.loads(l) for l in open(W.parent / 'core100_known_condition_readiness_20261021_v1/readiness100.jsonl')}
import csv
mcf = {r['clip_id']: json.loads(r['main_contact_friction']) for r in csv.DictReader(open(W.parent / 'core100_known_condition_readiness_20261021_v1/readiness100.csv'))}
B1 = B.parent / 'batch1'


def runs_for(clip):
    """all true-parameter replays of a task made with its current (v2) config: list of {mover: poses}"""
    out = []
    for f in [B / 'g0' / f'G0b2_{clip}.json', B / 'g0' / f'G0b2r_{clip}.json']:
        if f.exists(): out += [v['poses'] for v in json.load(open(f)).values() if v.get('poses')]
    if clip.endswith('C03'):
        v2 = json.load(open(B1 / 'cfg/v2_changes.json'))
        for f in ([B1 / 'g0v2' / f'{clip}.json'] if clip in v2 else [B1 / 'g0' / f'{clip}.json']) + [B1 / 'g0rep' / f'{clip}.json']:
            if f.exists(): out += [v['poses'] for v in json.load(open(f)).values() if v.get('poses')]
    return out


def first_over(e, thr=1e-3):
    return int(np.argmax(e > thr)) if (e > thr).any() else None


audit = json.load(open(B / 'reference_explosion_audit.json'))
result = {}
for clip in sorted(rows):
    sc = clip[:3]; primary = (mcf.get(clip) or {}).get('moving')
    r = dict(scene=sc, primary=primary)
    if clip == 'T06_C04':
        r.update(verdict='NOT_INTEGRATED', note='Isaac scene; needs the author\'s Isaac container (issue B15)'); result[clip] = r; continue
    runs = runs_for(clip)
    if sc in ('T06', 'T09', 'T10'):
        rep = None
        if len(runs) >= 2:
            diffs = []
            for n in runs[0]:
                A_, B_ = np.array(runs[0][n])[:, :3], np.array(runs[1][n])[:, :3]
                keep = (A_[:, 2] > -0.3) & (B_[:, 2] > -0.3)   # frames before an object drops below the table (no floor collider, B16)
                if np.linalg.norm(A_ - A_[0], axis=1).max() > 0.01 and keep.any():
                    diffs.append(float(np.linalg.norm(A_[keep] - B_[keep], axis=1).max()))
            rep = max(diffs, default=0.0)
        r.update(verdict='VIDEO_ONLY_VISUAL_MATCH', n_runs=len(runs), repeat_max_mm=None if rep is None else round(1000 * rep, 1),
                 note='no recorded states; replay overlaid on the frozen reference video (objects that fall below the table excluded)')
        result[clip] = r; continue
    meta = recorded(clip)
    if not runs or meta is None:
        r.update(verdict='NO_RUN'); result[clip] = r; continue
    objs = {}
    for n in runs[0]:
        try: R = np.array([next(o['position'] for o in fr['objects'] if o['name'] == n) for fr in meta['frames']])
        except StopIteration: continue
        if np.linalg.norm(R - R[0], axis=1).max() < 0.01: continue
        P = [np.array(x[n])[:, :3] for x in runs if n in x]; m = min(len(R), *(len(p) for p in P))
        e = [np.linalg.norm(p[:m] - R[:m], axis=1) for p in P]
        pair = [np.linalg.norm(P[a][:m] - P[b][:m], axis=1) for a in range(len(P)) for b in range(a + 1, len(P))]
        objs[n] = dict(best_mm=round(1000 * min(float(x.max()) for x in e), 2), worst_mm=round(1000 * max(float(x.max()) for x in e), 2),
                       first_1mm=min([f for f in (first_over(x) for x in e) if f is not None], default=None),
                       repeat_mm=round(1000 * max(float(x.max()) for x in pair), 2) if pair else None,
                       repeat_first_1mm=min([f for f in (first_over(x) for x in pair) if f is not None], default=None) if pair else None)
    r.update(n_runs=len(runs), objects=objs)
    if not objs:
        r.update(verdict='REPRODUCED', note='no object moves > 1 cm'); result[clip] = r; continue
    worst_best = max(o['best_mm'] for o in objs.values())      # best run, worst object
    worst_all = max(o['worst_mm'] for o in objs.values())      # worst run, worst object
    p = objs.get(primary) or objs[max(objs, key=lambda n: objs[n]['best_mm'])]   # primary that does not move -> worst object
    rep = max((o['repeat_mm'] for o in objs.values() if o['repeat_mm'] is not None), default=None)
    if audit.get(clip):
        r['verdict'] = 'REFERENCE_ANOMALY'                     # the reference itself is unphysical (A18)
    elif worst_all <= 2:
        r['verdict'] = 'REPRODUCED'                            # every run, every moving object within 2 mm
    elif worst_best <= 2:
        r['verdict'] = 'REPRODUCED_SOMETIMES'                  # at least one run matches the record; others branch off
    elif p['worst_mm'] <= 6:
        r['verdict'] = 'PRIMARY_REPRODUCED'                    # primary within 6 mm in every run; other objects drift/branch
    elif rep is None:
        r['verdict'] = 'DIVERGES_SINGLE_RUN'                   # one run only: cannot tell chaos from a systematic difference
    elif p['best_mm'] > 3 * max(p['repeat_mm'] or 0, 0.5):
        r['verdict'] = 'SYSTEMATIC_OFFSET'                     # repeats agree with each other but not with the record
    else:
        r['verdict'] = 'NOT_REPEATABLE'                        # repeats differ as much as they differ from the record
    result[clip] = r
json.dump(result, open(B / 'INTEGRATION_STATUS.json', 'w'), indent=1)
import collections
print(collections.Counter(v['verdict'] for v in result.values()))
for clip, v in result.items():
    o = v.get('objects', {}); p = o.get(v['primary']) if o else None
    print(f"{clip} {v['verdict']:22s} runs {v.get('n_runs', '-')} | primary {str(v['primary'])[-18:]:18s} "
          + (f"best {p['best_mm']}mm rep {p['repeat_mm']}" if p else '') + (f" | repeat {v['repeat_max_mm']}mm" if v.get('repeat_max_mm') is not None else '')
          + (' | worst obj ' + max(o, key=lambda n: o[n]['best_mm'])[-14:] + f" {max(x['best_mm'] for x in o.values())}mm" if o else ''))
