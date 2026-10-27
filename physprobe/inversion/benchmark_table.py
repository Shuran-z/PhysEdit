"""Per-model benchmark table (user request 2026-10-26): the common reference-comparison metrics of common_metrics.py and
the camera stability of cam_comp.py (both reused from the PhysEdit V metrics in the form common in papers), next to the
benchmark's own physical-parameter metrics of response_metrics.py (explainability, inversion error, parameter response).
Means over videos; the synthetic generated-like sets (correct physics in the same formats) give the ceiling of the common
metrics, the frozen condition frame (common_metrics.py --frozen) what a video scores by not moving at all, the known-truth
videos the floor / ceiling of the parameter metrics.
Usage: python benchmark_table.py COMMON_NAME RESPONSE_JSON CAMCOMP_STATS [--synthetic s15v,s30f121,s10f16] [--out NAME]
  (COMMON_NAME: results_gen/common_<COMMON_NAME>.jsonl, or NAME1+NAME2+... where later sets replace the same video keys,
  e.g. all_cc+v6all+v6de+v6f for the v6 prompt-corrected deliveries; CAMCOMP_STATS likewise comma-separated, later files
  replace the same keys; RESPONSE_JSON: results_gen/response_metrics*.json)
  -> results_gen/benchmark_<NAME>.md / .json"""
import argparse, collections, json, math
import numpy as np

from paths import WORK as B

COMMON = (('ade', 'ADE (median) ↓', '{:.4f}'), ('fde', 'FDE (median) ↓', '{:.4f}'), ('ade_rel', 'ADE / no-motion ADE (median) ↓', '{:.2f}'),
          ('spatial_iou', 'Spatial IoU ↑', '{:.3f}'),
          ('spatiotemporal_iou', 'Spatiotemporal IoU ↑', '{:.3f}'), ('weighted_spatial_iou', 'Weighted spatial IoU ↑', '{:.3f}'),
          ('mse', 'MSE ↓', '{:.4f}'), ('motion_area_gen', 'moving pixels', '{:.2%}'), ('video_psnr', 'video PSNR ↑', '{:.2f}'),
          ('video_ssim', 'video SSIM ↑', '{:.3f}'))
NAMES = {'cogvideox_i2v': 'CogVideoX', 'cosmos': 'Cosmos', 'cosmos3_nano': 'Cosmos3-nano', 'dynamicrafter_i2v': 'DynamiCrafter',
         'hunyuan15_i2v': 'Hunyuan', 'ltx_i2v': 'LTX', 'minimax_h3': 'MiniMax', 'physalign_wan22_i2v_a14b': 'PhysAlign',
         'physrvg_ti2v5b': 'PhysRVG', 'videogpa_ti2v5b': 'VideoGPA', 'wan22_i2v_a14b': 'Wan2.2-I2V-A14B', 'wan_ti2v5b': 'Wan-TI2V-5B'}
DIAG = math.hypot(854, 480)


MEDIAN = ('ade', 'fde', 'ade_rel')   # trajectory errors have heavy tails (objects thrown out of the scene, lost tracks): medians


def means(rows):
    out = {}
    for k, _, _ in COMMON:
        v = [r[k] for r in rows if r.get(k) is not None and np.isfinite(r[k])]
        out[k] = (float(np.median(v) if k in MEDIAN else np.mean(v)), len(v)) if v else (None, 0)
    return out


def fmt(v, f): return '—' if v is None else f.format(v)


ap = argparse.ArgumentParser(); ap.add_argument('common'); ap.add_argument('response'); ap.add_argument('camstats')
ap.add_argument('--synthetic', default='s15v,s30f121,s10f16'); ap.add_argument('--out', default='official')
a = ap.parse_args()
def with_rel(rs):   # ADE relative to a video in which nothing moves (scale-free across windows); tiny reference motion -> no value
    for r in rs:
        if r.get('ade') is not None and (r.get('ade_static') or 0) > 0.002: r['ade_rel'] = r['ade'] / r['ade_static']
    return rs


def by_key(lines):   # later sets replace the same video keys (re-generated deliveries)
    d = {}
    for l in lines:
        r = json.loads(l); d[r['key']] = r
    return list(d.values())


rows = with_rel(by_key(l for n in a.common.split('+') for l in open(B / 'results_gen' / f'common_{n}.jsonl')))
by = collections.defaultdict(list)
for r in rows: by[r['model']].append(r)
cam = collections.defaultdict(list)
for s in by_key(l for f in a.camstats.split(',') for l in open(f)):
    m = next((mm for mm in NAMES if s['key'].split('_', 1)[1].startswith(mm + '_')), None)
    if m: cam[m].append(s)
resp = json.load(open(a.response)); models = sorted(by)
out = dict(common={}, camera={}, parameters={})
L = ['# Benchmark table: common metrics and the benchmark\'s own physical-parameter metrics', '',
     '## 1. Common metrics (generated video vs the reference continuation of its task; means over videos, medians where marked)', '',
     '| model | videos | ' + ' | '.join(h for _, h, _ in COMMON) + ' | camera drift (median) ↓ | camera drift > 2 % |', '|---|---|' + '---|' * (len(COMMON) + 2)]
