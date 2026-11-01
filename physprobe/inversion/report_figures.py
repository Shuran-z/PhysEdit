"""Figures and tables for the acceptance report (static PNG + markdown tables; every figure has a table view).
Palette: the dataviz reference categorical order (blue, orange, aqua, yellow, magenta, green) — adjacent pairs validated
for stacked bars, first three slots validated all-pairs for the scatter; low-contrast slots are backed by the tables.
Usage: python report_figures.py OUT_DIR [--synth s15v,s10f16,s30f121,s15v_pan,s15v_pan_raw] [--generated all_cc_gated]
Fig. 3 shows the generated results that pass the known-truth validation gate (validation_gate.py, D28); the table also
counts the gated ones."""
import argparse, collections, glob, json, math, os, statistics as st
import matplotlib
import matplotlib.ticker
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import evaluator as ev

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--synth', default='s15v,s10f16,s30f121,s15v_pan,s15v_pan_raw'); ap.add_argument('--generated', default='all_cc_gated')
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
SLOT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
TXT, MUTED, GRID = '#0b0b0b', '#52514e', '#e4e3df'
KINDS = [('point', 'point estimate'), ('interval', 'interval'), ('bound', 'one-sided bound'), ('unidentifiable', 'unidentifiable'),
         ('not_explained', 'not explained'), ('no_observation', 'no observation')]
PARAMS = [('g', 'gravity g'), ('mu', 'friction mu'), ('v', 'initial speed v')]
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': TXT, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'axes.spines.top': False, 'axes.spines.right': False, 'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb'})
tables = []
SYNTH_LABEL = {'s15v': 'synthetic 15 fps, x1.026 warp', 's10f16': 'synthetic 10 fps, 16 frames', 's30f121': 'synthetic 30 fps, 121 frames',
               's15v_pan': 'synthetic 15 fps + camera pan, compensated', 's15v_pan_raw': 'synthetic 15 fps + camera pan, not compensated'}


def kind_of(r):
    k = r.get('kind'); return 'bound' if k in ('upper_bound', 'lower_bound') else k


def skip(r): return r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20')     # B20


ref = [json.load(open(f)) for f in glob.glob(str(ev.B / 'results_reference' / 'ref_*.json')) if not f.endswith('_summary.json')]
ref = [r for r in ref if not skip(r)]
syn = {s: [json.loads(l) for l in open(ev.B / 'results_gen' / f'{s}.jsonl')] for s in a.synth.split(',') if os.path.exists(ev.B / 'results_gen' / f'{s}.jsonl')}
syn = {s: [r for r in rs if 'param' in r and not skip(r)] for s, rs in syn.items()}

# 1. known-answer: estimate / truth with band, reference videos
fig, axs = plt.subplots(1, 3, figsize=(12, 5.2))
rows = ['| parameter | cases with a band | point estimates | median abs error | 90th pct | truth inside band |', '|---|---|---|---|---|---|']
for ax, (p, lab) in zip(axs, PARAMS):
    rs = [r for r in ref if r['param'] == p and r.get('band') and r.get('truth')]
    rs.sort(key=lambda r: (kind_of(r) != 'point', (r.get('est') or r.get('center') or r['band'][0]) / r['truth']))
    for i, r in enumerate(rs):
        lo, hi = r['band'][0] / r['truth'], r['band'][1] / r['truth']
        if r['kind'] == 'upper_bound': lo = 0.2
        if r['kind'] == 'lower_bound': hi = 5
        c = SLOT[0] if kind_of(r) == 'point' else SLOT[1]
        ax.plot([lo, hi], [i, i], color=c, lw=2, solid_capstyle='round')
        if r.get('est'): ax.plot([r['est'] / r['truth']], [i], 'o', ms=4.5, color=c, mec='#fcfcfb', mew=1)
    ax.axvline(1.0, color=TXT, lw=1, ls='--'); ax.set_xscale('log'); ax.set_xlim(0.2, 5); ax.set_yticks([])
    ax.set_xticks([0.25, 0.5, 1, 2, 4]); ax.set_xticklabels(['0.25', '0.5', '1', '2', '4']); ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel('estimate / truth (band as line)'); ax.set_title(lab, color=TXT, loc='left'); ax.grid(axis='x', color=GRID, lw=0.6)
    pts = sorted(abs(r['err_pct']) for r in rs if r.get('kind') == 'point' and 'err_pct' in r)
    rows.append(f"| {lab} | {len(rs)} | {len(pts)} | {st.median(pts):.1f}% | {pts[min(len(pts) - 1, int(0.9 * len(pts)))]:.1f}% | "
                f"{sum(bool(r.get('truth_in_band')) for r in rs)}/{len(rs)} |" if pts else f"| {lab} | {len(rs)} | 0 | - | - | - |")
