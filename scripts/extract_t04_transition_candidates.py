"""Extract measured adjacent transitions; never certify them as searched thresholds."""
import collections,json
from pathlib import Path
from physedit.boundary import digest

ROOT=Path('review/scene_family_completion_20261018')

def main():
    path=ROOT/'t04_measured_published_events.json'
    rows=json.loads(path.read_text(encoding='utf-8'))
    groups=collections.defaultdict(list)
    for r in rows:
        if r['family_id'] in ['stack_sliding','terminal_transfer']:
            groups[(r['source_group_id'],r['family_id'],r['repeat'])].append(r)
    result=[]
    for (context,family,repeat),items in sorted(groups.items()):
        event='stack_motion' if family=='stack_sliding' else 'terminal_transfer'
        items.sort(key=lambda r:r['theta'])
        intervals=[]
        for left,right in zip(items,items[1:]):
            a,b=left['events'][event],right['events'][event]
            if a is not None and b is not None and a!=b:
                matched=bool(left.get('fixed_context_sha256')) and left.get('fixed_context_sha256')==right.get('fixed_context_sha256')
                intervals.append(dict(bracket=[left['theta'],right['theta']],labels=[a,b],sample_ids=[left['sample_id'],right['sample_id']],state_sha256=[left['sha256'],right['sha256']],fixed_context_matches=matched,fixed_context_sha256=[left.get('fixed_context_sha256'),right.get('fixed_context_sha256')]))
        result.append(dict(context=context,family=family,repeat=repeat,target_event=event,observed_points=len(items),transitions=intervals,status='observed_transition_requires_context_and_backend_verification',source_sha256=digest(path)))
    (ROOT/'t04_transition_candidates.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(groups=len(result),groups_with_transition=sum(bool(r['transitions']) for r in result),intervals=sum(len(r['transitions']) for r in result))))

if __name__=='__main__':main()