for m in models:
    mm = means(by[m]); out['common'][m] = mm
    dr = [s['max_shift_px'] / DIAG for s in cam.get(m, []) if s.get('max_shift_px') is not None]
    out['camera'][m] = dict(drift_median=float(np.median(dr)) if dr else None, drift_over_2pct=float(np.mean(np.array(dr) > 0.02)) if dr else None, n=len(dr))
    L.append(f'| {NAMES.get(m, m)} | {len(by[m])} | ' + ' | '.join(fmt(mm[k][0], f) for k, _, f in COMMON)
             + f" | {fmt(out['camera'][m]['drift_median'], '{:.4f}')} | {fmt(out['camera'][m]['drift_over_2pct'] and 100 * out['camera'][m]['drift_over_2pct'], '{:.0f}%')} |")
for s in a.synthetic.split(','):
    f = B / 'results_gen' / f'common_{s}.jsonl'
    if not f.exists(): continue
    sr = with_rel([json.loads(l) for l in open(f)]); mm = means(sr); out['common'][f'synthetic_{s}'] = mm
    L.append(f'| ceiling: synthetic {s} | {len(sr)} | ' + ' | '.join(fmt(mm[k][0], f) for k, _, f in COMMON) + ' | — | — |')
f = B / 'results_gen' / 'common_frozen.jsonl'
if f.exists():
    fr = with_rel([json.loads(l) for l in open(f)]); mm = means(fr); out['common']['frozen'] = mm
    L.append(f'| baseline: condition frame held still | {len(fr)} clips | ' + ' | '.join(fmt(mm[k][0], f) for k, _, f in COMMON) + ' | — | — |')
static = [r['ade_static'] for r in rows if r.get('ade_static') is not None]
ref_move = [r['motion_area_ref'] for r in rows if r.get('motion_area_ref') is not None]
L += ['', f'Reference scale: a video in which nothing moves would have ADE {np.mean(static):.4f} (mean displacement of the reference objects, '
      f'normalised by the image diagonal); in the reference continuations {np.mean(ref_move):.2%} of the pixels move per 0.1 s step (moving pixels '
      'of the generated videos for comparison). The held-still condition frame shows what not moving at all scores: its trajectory error equals the no-motion ADE (ratio 1), it has no motion to overlap, and its PSNR / SSIM are the highest because the reference continuations change little. Camera drift: largest background shift of a video relative to its first frame / image diagonal (cam_comp).', '',
      '## 2. The benchmark\'s own metrics (physical parameters; validated results)', '',
      '| model | explainable ↑ | with a value | g error ↓ | μ error ↓ | v error ↓ | g response τ ↑ | v response τ ↑ |', '|---|---|---|---|---|---|---|---|']
ev_ = resp['evaluability']; gen = resp['generated']; bands = resp['bands']
def err(d): return '—' if not d or not d.get('n') else f"{d['err_median']:.1f}% ({d['n']})"
def tau(d): return '—' if not d or 'tau_band' not in d else f"{d['tau_band']:+.2f} [{d['tau_band_ci'][0]:+.2f}, {d['tau_band_ci'][1]:+.2f}]"
for m in models + ['all']:
    e = ev_.get(m)
    if not e: continue
    expl = 1 - e['not_explained'] - e['no_observation']
    out['parameters'][m] = dict(explainable=expl, value=e['value'], **{f'err_{p}': gen.get(f'{m}|{p}', {}).get('err_median') for p in ('g', 'mu', 'v')},
                                tau_g=bands.get(f'{m}|g', {}).get('tau_band'), tau_v=bands.get(f'{m}|v', {}).get('tau_band'))
    L.append(f"| {NAMES.get(m, m)} | {100 * expl:.1f}% | {100 * e['value']:.1f}% | {err(gen.get(f'{m}|g'))} | {err(gen.get(f'{m}|mu'))} | {err(gen.get(f'{m}|v'))} | "
             f"{tau(bands.get(f'{m}|g'))} | {tau(bands.get(f'{m}|v'))} |")
for s in ('reference', 's15v', 's30f121', 's10f16'):
    kn = resp['known']
    L.append(f"| known truth: {s} | — | — | {err(kn.get(f'{s}|g'))} | {err(kn.get(f'{s}|mu'))} | {err(kn.get(f'{s}|v'))} | "
             f"{tau(bands.get(f'{s}|g'))} | {tau(bands.get(f'{s}|v'))} |")
L += ['', 'Explainable = share of results whose motion some value of the parameter explains (not "not explained", not "no observation"); '
      'to be checked against human scores. Errors: median |best / prompt − 1| of the results with a value (n). Response: within-task Kendall τ '
      'of the bands (one-sided bounds included), 95 % CI over (model, task) groups; per-model values come from 1–7 groups.']
(B / 'results_gen' / f'benchmark_{a.out}.md').write_text('\n'.join(L) + '\n')
json.dump(out, open(B / 'results_gen' / f'benchmark_{a.out}.json', 'w'), indent=1, default=float)
print('\n'.join(L))
