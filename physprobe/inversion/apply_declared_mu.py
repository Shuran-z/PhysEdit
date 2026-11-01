"""Prompted friction of re-generated videos (user decision 2026-10-26, issue log E4): mu is scored against the value that the
video's own prompt declares for the measured contact, not against the simulator's value.
Measured contact = the library's friction pair (library_plan.json friction_objects; both objects are set to the library value).
Declared = the material frictions of these objects among the prompt's selected keys in the known conditions of that prompt
release (the table / ramp coefficient keys count for tabletop / ramp objects). Several -> the larger one (Genesis combines a
contact by max). None -> the prompt says nothing about this contact: the result keeps its kind (evaluability) but has no
prompted value, so it is left out of the error, in-band and response statistics. The simulator's value moves to
truth_physical; err_pct, best_err_pct and truth_in_band are recomputed. Only rows of the given prompts (default: revised) change.
Idempotent (starts again from truth_physical). Usage:
python apply_declared_mu.py NAME KNOWN_CONDITIONS.json [--prompts revised]   (rewrites results_gen/NAME.jsonl in place)"""
import argparse, collections, json

from paths import WORK as B

ALIAS = (('tabletop', 'table_material friction_coefficient'), ('ramp', 'ramp_material friction_coefficient'))


def declared_mu(task, pair):
    facts = {k: v for k, _, v, _ in task['prompt_generation_facts']}; sel = set(task['selected_parameter_keys'])
    vals = []
    for o in pair:
        keys = [f'{o}.material friction'] + [k for a, k in ALIAS if a in o]
        vals += [facts[k] for k in keys if k in sel and k in facts][:1]
    return max(vals) if vals else None


def in_band(r, t):
    if not t or not r.get('band'): return None
    lo, hi = r['band']
    if r['kind'] == 'upper_bound': lo = 0.0
    if r['kind'] == 'lower_bound': hi = float('inf')
    return bool(lo <= t <= hi)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('known_conditions'); ap.add_argument('--prompts', default='revised')
    a = ap.parse_args()
    tasks = {t['clip_id']: t for t in json.load(open(a.known_conditions))['tasks']}
    lib_of = {m: L['lib'] for L in json.load(open(B / 'library_index.json'))['libraries'] if L['param'] == 'mu' for m in L['members']}
    pair_of = {}
    for j in json.load(open(B / 'library_plan.json')):
        if j['param'] == 'mu' and j.get('friction_objects'): pair_of.setdefault(j['lib'], j['friction_objects'].split(','))
    f = B / 'results_gen' / f'{a.name}.jsonl'; rows = [json.loads(l) for l in open(f)]; n = collections.Counter(); per_task = {}
    for r in rows:
        if r.get('param') != 'mu' or r.get('prompts') != a.prompts: continue
        phys = r.setdefault('truth_physical', r.get('truth'))
        mu = declared_mu(tasks[r['clip']], pair_of[lib_of[r['clip']]]) if r['clip'] in lib_of else None
        per_task[r['clip']] = (phys, mu)
        r['truth'] = mu; r['prompt_mu_source'] = 'declared' if mu is not None else 'not_declared'
        for k, v in (('est', 'err_pct'), ('best', 'best_err_pct')):
            if r.get(k) is not None and mu: r[v] = 100 * (r[k] - mu) / mu
            else: r.pop(v, None)
        if r.get('band'): r['truth_in_band'] = in_band(r, mu)
        n['declared' if mu is not None else 'not declared'] += 1
    f.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    print(f'{a.name}: {dict(n)} mu rows of the {a.prompts} prompts re-scored')
    for c, (phys, mu) in sorted(per_task.items()): print(f'  {c}: simulator {phys} -> prompt {mu}')
