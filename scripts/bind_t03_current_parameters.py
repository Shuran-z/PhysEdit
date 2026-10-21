"""Bind all current T03 metadata parameters and original event reports.

Original rendering stars and supplemental adjacent event brackets stay separate.
No video quality, inversion applicability or manual admission gates this export.
"""
import collections
import copy
import hashlib
import json
import math
from pathlib import Path

from scripts.export_original_boundary_distances import distances

ROOT=Path('review/scene_family_completion_20261018')
FIELDS={'A':'book_initial_speed_mps','B':'upper_can_com_edge_distance_m','C':'lower_phone_com_edge_distance_m'}


def context(experiment,family):
    p=copy.deepcopy(experiment['parameter']);g=copy.deepcopy(experiment['geometry_contract']);theta=p[FIELDS[family]]
    p[FIELDS[family]]='<intervention>';p.pop('parameter_value',None);p.pop('parameter_name',None)
    if family=='A':
        p.pop('declared_one_shot_impulse_vector_Ns',None);p.pop('declared_one_shot_impulse_magnitude_Ns',None)
    if family=='B':
        g['upper_can_center_m'][0]+=theta
        g['initial_can_phone_horizontal_gap_m']-=theta
        g['initial_book_can_surface_gap_m']+=theta
    if family=='C':
        g['lower_phone_center_m'][0]+=theta
        g['lower_phone_center_m'][2]-=theta*math.tan(math.radians(p['lower_transfer_ramp_slope_deg']))
        g['initial_can_phone_horizontal_gap_m']+=theta
    def stable(x):
        if isinstance(x,float):return round(x,9)
        if isinstance(x,list):return [stable(v) for v in x]
        if isinstance(x,dict):return {k:stable(v) for k,v in x.items()}
        return x
    payload=dict(parameters=p,geometry=g,background=experiment['background_id'],gravity=experiment['gravity_id'],
        repeat=experiment.get('replicate_id',experiment.get('replicate_index')),consumed_random_seed=experiment.get('random_seed'),revision=experiment.get('revision'))
    return hashlib.sha256(json.dumps(stable(payload),sort_keys=True).encode()).hexdigest()


def original_label(report,family):
    if family=='A':return int(report['first_contact_frame']['book_can'] is not None),'book_contacts_upper_can'
    if family=='B':return int(report['observed_outcome'].startswith(('B1_','C'))),'upper_can_falls'
    return int(report['observed_outcome']=='C2_full_chain_phone_second_fall'),'full_chain_phone_second_fall'


