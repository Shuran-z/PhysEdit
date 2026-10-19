"""Keep effective T05 interventions and repair variants separate."""
import collections,json
from pathlib import Path
from physedit.boundary import digest

ROOT=Path('review/scene_family_completion_20261018')

def main():
    source=ROOT/'t05_measured_published_events.json';rows=json.loads(source.read_text())
    targets={'gate_passage':'gate_passage','terminal_transfer':'terminal_contact'}
    groups=collections.defaultdict(list)
    for r in rows:
        if r['family_id'] in targets:
            groups[(r['source_group_id'],r['family_id'],r['repeat'],r['repair_requires_separate_boundary'])].append(r)
    results=[]
    for (context,family,repeat,repair),points in sorted(groups.items()):
        points.sort(key=lambda r:r['theta']);event=targets[family];transitions=[]
        for a,b in zip(points,points[1:]):
            left,right=a['events'][event],b['events'][event]
            if left is None or right is None or left==right:continue
            if a['theta']==b['theta']:
                transitions.append(dict(status='same_effective_parameter_conflicting_labels',sample_ids=[a['sample_id'],b['sample_id']]))
                continue
            transitions.append(dict(bracket=[a['theta'],b['theta']],labels=[left,right],sample_ids=[a['sample_id'],b['sample_id']],state_sha256=[a['sha256'],b['sha256']],fixed_context_matches=bool(a.get('fixed_context_sha256')) and a.get('fixed_context_sha256')==b.get('fixed_context_sha256'),status='observed_transition_not_solved_threshold'))
        results.append(dict(context=context,family=family,repeat=repeat,repair_variant=repair,target_event=event,points=len(points),transitions=transitions,source_sha256=digest(source)))
    (ROOT/'t05_transition_candidates.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(dict(groups=len(results),observed_intervals=sum(len(r['transitions']) for r in results),matched_context_intervals=sum(t.get('fixed_context_matches',False) for r in results for t in r['transitions']))))

if __name__=='__main__':main()