axs[0].plot([], [], color=SLOT[0], lw=2, marker='o', label='point estimate + band'); axs[0].plot([], [], color=SLOT[1], lw=2, label='interval / one-sided bound')
fig.legend(loc='upper right', ncol=2, frameon=False, bbox_to_anchor=(0.995, 0.995))
fig.suptitle('Known-answer test on the reference videos (truth not in the simulation library)', x=0.01, ha='left', color=TXT)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(os.path.join(a.out, 'fig1_known_answer.png'), dpi=160, bbox_inches='tight'); plt.close(fig)
tables.append('### Fig. 1 — known-answer accuracy (reference videos)\n\n' + '\n'.join(rows))

# 2. result kinds: reference and synthetic generated-like sets
sets = [('reference 30 fps', ref)] + [(SYNTH_LABEL.get(s, s), rs) for s, rs in syn.items()]
labels, shares = [], []
rows = ['| set | parameter | n | ' + ' | '.join(k[1] for k in KINDS) + ' | point median abs error | truth inside band |', '|---|---|---|' + '---|' * len(KINDS) + '---|---|']
for name, rs in sets:
    for p, lab in PARAMS:
        x = [r for r in rs if r['param'] == p]
        if not x: continue
        c = collections.Counter(kind_of(r) for r in x); n = len(x)
        labels.append(f'{name} | {p}'); shares.append([c[k] / n for k, _ in KINDS])
        pts = [abs(r['err_pct']) for r in x if r.get('kind') == 'point' and 'err_pct' in r]; nb = [r for r in x if r.get('band')]
        rows.append(f"| {name} | {p} | {n} | " + ' | '.join(f'{100 * c[k] / n:.0f}%' for k, _ in KINDS) +
                    f" | {st.median(pts):.1f}% | {sum(bool(r.get('truth_in_band')) for r in nb)}/{len(nb)} |" if pts else f"| {name} | {p} | {n} | " + ' | '.join(f'{100 * c[k] / n:.0f}%' for k, _ in KINDS) + ' | - | - |')
fig, ax = plt.subplots(figsize=(11, 0.32 * len(labels) + 1.4))
for j, (k, kl) in enumerate(KINDS):
    left = [sum(s[:j]) for s in shares]
    ax.barh(range(len(labels)), [s[j] for s in shares], left=left, color=SLOT[j], edgecolor='#fcfcfb', linewidth=2, label=kl, height=0.72)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels); ax.invert_yaxis(); ax.set_xlim(0, 1); ax.set_xlabel('share of results')
ax.legend(ncol=3, loc='upper left', bbox_to_anchor=(0, -0.08), frameon=False); ax.set_title('Result kinds — reference videos and synthetic generated-like videos (known truth)', loc='left', color=TXT)
fig.tight_layout(); fig.savefig(os.path.join(a.out, 'fig2_kinds_known_truth.png'), dpi=160, bbox_inches='tight'); plt.close(fig)
tables.append('### Fig. 2 — result kinds with known truth\n\n' + '\n'.join(rows))

