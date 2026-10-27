"""Merge a re-generated delivery into the generated-video results (issue log E4): every result of NEW replaces the result
with the same key and parameter in BASE (same seed / prompt variant / model / task, re-generated with corrected prompts);
the rest of BASE is kept. Each row gets prompt_version (NEW_TAG, or BASE_TAG unless the base row already has one, so increments can be merged onto an
earlier merge), and the merged set mirrors the delivered snapshot (new videos where they exist, the earlier ones elsewhere).
Usage: python merge_generated.py BASE NEW OUT [--base-tag v3] [--new-tag v6]   (names in results_gen/, without .jsonl)"""
import argparse, collections, json

from paths import WORK as B

ap = argparse.ArgumentParser(); ap.add_argument('base'); ap.add_argument('new'); ap.add_argument('out')
ap.add_argument('--base-tag', default='v3'); ap.add_argument('--new-tag', default='v6')
a = ap.parse_args()
load = lambda n: [json.loads(l) for l in open(B / 'results_gen' / f'{n}.jsonl')]
base, new = load(a.base), load(a.new)
newk = {(r['key'], r.get('param')) for r in new}
kept = [dict(r, prompt_version=r.get('prompt_version', a.base_tag)) for r in base if (r['key'], r.get('param')) not in newk]
out = kept + [dict(r, prompt_version=a.new_tag) for r in new]
(B / 'results_gen' / f'{a.out}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in out))
c = collections.Counter(r['prompt_version'] for r in out)
print(f'{len(base)} base + {len(new)} new -> {len(out)} rows ({dict(c)}); replaced {len(base) - len(kept)} base rows')