def main():
    state_path=ROOT/'t03_completed_state_contracts_20261020.json'
    states={r['sample_id']:r for r in json.loads(state_path.read_text(encoding='utf-8'))} if state_path.exists() else {}
    headers=json.loads((ROOT/'t03_current_parameter_headers_20261019.json').read_text(encoding='utf-8'))
    reports={r['sample_id']:r for r in json.loads((ROOT/'t03_current_original_event_reports.json').read_text(encoding='utf-8')) if 'data' in r}
    release=json.loads((ROOT/'t03_current_selection_20261019.json').read_text(encoding='utf-8'))[0]
    roster={r['sample_id']:r for r in map(json.loads,next(f for f in release['files'] if f['path']=='catalog/t03_880_selection.jsonl')['text'].splitlines())}
    parameters=[];groups=collections.defaultdict(list);conflicts=[]
    for header in headers:
        if header.get('status')!='published_parameter_header_read':continue
        sid=header['sample_id'];e=header['experiment'];family=e['causal_parameter_group'];theta=e['parameter'][FIELDS[family]]
        report=reports.get(sid)
        if report is None:raise ValueError('missing original event report')
        if report['revision']!=header['revision']:raise ValueError('mixed publication revisions')
        mismatches=[k for k,v in report['data']['required_physics_parameters'].items() if k in e['parameter'] and e['parameter'][k]!=v]
        if mismatches:conflicts.append(dict(sample_id=sid,parameter_fields=mismatches))
        label,event=original_label(report['data'],family)
        row=dict(scene_id='T03',engine='genesis',sample_id=sid,family_id=family,parameter_name=FIELDS[family],theta=theta,parameter_unit='m/s' if family=='A' else 'm',
            revision=header['revision'],repo_id=header['repo_id'],release=roster[sid]['release_prefix'],videos=roster[sid]['video_paths'],
            original_metadata_path=header['published_path'],original_metadata_identity=header['published_identity'],metadata_parameter_value=e['parameter'].get('parameter_value'),
            fixed_context_sha256=context(e,family),original_parameter_region=e.get('parameter_region'),reference_label=label,target_event=event,
            original_event_report_path=report['path'],original_event_report_sha256=report['sha256'],observed_outcome=report['data']['observed_outcome'],
            original_report_parameter_mismatches=mismatches,publication_recovery=header['publication_recovery'],extra_validation_separate=True)
        row['simulation_seed']=e.get('seed',e.get('random_seed'))
        row['seed_scope']='Published seed-varied scan; no claim of a unique same-seed exact threshold.'
        if sid in states:
            state=states[sid]
            if state['revision']!=header['revision'] or state['experiment']['parameter']!=e['parameter']:raise ValueError('actual published state/header mismatch')
            row.update(reference_state_sha256=state['reference_state_sha256'],solver_contract_sha256=state['solver_contract_sha256'],published_state_path=state['published_path'])
            row['metadata_context_sha256']=row['fixed_context_sha256']
            row['fixed_context_sha256']=hashlib.sha256((row['fixed_context_sha256']+state['solver_contract_sha256']).encode()).hexdigest()
        parameters.append(row);groups[(family,row['fixed_context_sha256'])].append(row)
    stars=[];intervals=[]
    for (family,signature),items in groups.items():
        centres={r['theta'] for r in items if r['original_parameter_region']=='theta_star'}
        if len(centres)==1:
            centre=next(iter(centres))
            for r in items:stars.append({**r,'original_rendering_star':centre,'reference_kind':'recorded_rendering_star_not_automatically_a_solved_boundary',**distances(r['theta'],point=centre)})
        domain=[min(r['theta'] for r in items),max(r['theta'] for r in items)];span=domain[1]-domain[0]
        ordered=sorted(items,key=lambda r:r['theta']);values=collections.defaultdict(list)
        for r in ordered:values[r['theta']].append(r)
        consistent={t:rs for t,rs in values.items() if len({r['reference_label'] for r in rs})==1 and not any(r['original_report_parameter_mismatches'] for r in rs)}
        for a,b in zip(sorted(values),sorted(values)[1:]):
            if a not in consistent or b not in consistent:continue
            left,right=consistent[a][0],consistent[b][0]
            if left['reference_label']==right['reference_label']:continue
            for r in items:
                d=distances(r['theta'],bracket=[a,b])
                intervals.append({**r,'original_boundary_interval':[a,b],**d,
                    'normalization_domain':domain,'normalization_span':span,'normalized_distance_lower':d['distance_lower']/span,'normalized_distance_upper':d['distance_upper']/span,
                    'original_reference_kind':'supplemental_interval_from_original_published_event_reports',
                    'endpoint_sample_ids':[left['sample_id'],right['sample_id']],'endpoint_event_report_sha256':[left['original_event_report_sha256'],right['original_event_report_sha256']]})
    out=ROOT/'original_value_distance_ledger';out.mkdir(exist_ok=True)
    for filename,rows in [('t03_published_parameters.jsonl',parameters),('t03_recorded_rendering_star_distances.jsonl',stars),('t03_supplemental_sample_distances.jsonl',intervals)]:
        (out/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    summary=dict(published_parameters=len(parameters),original_event_reports=len(reports),recorded_star_distances=len(stars),conditional_contexts=len(groups),
        recovered_state_bindings=sum('reference_state_sha256' in r for r in parameters),normalized_interval_records=sum(r.get('normalization_span',0)>0 for r in intervals),
        supplemental_sample_interval_records=len(intervals),supplemental_unique_samples=len({r['sample_id'] for r in intervals}),parameter_conflicts=conflicts,
        local_intervals=len({(r['fixed_context_sha256'],tuple(r['original_boundary_interval'])) for r in intervals}))
    (out/'t03_binding_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
