"""Join released Genesis scans by actual physical context and named contact event.

Preserve topology/revision variants and every local observed transition. These
are scan brackets, not recovered exact numerical roots or universal fall labels.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path


def context(row):
    e=copy.deepcopy(row['experiment']);axis=e['parameter']['parameter_name'];scene=row['scene_id']
    objects={a['name']:copy.deepcopy(a['spec']) for a in row['actors']}
    def mask(name,*path):
        target=objects[name]
        for k in path[:-1]:target=target[k]
        target[path[-1]]='<intervention>'
    aliases=[]
    if scene=='T16':
        if axis not in ['contact_position','support_angle']:raise ValueError('unmapped T16 recipe')
        mask('t16_support_book','pose','position',0)
        for i in range(len(objects['t16_support_book']['motion']['keyframes'])):mask('t16_support_book','motion','keyframes',i,'position',0)
        if axis=='support_angle':
            mask('t16_folder','pose','euler_xyz',1);mask('t16_folder','pose','position',2);aliases=['support_angle_deg']
        else:aliases=['contact_position_normalized']
    elif scene=='T17':
        if axis=='initial_speed':mask('t17_can','motion','initial_velocity',0);aliases=['initial_speed_mps']
        elif axis=='lateral_offset':mask('t17_can','pose','position',1);aliases=['lateral_offset_m']
        else:raise ValueError('unmapped T17 recipe')
    elif scene=='T18':
        if axis=='overlap_length':
            # Multi-book overlap versions change extraction geometry differently.
            # Retain them separately until their exact builder recipe is mapped.
            if 't18_upper_book' not in objects:raise ValueError('multi-book overlap recipe pending')
            mask('t18_upper_book','pose','position',0);aliases=['overlap_length_m','overlap_ratio']
        elif axis=='contact_friction':
            for name in objects:
                if name.startswith('t18_'):
                    if 'friction' in objects[name]:mask(name,'friction')
            aliases=['static_friction','dynamic_friction']
        else:raise ValueError('unmapped T18 recipe')
    elif scene=='T20':
        names={'book_can_gap':['t20_book'],'can_box_gap':['t20_book','t20_can'],
               'box_cup_gap':['t20_book','t20_can','t20_box'],
               'cup_edge_margin':['t20_book','t20_can','t20_box','t20_cup']}
        if axis=='book_drive_speed':mask('t20_book','motion','initial_velocity',0)
        elif axis in names:
            for name in names[axis]:mask(name,'pose','position',0)
        else:raise ValueError('unmapped T20 recipe')
        aliases=[axis]
    else:raise ValueError('unsupported scene')
    for key in aliases+['trajectory_id','parameter','local_margin_value']:e.pop(key,None)
    physics={k:v for k,v in row['scene_overrides'].items() if not k.startswith('raytracing')}
    payload=dict(objects=objects,experiment=e,scene=physics,revision=row['revision'],
                 timing={k:row['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    root=Path(args.records);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    groups=collections.defaultdict(list);counts=collections.Counter();pending=[]
    for path in root.glob('T*.json'):
        row=json.loads(path.read_text())
        if row.get('status')!='published_metadata_extracted' or not row.get('hash_verified'):continue
        counts[row['scene_id']]+=1
        try:key=context(row)
        except (KeyError,ValueError) as exc:
            pending.append(dict(sample_id=row['sample_id'],scene_id=row['scene_id'],reason=str(exc)));continue
        parameter=row['experiment']['parameter'];names={a['name'] for a in row['actors']}
        base=dict(scene_id=row['scene_id'],engine='genesis',sample_id=row['sample_id'],revision=row['revision'],
                  family_id=parameter['parameter_name'],theta=parameter['parameter_value'],parameter_unit=parameter['parameter_unit'],
                  fixed_context_sha256=key,reference_state_sha256=row['metadata_sha256'])
        for contact in row['contacts']:
            if not set(contact['pair'])<=names:continue
            for field in ['occurred','present_at_end']:
                if contact.get(field) is None:continue
                event='contact_'+'__'.join(contact['pair'])+'_'+field
                groups[(row['scene_id'],key,event)].append(dict(base,target_event=event,reference_label=int(contact[field])))
    windows=[];bindings=[]
    for (scene,key,event),items in groups.items():
        items.sort(key=lambda r:r['theta']);values=[r['theta'] for r in items]
        if len(values)!=len(set(values)):
            pending.append(dict(scene_id=scene,context=key,event=event,reason='duplicate parameter values'));continue
        domain=[min(values),max(values)];span=domain[1]-domain[0]
        for left,right in zip(items,items[1:]):
            if left['reference_label']==right['reference_label']:continue
            a,b=left['theta'],right['theta'];identity=dict(context=key,event=event,bracket=[a,b],
                samples=[left['sample_id'],right['sample_id']],states=[left['reference_state_sha256'],right['reference_state_sha256']])
            job=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
            windows.append(dict(scene_id=scene,job_id=job,**identity,labels=[left['reference_label'],right['reference_label']]))
            for row in items:
                t=row['theta'];lo=max(a-t,t-b,0);hi=max(abs(t-a),abs(t-b))
                bindings.append(dict(row,original_boundary_interval=[a,b],distance_lower=lo,distance_upper=hi,
                    normalized_distance_lower=lo/span,normalized_distance_upper=hi/span,
                    normalization_domain=domain,normalization_span=span,refinement_job_id=job,
                    original_reference_kind='published_actual_metadata_contact_scan_interval',
                    scope='local adjacent released parameter samples; exact same-seed refinement separate; no collapse/fall equivalence'))
    (out/'t16_t20_published_contact_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    (out/'t16_t20_contact_search_plan.json').write_text(json.dumps(windows,indent=2))
    (out/'t16_t20_contact_pending.json').write_text(json.dumps(pending,indent=2))
    summary=dict(verified_metadata=dict(counts),intervals=dict(collections.Counter(r['scene_id'] for r in windows)),
        unique_bound_samples={s:len({r['sample_id'] for r in bindings if r['scene_id']==s}) for s in counts},pending_recipe_records=len(pending),
        exact_root_claim=False,formal_nearacc_admissions=0)
    (out/'t16_t20_contact_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
