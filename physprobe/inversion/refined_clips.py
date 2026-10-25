"""Reference clips whose libraries have every chunk of the given refinement plans collected (or are not in the plans), so
a refinement A/B can run on them before the whole round has finished. Prints the clip names on one line.
Usage: python refined_clips.py PLAN.json [PLAN.json ...] [--dir libs3_refine]"""
import collections, json, sys

import evaluator as ev

args = sys.argv[1:]; d = 'libs3_refine'
if '--dir' in args: i = args.index('--dir'); d = args[i + 1]; del args[i:i + 2]
done = collections.defaultdict(list)
for p in args:
    for j in json.load(open(p)): done[j['lib']].append((ev.B / d / f"{j['tag']}.json").exists())
ok = collections.defaultdict(list)
for L in ev.LIBS:
    for m in L['members']: ok[m].append(all(done.get(L['lib'], [True])))
print(' '.join(c for c, v in sorted(ok.items()) if all(v)))
