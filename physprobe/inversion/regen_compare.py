"""Paired comparison of a re-generated delivery with the results it replaces (issue log E4): only the keys and parameters
present in both (same seed / prompt variant / model / task, earlier prompts vs corrected prompts), after the known-truth
gate of the merged set. Per model and parameter: share with a value (point / interval), one-sided bound, unidentifiable,
not explained, no observation, for the earlier and the new videos; and how many results changed kind.
T19/T20 friction is left out (B20). Usage: python regen_compare.py BASE_GATED NEW_GATED [--out FILE.md]
(BASE_GATED: the gated official results, e.g. all_cc_gated; NEW_GATED: the gated merged results, e.g. all_cc_revised_gated;
the new rows are those with prompts != original)"""
import collections, json, sys

from paths import WORK as B

MEAS = ('point', 'interval')
CATS = (('value', MEAS), ('bound', ('upper_bound', 'lower_bound')), ('unidentifiable', ('unidentifiable',)),
        ('not explained', ('not_explained',)), ('no observation', ('no_observation',)))
args = [x for x in sys.argv[1:] if not x.startswith('--')]
out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
if out: args = [x for x in args if x != out]
load = lambda n: [json.loads(l) for l in open(B / 'results_gen' / f'{n}.jsonl')]
skip = lambda r: 'param' not in r or (r['param'] == 'mu' and r['clip'][:3] in ('T19', 'T20'))
base = {(r['key'], r['param']): r for r in load(args[0]) if not skip(r)}
new = {(r['key'], r['param']): r for r in load(args[1]) if not skip(r) and r.get('prompts') not in (None, 'original')}
keys = [k for k in new if k in base and base[k]['kind'] != 'not_validated' and new[k]['kind'] != 'not_validated']
L = [f'# Re-generated videos vs the videos they replace ({args[1]} vs {args[0]})', '',
     f'Paired results (same key and parameter, both past the known-truth gate): {len(keys)}; tasks: '
     + ', '.join(sorted({k[0][-7:] for k in keys})), '',
     '| model | parameter | n | ' + ' | '.join(f'{c}: before → after' for c, _ in CATS) + ' | kind changed |', '|---|---|---|' + '---|' * (len(CATS) + 1)]
by = collections.defaultdict(list)
for k in keys: by[(base[k]['model'], k[1])].append(k); by[('all', k[1])].append(k)
for (m, p), ks in sorted(by.items(), key=lambda t: (t[0][0] == 'all', t[0])):
    cells = []
    for _, kinds in CATS:
        a = sum(base[k]['kind'] in kinds for k in ks) / len(ks); b = sum(new[k]['kind'] in kinds for k in ks) / len(ks)
        cells.append(f'{100 * a:.0f}% → {100 * b:.0f}%')
    ch = sum(base[k]['kind'] != new[k]['kind'] for k in ks)
    L.append(f'| {m} | {p} | {len(ks)} | ' + ' | '.join(cells) + f' | {100 * ch / len(ks):.0f}% |')
txt = '\n'.join(L) + '\n'
if out: open(out, 'w').write(txt)
print(txt)
