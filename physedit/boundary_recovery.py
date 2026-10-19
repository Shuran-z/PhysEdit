"""Recover observed transition intervals, never invent an exact physical threshold."""
from collections import defaultdict
import math


def recover(points):
    """Each point carries a verified fixed-context ID, numeric theta, binary label.

    Unknown/bad observations block adjacency; conflicting repeats remain unresolved.
    Intervals describe sampled outcome transitions, not certified monotonic physics.
    """
    values=defaultdict(list)
    for p in points:
        if type(p['theta']) not in (int,float) or not math.isfinite(p['theta']):
            raise ValueError('finite theta required')
        if p.get('label') is not None and (type(p['label']) is not int or p['label'] not in (0,1)):
            raise ValueError('binary or unknown label required')
        values[p['theta']].append(p)
    ordered=[]
    for theta,rows in sorted(values.items()):
        labels={r.get('label') for r in rows}
        valid=all(r.get('valid') is True for r in rows)
        label=next(iter(labels)) if valid and len(labels)==1 and None not in labels else None
        ordered.append(dict(theta=theta,label=label,sample_ids=[r['sample_id'] for r in rows]))
    intervals=[]
    for a,b in zip(ordered,ordered[1:]):
        if a['label'] is not None and b['label'] is not None and a['label']!=b['label']:
            intervals.append(dict(bracket=[a['theta'],b['theta']],labels=[a['label'],b['label']],
                endpoint_ids=[a['sample_ids'],b['sample_ids']]))
    return dict(evidence_kind='observed_sample_transitions',points=ordered,intervals=intervals,
        multiple_transitions=len(intervals)>1,exact_threshold=None,
        status='recovered_intervals' if intervals else 'insufficient_transition_evidence')


def observed_distances(theta,record):
    return [dict(bracket=i['bracket'],absolute_distance_interval=[max(i['bracket'][0]-theta,theta-i['bracket'][1],0),max(abs(theta-i['bracket'][0]),abs(theta-i['bracket'][1]))]) for i in record['intervals']]
