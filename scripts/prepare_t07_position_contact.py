"""Bind user-selected E4 table contact on all original T07-B reference videos."""
import collections
import copy
import gzip
import hashlib
import json
import re
from pathlib import Path
from scripts.export_original_boundary_distances import ROOT, distances
from scripts.t07_original_boundary_worker import table_contact


def context(state):
    objects={o['name']:copy.deepcopy(o['spec']) for o in state['dynamic_objects']}
    for axis in [0,2]:objects['t07_smartphone']['pose']['position'][axis]='<B-position>'
    scene={k:v for k,v in state['scene_overrides'].items() if not k.startswith('raytracing')}
    payload=dict(objects=objects,scene=scene,manifest=state['manifest'],seed=state['experiment'].get('random_seed'),
        timing={k:state['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def main():
    selected=[r for r in json.loads((ROOT/'t07_measured_published_events.json').read_text()) if r['family_id']=='B_initial_longitudinal_position_m']
    measured=[];states={};groups=collections.defaultdict(list)
    for source in selected:
        raw=Path(source['local_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('original selected state hash changed')
        state=json.loads(gzip.decompress(raw));event=table_contact(state);sid=source['sample_id'];states[sid]=state
        repeat=re.search(r'__rep(\d+)$',sid).group(1)
        row=dict(scene_id='T07',engine='genesis',sample_id=sid,revision=source['revision'],repo_id=source['repo_id'],
            family_id=source['family_id'],theta=source['theta'],background=source['background'],gravity=source['gravity'],repeat=repeat,
            target_event='phone_table_contact_after_release',reference_label=event['label'],first_contact_frame=event['first_table_contact_frame'],
            contact_frames=event['table_contact_frames'],reference_state_sha256=source['sha256'],fixed_context_sha256=context(state),
            motion_ge_1cm=source['events']['motion_ge_1cm'],reference_origin='published_original_native_contact_telemetry',
            event_definition='any native phone/table contact in frames from pre_static_frames through video end',
            inversion_eligibility='independent',formal_nearacc_eligible=False)
        measured.append(row);groups[(row['background'],row['gravity'],repeat,row['fixed_context_sha256'])].append(row)
    jobs=[];bindings=[];no_flip=[]
    for key,items in groups.items():
        items.sort(key=lambda r:r['theta'])
        if len(items)!=3:raise ValueError('T07-B physical context does not retain its three original branches')
        domain=[items[0]['theta'],items[-1]['theta']];span=domain[1]-domain[0];flips=0
        source_group=hashlib.sha256(json.dumps(key).encode()).hexdigest()
        windows=[]
        for row in items:
            row.update(source_group_id=source_group,reference_sample_id=row['sample_id'],events=dict(motion_ge_1cm=row['motion_ge_1cm'],phone_table_contact_after_release=row['reference_label']))
        for left,right in zip(items,items[1:]):
            if left['reference_label']==right['reference_label']:continue
            flips+=1;interval=[left['theta'],right['theta']];state=states[left['sample_id']]
            windows.append(dict(bracket=interval,labels=[left['reference_label'],right['reference_label']],source_state_sha256=[left['reference_state_sha256'],right['reference_state_sha256']]))
            job=dict(sample_id=left['sample_id'],family='B_initial_longitudinal_position_m',target_event=left['target_event'],
                endpoints=interval,endpoint_labels=[left['reference_label'],right['reference_label']],
                objects=[o['spec'] for o in state['dynamic_objects']],scene_overrides=state['scene_overrides'],state_sha256=left['reference_state_sha256'],
                published_endpoint_states=[dict(sample_id=r['sample_id'],theta=r['theta'],label=r['reference_label'],state_sha256=r['reference_state_sha256']) for r in [left,right]],
                normalization_domain=domain,group_sample_ids=[r['sample_id'] for r in items])
            jobs.append(job)
            for row in items:
                d=distances(row['theta'],bracket=interval)
                bindings.append(dict(row,original_boundary_interval=interval,**d,normalization_domain=domain,normalization_span=span,
                    normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                    source_interval_id=left['sample_id'],original_reference_kind='published_E4_native_table_contact_scan_interval'))
        for row in items:
            row['boundary']=dict(status='observed',intervals=windows,normalization_span=span,source=str((ROOT/'t07_B_E4_reference_answers_20261022.json').resolve())) if flips else dict(status='unavailable',reason='no observed E4 flip in original triplet',domain=domain)
        if not flips:no_flip.append(dict(sample_ids=[r['sample_id'] for r in items],labels=[r['reference_label'] for r in items],domain=domain,status='no_observed_flip_in_published_triplet'))
    (ROOT/'t07_B_E4_reference_answers_20261022.json').write_text(json.dumps(measured,indent=2))
    (ROOT/'t07_B_E4_search_plan_20261022.json').write_text(json.dumps(jobs))
    (ROOT/'original_value_distance_ledger/t07_B_E4_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    summary=dict(reference_videos=len(measured),event_labels=dict(collections.Counter(r['reference_label'] for r in measured)),
        contexts=len(groups),original_intervals=len(jobs),bound_distinct_samples=len({r['sample_id'] for r in bindings}),
        contexts_without_observed_flip=len(no_flip),no_flip_contexts=no_flip,formal_admissions=0,target_event='phone_table_contact_after_release')
    (ROOT/'t07_B_E4_preparation_summary_20261022.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='no_flip_contexts'}))


if __name__=='__main__':main()
