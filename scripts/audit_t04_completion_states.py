"""Extract observable motion predicates; missing contact telemetry stays unknown.

Thresholds are taken from recovered original audit_t04_v4_quality.py.
These are measured published samples, not newly solved boundaries.
"""
import collections, copy, gzip, hashlib, json, math
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')

def fixed_context(data, family):
    """Retain every runtime object field except the declared intervention.

    This is a conservative state-config fingerprint, not proof of renderer identity.
    The recovered renderer consumes random_seed, not the declarative seed field.
    Both are recorded in the output; only the consumed one enters this fingerprint.
    """
    objects=copy.deepcopy([o['spec'] for o in data['dynamic_objects']])
    for o in objects:
        if family=='stack_sliding' and o['name'] in ['t04v3_folder_ramp_pbr','t04v3_stack_book_bottom']:
            o['friction']='<intervention>'
        elif family=='terminal_transfer' and o['name']=='t04v3_chain_mug':
            o['pose']['position'][0]='<intervention>'
        elif family=='support_release' and o['name']=='t04v3_removable_support_bar':
            o['motion']['initial_velocity'][1]='<intervention>'
    exp=data['experiment']
    context=dict(objects=objects,scene_overrides=data['scene_overrides'],runtime_forces=data.get('runtime_forces'),
                 manifest=data.get('manifest'),room_boundary=data.get('room_boundary'),
                 random_seed=exp.get('random_seed'),
                 render_timing={k:v for k,v in data.get('render',{}).items() if k in ['fps','n_frames','num_frames','frames','pre_static_frames','duration_s','physics_steps_per_render_frame','settle_steps']})
    return hashlib.sha256(json.dumps(context,sort_keys=True,allow_nan=False).encode()).hexdigest()

def measure(data):
    frames=data['frames']
    names=['t04v3_stack_book_'+s for s in ['bottom','middle','top']]
    names+=['t04v3_chain_mug']
    series={n:[next(o for o in f['objects'] if o['name']==n) for f in frames] for n in names}
    metrics={}
    for n,ss in series.items():
        p=ss[0]['position'];q=ss[0]['quaternion_xyzw']
        def angle(o):
            qq=o['quaternion_xyzw'];den=math.sqrt(sum(x*x for x in q)*sum(x*x for x in qq))
            return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(q,qq))/den))))
        metrics[n]=dict(dx=max(o['position'][0]-p[0] for o in ss),drop=max(p[2]-o['position'][2] for o in ss),displacement=max(math.dist(p,o['position']) for o in ss),rotation=max(map(angle,ss)))
    books=[metrics[n] for n in names[:3]];mug=metrics[names[-1]]
    contact_fields=sum('contacts' in f for f in frames)
    events=dict(stack_motion=int(max(x['dx'] for x in books)>.12 or max(x['drop'] for x in books)>.025),terminal_response=int(mug['rotation']>=18 or mug['displacement']>=.04))
    # Never turn an absent sensor channel into a negative contact label.
    events['can2_mug_contact']=None if not contact_fields else int(any({c.get('entity_a'),c.get('entity_b')}=={'t04v3_chain_can_2','t04v3_chain_mug'} for f in frames for c in f.get('contacts',[])))
    events['terminal_transfer']=None if events['can2_mug_contact'] is None else int(events['terminal_response'] and events['can2_mug_contact'])
    return dict(events=events,metrics=metrics,contact_frames_present=contact_fields)

def main():
    extractor_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    bindings={r['sample_id']:r for r in json.loads((ROOT/'t04_t05_profile_bindings.json').read_text())}
    output=ROOT/'t04_measured_published_events.json'
    old={r['sample_id']:r for r in json.loads(output.read_text(encoding='utf-8'))} if output.exists() else {}
    rows=[];seen=set()
    for receipt in sorted((ROOT/'completion_states').glob('T04_*.json')):
        for r in json.loads(receipt.read_text(encoding='utf-8')):
            if not r.get('local_path'):continue
            if r['sample_id'] in seen:raise ValueError('duplicate published sample receipt')
            seen.add(r['sample_id'])
            p=Path(r['local_path']);raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('state hash changed')
            cached=old.get(r['sample_id'])
            if cached and cached.get('sha256')==r['sha256'] and cached.get('extractor_sha256')==extractor_hash and 'runtime_random_seed' in cached:
                rows.append(cached);continue
            d=json.loads(gzip.decompress(raw));b=bindings.get(r['sample_id'])
            if not b:continue
            rows.append(dict(**r,**measure(d),declared_seed=d['experiment'].get('seed'),runtime_random_seed=d['experiment'].get('random_seed'),fixed_context_sha256=fixed_context(d,b['family_id']),extractor_sha256=extractor_hash,family_id=b['family_id'],theta=b['theta'],parameter_name=b['parameter_name'],source_group_id=b['source_group_id'],repeat=b['repeat'],status='measured_published_state_not_boundary_certification'))
    (ROOT/'t04_measured_published_events.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    summary=dict(states=len(rows),by_family={str(f):dict(count=len(rr),stack_positive=sum(x['events']['stack_motion'] for x in rr),terminal_positive=sum(x['events']['terminal_response'] for x in rr),unknown_contact=sum(x['events']['can2_mug_contact'] is None for x in rr)) for f in set(x['family_id'] for x in rows) for rr in [[x for x in rows if x['family_id']==f]]})
    (ROOT/'t04_measured_published_events_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))

if __name__=='__main__':main()
