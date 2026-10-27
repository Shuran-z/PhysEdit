"""Combine tracked job sets of one delivery that arrived in parts (e.g. the prompt-corrected re-generation and its
increments, issue log E4) into one set
for evaluation: sam_gen/<OUT>/items.json (items of all sets; a key present in several sets keeps the last one) and
sam_gen/<OUT>/tracks_lean.jsonl (all tracks). Usage: python combine_jobsets.py OUT NAME1 NAME2 [...]"""
import json, sys

from paths import WORK as B

out, names = sys.argv[1], sys.argv[2:]
D = B / 'sam_gen' / out; D.mkdir(parents=True, exist_ok=True)
items, med = {}, {}
for n in names:
    d = json.load(open(B / 'sam_gen' / n / 'items.json'))
    for x in d['items']: items[x['key']] = x
    for m, v in d.get('model_median_map', {}).items(): med.setdefault(m, v)
json.dump(dict(items=list(items.values()), model_median_map=med, combined_from=names), open(D / 'items.json', 'w'), indent=1)
lines = [l for n in names for l in open(B / 'sam_gen' / n / 'tracks_lean.jsonl')]
(D / 'tracks_lean.jsonl').write_text(''.join(lines))
print(f'{out}: {len(items)} items, {len(lines)} track lines from {", ".join(names)}')
