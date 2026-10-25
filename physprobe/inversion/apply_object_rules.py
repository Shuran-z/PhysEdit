"""Re-classify existing result files with evaluator.apply_carrier_rule (D22) without re-running the evaluation.
Usage: python apply_object_rules.py IN.jsonl OUT.jsonl  |  python apply_object_rules.py --ref (results3/ref_*.json in place)"""
import glob, json, sys
import evaluator as ev

if sys.argv[1] == '--ref':
    n = 0
    for f in glob.glob(str(ev.B / 'results3' / 'ref_*.json')):
        if f.endswith('_summary.json'): continue
        r = json.load(open(f)); k0 = r.get('kind'); ev.apply_carrier_rule(r); n += r.get('kind') != k0
        json.dump(r, open(f, 'w'), indent=1)
    print('reference results re-classified:', n)
else:
    n = 0
    with open(sys.argv[2], 'w') as out:
        for l in open(sys.argv[1]):
            r = json.loads(l)
            if 'param' in r: k0 = r.get('kind'); ev.apply_carrier_rule(r); n += r.get('kind') != k0
            out.write(json.dumps(r) + '\n')
    print('re-classified:', n)