# 3. generated videos per model
gen = [json.loads(l) for l in open(ev.B / 'results_gen' / f'{a.generated}.jsonl')]
gen = [r for r in gen if 'param' in r and not skip(r)]
models = sorted({r['model'] for r in gen})
for p, lab in PARAMS:
    sh, rows = [], ['| model | videos | not validated (gated) | validated | ' + ' | '.join(k[1] for k in KINDS) + ' | prompt inside band |', '|---|---|---|---|' + '---|' * len(KINDS) + '---|']
    for m in models:
        allx = [r for r in gen if r['model'] == m and r['param'] == p]; x = [r for r in allx if r.get('kind') != 'not_validated']
        c = collections.Counter(kind_of(r) for r in x); n = max(1, len(x))
        sh.append([c[k] / n for k, _ in KINDS]); nb = [r for r in x if r.get('band') and r.get('truth')]
        rows.append(f"| {m} | {len(allx)} | {len(allx) - len(x)} | {len(x)} | " + ' | '.join(f'{100 * c[k] / n:.0f}%' for k, _ in KINDS) + f" | {sum(bool(r.get('truth_in_band')) for r in nb)}/{len(nb)} |")
    fig, ax = plt.subplots(figsize=(11, 0.34 * len(models) + 1.4))
    for j, (k, kl) in enumerate(KINDS):
        ax.barh(range(len(models)), [s[j] for s in sh], left=[sum(s[:j]) for s in sh], color=SLOT[j], edgecolor='#fcfcfb', linewidth=2, label=kl, height=0.72)
    ax.set_yticks(range(len(models))); ax.set_yticklabels(models); ax.invert_yaxis(); ax.set_xlim(0, 1); ax.set_xlabel('share of validated videos')
    ax.legend(ncol=3, loc='upper left', bbox_to_anchor=(0, -0.08), frameon=False); ax.set_title(f'Generated videos — {lab}: result kinds per model (tasks that pass the known-truth validation)', loc='left', color=TXT)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, f'fig3_generated_{p}.png'), dpi=160, bbox_inches='tight'); plt.close(fig)
    tables.append(f'### Fig. 3 ({p}) — generated videos, result kinds per model\n\n' + '\n'.join(rows))

# 4. gravity prompt response (C01/C02/C03 prompt 1.62 / 3.71 / 9.81); point estimate or band centre
fig, ax = plt.subplots(figsize=(12, 4.6)); prompts = [1.62, 3.71, 9.81]
rows = ['| model | prompt 1.62: median (n) | prompt 3.71: median (n) | prompt 9.81: median (n) |', '|---|---|---|---|']
for i, m in enumerate(models):
    cells = []
    for j, g in enumerate(prompts):
        xs = [r['est'] if r.get('kind') == 'point' else math.sqrt(r['band'][0] * r['band'][1]) for r in gen
              if r['model'] == m and r['param'] == 'g' and r['clip'][4:] in ('C01', 'C02', 'C03') and abs(r['truth'] - g) < 0.01 and r.get('kind') in ('point', 'interval')]
        ax.scatter([i + (j - 1) * 0.22] * len(xs), xs, s=18, color=SLOT[j], edgecolors='#fcfcfb', linewidths=0.8, label=f'prompted g = {g}' if i == 0 else None, zorder=3)
        cells.append(f'{st.median(xs):.2f} ({len(xs)})' if xs else '- (0)')
    rows.append(f'| {m} | ' + ' | '.join(cells) + ' |')
for j, g in enumerate(prompts): ax.axhline(g, color=SLOT[j], lw=1, ls='--', zorder=1)
ax.set_yscale('log'); ax.set_xticks(range(len(models))); ax.set_xticklabels(models, rotation=30, ha='right'); ax.set_ylabel('measured g (m/s^2)')
ax.grid(axis='y', color=GRID, lw=0.6); ax.legend(frameon=False, loc='upper left', bbox_to_anchor=(1.0, 1.0))
ax.set_title('Gravity prompt response: measured g of generated videos (point estimates and interval centres), dashed = prompted value', loc='left', color=TXT)
fig.tight_layout(); fig.savefig(os.path.join(a.out, 'fig4_gravity_prompt.png'), dpi=160, bbox_inches='tight'); plt.close(fig)
tables.append('### Fig. 4 — gravity prompt response\n\n' + '\n'.join(rows))
open(os.path.join(a.out, 'tables.md'), 'w').write('\n\n'.join(tables) + '\n')
print('figures and tables ->', a.out)
