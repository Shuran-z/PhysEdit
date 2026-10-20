"""Measure original T13 audit predicates on the current, hash-bound archive states.

1cm motion and 5cm vertical drop retain their original audit meanings. They are
not renamed solver contact, support loss or floor impact. Local adjacent outcome
changes are recorded for subsequent original-backend replay, not auto-admitted.
"""
import collections
import copy
import hashlib
import json
import math
from pathlib import Path

from scripts.bind_current_release_parameter_families import bind_t13

ROOT=Path('review/scene_family_completion_20261018')


def context(config,family,theta,runtime_objects=None):
    objects=copy.deepcopy(runtime_objects if runtime_objects is not None else config['dynamic_objects'])
    for obj in objects:
        if family=='drink_edge_distance' and obj['name']=='t13_drink_box':obj['pose']['position'][0]+=theta
        if family=='driver_pivot_gap' and obj['name']=='t13_driver_book':
            obj['pose']['position'][0]+=theta;obj['motion']['pivot_world'][0]+=theta
        if family=='book_cluster_shift_toward_drink' and obj['name'] in ['t13_falling_book','t13_driver_book']:
            obj['pose']['position'][0]-=theta
            if obj['name']=='t13_driver_book':obj['motion']['pivot_world'][0]-=theta
    def stable(value):
        if isinstance(value,float):return round(value,10)
        if isinstance(value,list):return [stable(v) for v in value]
        if isinstance(value,dict):return {k:stable(v) for k,v in value.items()}
        return value
    scene={k:v for k,v in config['scene_overrides'].items() if not k.startswith('raytracing') and k!='use_raytracing'}
    c=dict(objects=objects,scene_overrides=scene,manifest=config.get('manifest'),background_anchor=config.get('background_anchor'),random_seed=config['experiment'].get('random_seed'),
        timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(stable(c),sort_keys=True).encode()).hexdigest()


def measure(tracks):
    result={};metrics={}
    for name,track in tracks.items():
        if len(track)!=168:raise ValueError('incomplete published T13 track')
        positions=[row['position'] for row in track]
        if any(not math.isfinite(x) for p in positions for x in p):raise ValueError('nonfinite T13 state')
        baseline=positions[18]
        peak=max(math.dist(baseline,p) for p in positions[18:]);drop=baseline[2]-min(p[2] for p in positions[18:])
        metrics[name]=dict(max_displacement_m=peak,max_drop_m=drop)
        result[name+'_motion_ge_1cm']=int(peak>=.01)
        if name=='t13_drink_box':result['drink_drop_ge_5cm']=int(drop>=.05)
    return dict(events=result,metrics=metrics,book_drink_contact=None,support_loss=None,note='published annotation has no solver contact list; use recovered original audit kinematics only')


def main():
    configs={};states={}
    source=ROOT/'t13_latest_archive_records_20261019.jsonl'
    for line in source.open(encoding='utf-8'):
        r=json.loads(line);sid=r['path'].split('/')[1].removesuffix('_rgb3d')
        (configs if 'config' in r else states)[sid]=r
    if configs.keys()!=states.keys():raise ValueError('T13 config/state coverage mismatch')
    groups=collections.defaultdict(list);rows=[]
    rule=ROOT/'t13_current_sources/audit_t13_release_20260919.py'
    for sid,record in configs.items():
        c=record['config'];state=states[sid];b=bind_t13(c);m=c['sample_metadata']
        actual={o['spec']['name']:o['spec'] for o in state['objects']}
        if any(actual.get(o['name'])!=o for o in c['dynamic_objects']):raise ValueError('T13 config/state object mismatch')
        row=dict(sample_id=sid,background=m['background_id'],gravity=m['gravity_id'],family=b['family'],theta=b['theta'],
            fixed_context_sha256=context(c,b['family'],b['theta'],list(actual.values())),config_sha256=record['sha256'],state_sha256=state['sha256'],
            archive_sha256=state['archive_sha256'],original_audit_sha256=hashlib.sha256(rule.read_bytes()).hexdigest(),**measure(state['tracks']))
        rows.append(row);groups[(row['background'],row['gravity'],row['family'],row['fixed_context_sha256'])].append(row)
    intervals=[]
    for key,items in groups.items():
        items.sort(key=lambda r:r['theta'])
        for event in ['t13_drink_box_motion_ge_1cm','drink_drop_ge_5cm']:
            changes=[]
            for left,right in zip(items,items[1:]):
                if left['events'][event]!=right['events'][event]:changes.append(dict(bracket=[left['theta'],right['theta']],labels=[left['events'][event],right['events'][event]],sample_ids=[left['sample_id'],right['sample_id']],state_sha256=[left['state_sha256'],right['state_sha256']]))
            intervals.append(dict(background=key[0],gravity=key[1],family=key[2],fixed_context_sha256=key[3],target_event=event,points=len(items),transitions=changes,status='published_adjacent_observations_replay_pending'))
    (ROOT/'t13_current_measured_events_20261019.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (ROOT/'t13_current_transition_candidates_20261019.json').write_text(json.dumps(intervals,indent=2),encoding='utf-8')
    summary=dict(states=len(rows),fixed_context_groups=len(groups),by_event={e:dict(positive=sum(r['events'][e] for r in rows),transition_intervals=sum(len(x['transitions']) for x in intervals if x['target_event']==e)) for e in ['t13_drink_box_motion_ge_1cm','drink_drop_ge_5cm']},formal_new_near=0)
    (ROOT/'t13_current_event_summary_20261019.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
