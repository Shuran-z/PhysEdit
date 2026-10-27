"""Known-truth validation gate (issue log D28). A generated video's (task, parameter) is scored only where the evaluation
explains the TRUE physics of that task in the same video format: the reference known-answer result (results3/ref_*.json)
and the synthetic generated-like set of that format must both be an estimate (point / interval / bound / unidentifiable),
not not_explained / no_observation / error. Elsewhere the instrument itself fails on correct physics (tracking of stacked
or occluded objects, object rules with two objects), so a 'not explained' there says nothing about the model: the
generated result becomes kind 'not_validated' (the original kind is kept in kind_before_gate).
Format -> synthetic set: <= 24 frames -> s10f16 (DynamiCrafter); <= 16 fps -> s15v (16 fps x 81, PhysRVG 15 fps x 49);
otherwise s30f121 (24-25 fps x 121-189).
Usage: python validation_gate.py NAME [ITEMS_SET[,ITEMS_SET...]] [TRUTH_TAG] -> results_gen/<NAME>_gated.jsonl + results_gen/<NAME>_gate.json
(TRUTH_TAG: use the known-truth results of a rule variant, results3_<TAG>/ and results_gen/<set>_<TAG>.jsonl)"""
import collections, glob, json, sys

from paths import WORK as B

PASS = {'point', 'interval', 'upper_bound', 'lower_bound', 'unidentifiable'}
SETS = ('s15v', 's30f121', 's10f16')


def format_set(fps, frames):
    return 's10f16' if frames <= 24 else ('s15v' if fps <= 16 else 's30f121')


def failed(tag=''):
    """(set name) -> {(clip, param)} where the known-truth result is not an estimate; 'reference' = results3."""
    bad = collections.defaultdict(set)
    for f in glob.glob(str(B / ('results3' + tag) / 'ref_*.json')):
        if f.endswith('_summary.json'): continue
        r = json.load(open(f))
        if r.get('kind') not in PASS: bad['reference'].add((r['clip'], r['param']))
    for s in SETS:
        for line in open(B / 'results_gen' / f'{s}{tag}.jsonl'):
            r = json.loads(line)
            if 'param' in r and r.get('kind') not in PASS: bad[s].add((r['clip'], r['param']))
    return bad


if __name__ == '__main__':
    name = sys.argv[1]; items_set = sys.argv[2] if len(sys.argv) > 2 else 'all'; tag = '_' + sys.argv[3] if len(sys.argv) > 3 else ''
    fmt = {x['key']: format_set(x['fps'], x['frames']) for n in items_set.split(',')   # several sets: the later ones win
           for x in json.load(open(B / 'sam_gen' / n / 'items.json'))['items']}
    bad = failed(tag); n = collections.Counter(); out = []
    for line in open(B / 'results_gen' / f'{name}.jsonl'):
        r = json.loads(line)
        if 'param' in r:
            s = fmt[r['key']]; why = [k for k in ('reference', s) if (r['clip'], r['param']) in bad[k]]
            r['format_set'] = s
            if why:
                r.update(kind_before_gate=r.get('kind'), kind='not_validated', not_validated_by=why); n[(s, r['param'], 'gated')] += 1
            n[(s, r['param'], 'all')] += 1
        out.append(r)
    with open(B / 'results_gen' / f'{name}_gated.jsonl', 'w') as f:
        for r in out: f.write(json.dumps(r) + '\n')
    rep = {'failed_known_truth': {k: sorted(f'{c}|{p}' for c, p in v) for k, v in sorted(bad.items())},
           'gated_share': {f'{s}|{p}': f"{n[(s, p, 'gated')]}/{n[(s, p, 'all')]}" for s in SETS for p in ('g', 'mu', 'v') if n[(s, p, 'all')]}}
    json.dump(rep, open(B / 'results_gen' / f'{name}_gate.json', 'w'), indent=1)
    for k, v in rep['failed_known_truth'].items(): print(k, len(v), ' '.join(v))
    print(json.dumps(rep['gated_share']))
