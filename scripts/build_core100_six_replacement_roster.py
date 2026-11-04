"""Prepare a separate 20x5 roster and its source-bound critical protocol.

The old roster and live annotation pointer are preserved. A prepared version
does not transfer old model outputs or imply completed model evaluation.
"""
import copy
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import shutil

from physedit.core100_bindings import interval_distance
from physedit.core100_critical import load as load_protocol, primary
from physedit.core100_rebalanced import load as load_roster
from physedit.compact_prompt import counts, number
from physedit.prompt_contract import validate_text
from scripts.build_critical_supplement import measurement, fixed_context, declared_schedule_and_prompts
from scripts.t18_table_contact_boundary_worker import table_event

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_six_replacements_20261103'
OUT=ROOT/'benchmarks/core100_critical_pairs_v3_20261103'
PROTOCOL=ROOT/'benchmarks/core100_critical_protocol_v5_20261103'
VERSION='core100-critical-pairs-v3-20261103'
TARGETS=['T04_C02','T06_C02','T06_C03','T10_C05','T18_C01','T18_C02']
TEMPLATES={'T04_C02':'T04_C01','T06_C02':'T06_C05','T06_C03':'T06_C05',
           'T10_C05':'T10_C01','T18_C01':'T18_C03','T18_C02':'T18_C03'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')


def state(cid):return json.loads(gzip.decompress((WORK/'sources'/cid/'source_state.json.gz').read_bytes()))


def source_truth(s,cid):
    if cid.startswith(('T04','T10')):
        theta,events,end,extra=measurement(s,cid[:3]);return theta,events,end,extra
    if cid.startswith('T06'):
        theta=s['experiment']['parameter']['parameter_value'];pairs=s['experiment']['required_contact_pairs']
        hits=[min((f['frame_index']for f in s['frames'][5:210]for c in f.get('contacts',[])
            if{c['entity_a'],c['entity_b']}==set(pair)),default=None)for pair in pairs]
        assert len(pairs)==9
        return theta,{'complete_required_contact_chain':int(all(x is not None for x in hits))},209,dict(first_contact_frames=hits,required_contact_pairs=pairs)
    theta=s['experiment']['parameter']['parameter_value'];f=copy.deepcopy(s['frames'][154])
    f['contacts']=f['original_exterior_contacts'];extra=table_event(s,f)
    return theta,{'upper_nonpulled_book_on_table_at_end':extra['label']},154,extra


def new_prompts(s,cid,theta,row,end,proof):
    if cid.startswith(('T04','T10')):
        schedule,prompts=declared_schedule_and_prompts(s,row,cid[:3],theta,end,proof)
        return schedule,prompts
    if cid.startswith('T06'):
        pre=s['render']['pre_static_frames'];period=s['scene_overrides']['dt']*s['render']['physics_steps_per_render_frame']
        assert pre==12 and abs(period-.02)<1e-12
        commands=s['runtime_forces'];assert len(commands)==12
        assert [r['frame_start']for r in commands]==list(range(8,20))
        assert all(r['target']=='t06_book_00'and r['frame_end']==r['frame_start']for r in commands)
        body=(' Hold for 7/30 s. Gravity 9.81 m/s^2. Then apply the prescribed off-screen force pulse to the first book, '
            'active frames 8-19 at 50 Hz; nominal impact command '+number(theta)+' N. Book masses 0.38 kg; gaps 0.03 m; book friction 0.58.')
        schedule=dict(initial_hold_duration_s=7/30,remaining_static_frames=7,static_clock_hz=30,
            active_frame_period_s=period,active_state_frames=end-11,
            physical_observation_duration_s=7/30+(end-11)*period,full_force_waveform=commands,
            force_frame_semantics='zero-based active physics-frame index after static hold')
    else:
        # New friction values come from these source configs; no parameter or
        # control timing is borrowed from an unrelated published trajectory.
        assert s['experiment']['supported_book_names']==['t18_book_02','t18_book_03','t18_book_04','t18_book_05']
        body=(' Hold for 19/30 s. Gravity 9.81 m/s^2. An off-screen actuator extracts Book 01, starting 38/30 s from now; '
            'travel 0.58 m; release at 92/30 s. All book friction '+number(theta)+'. Overlap 0.15 m; background material friction 1.')
        schedule=dict(initial_hold_duration_s=19/30,remaining_static_frames=19,static_clock_hz=30,
            active_frame_period_s=1/30,active_state_frames=end-23,physical_observation_duration_s=5.,
            extractor_start_from_condition_s=38/30,extractor_release_from_condition_s=92/30,
            timeline_source='native source control at global 1.4 s and 3.2 s, subtract condition frame 4/30 s',
            actual_controller_preserved_in_source_config=True)
    prompts=[lead+body for lead in ['Fixed camera.','Keep the camera fixed.','Preserve the scene and camera.']]
    for text in prompts:validate_text(text)
    return schedule,prompts


def new_unit(template,cid,theta,label,reference_hash,brackets):
    u=copy.deepcopy(primary(template));u.update(clip_id=cid,theta=theta,label=label,intervals=brackets)
    ds=[interval_distance(theta,b,u['normalization_span'])for b in brackets]
    u['normalized_absolute_interval']=[min(d['normalized_absolute_interval'][i]for d in ds)for i in [0,1]]
    lo,hi=u['normalized_absolute_interval'];u['bin']='near'if hi<=.05 else'mid'if lo>.05 and hi<=.2 else'far'if lo>.2 else None
    u['reference_id']=hashlib.sha256(json.dumps(dict(cid=cid,video=reference_hash,axis=u['axis'],event=u['event'],theta=theta,brackets=brackets),sort_keys=True).encode()).hexdigest()
    u.update(rgb_distance_admitted=True,rgb_blockers=[],numerical_evidence_status='bound_local_intervals',supplemental_axis=False)
    return u


def main():
    if(OUT/'MANIFEST.json').exists():raise ValueError('sealed_release_exists_create_new_version')
    parent,manifest,tasks,_=load_roster();protocol,protocol_path=load_protocol()
    assert manifest['version']=='core100-critical-pairs-v2-20261101'
    four=read(WORK/'FOUR_SOURCE_RECOVERY.json');two=read(WORK/'T18_SOURCE_RECOVERY.json');visual=read(WORK/'VISUAL_REVIEW.json')
    visual={r['clip_id']:r for r in visual['cases']};assert set(visual)==set(TARGETS)
    assert all(r['status']=='observable_for_registered_target'for r in visual.values())
    published={r['replacement_clip_id']:r for r in read(WORK/'FOUR_CATALOG_ROWS.json')}
    proofs={r['clip_id']:r for r in four['sources']+two['sources']}
    for cid,p in proofs.items():
        for n,h in p['files'].items():assert sha(WORK/'sources'/cid/n)==h
    protected=read(ROOT/'review/core100_v3_remaining8_20261103/PROTECTED_CANDIDATES.json')
    assert all(r['split']!='train_final'for r in published.values())
    # Check the entire source-group training membership, not just a selected
    # file's split string. Preserve the current training files and live jobs.
    groups={r['source_group_id']for r in published.values()};train_overlap=[]
    with gzip.open(ROOT.parent/'prompts_72000_unified/videos.jsonl.gz','rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line)
            if r['split']=='train_final'and r['source_group_id']in groups:train_overlap.append(r['video_id'])
    assert not train_overlap,'replacement_source_group_overlaps_training'
    OUT.mkdir(exist_ok=False);(OUT/'assets').mkdir();(OUT/'references').mkdir();(OUT/'evidence').mkdir();PROTOCOL.mkdir(exist_ok=True)
    old_cases={r['clip_id']:r for r in protocol['cases']};new_cases={};new_inputs={};new_tasks={};mapping=[]
    source_objects={}
    for cid in TARGETS:
        s=state(cid);proof=proofs[cid];template=old_cases[TEMPLATES[cid]];theta,events,end,measure=source_truth(s,cid)
        assert len(events)==1;event=next(iter(events));label=events[event]
        assert event==primary(template)['event'];assert primary(template)['rgb_distance_admitted']
        folder=WORK/'sources'/cid
        if cid.startswith(('T04','T10')):
            assert fixed_context(s,cid[:3])==template['fixed_context_sha256'],'new_fixed_context_changed:'+cid
        if cid.startswith('T06'):
            objects={o['name']:o.get('spec',o)for o in s['dynamic_objects']};source_objects[cid]=objects
        video_hash=sha(folder/'reference.mp4');media=proof['media'];native=published[cid]['native_sample_id']if cid in published else'T18_CRITICAL_GPU_PAIR_20261103_'+cid
        schedule,prompts=new_prompts(s,cid,theta,published.get(cid),end,dict(proof,physics_dt_s=s['scene_overrides']['dt'],physics_steps_per_frame=s['render']['physics_steps_per_render_frame']))
        token_counts=[counts(text)for text in prompts];assert all(x['ltx']<=120 and x['wan']<=504 for x in token_counts),'new_prompt_too_long:'+cid
        image=OUT/'assets'/(cid+'_'+sha(folder/'condition.png')[:12]+'.png');shutil.copyfile(folder/'condition.png',image)
        reference=copy.deepcopy(published[cid]['download'])if cid in published else dict(local_path=(OUT/'references'/(cid+'.mp4')).relative_to(ROOT).as_posix(),publication_status='prepared_local_reference_not_published')
        reference['sha256']=video_hash
        if cid.startswith('T18'):shutil.copyfile(folder/'reference.mp4',OUT/'references'/(cid+'.mp4'))
        input_binding=dict(clip_id=cid,sample_id=native,prompt_variants_en=prompts,prompt_variant_sha256=[hashlib.sha256(t.encode()).hexdigest()for t in prompts],
            reference_video_sha256=video_hash,condition_image=image.relative_to(ROOT).as_posix(),condition_sha256=sha(image),condition_frame_index=4,
            source_width=media['width'],source_height=media['height'],evaluation_duration_s=schedule['physical_observation_duration_s'])
        new_inputs[cid]=input_binding
        new_tasks[cid]=dict(clip_id=cid,sample_id=native,scene_id=cid[:3],reference=reference,source_video_sha256=video_hash,
            condition_image=input_binding['condition_image'],condition_sha256=sha(image),condition_frame_index=4,
            source_width=media['width'],source_height=media['height'],prompt_en=prompts[0],prompt_variants_en=prompts,
            prompt_variant_sha256=input_binding['prompt_variant_sha256'],prompt_variant_token_counts=token_counts,
            prompt_policy='core100-aligned-compact-three-prompts',clock=schedule,evaluation_duration_s=schedule['physical_observation_duration_s'],
            verified_parameter_truth=dict(gravity=abs(s['scene_overrides']['gravity'][2]),**{primary(template)['axis']:theta}),
            source_group_id=published[cid]['source_group_id']if cid in published else next(r['source_group_id']for r in protected if r['native_sample_id']=='T18__bg01_home_ase__g03_earth__contact_friction__p019'and r['engine']=='genesis'),
            declared_controls=schedule,full_source_physics_config_evidence=proof,
            target_event=event,reference_release_version=VERSION,new_generation_required=True,new_annotation_required=True,
            legacy_generated_outputs_reusable=False,legacy_annotations_reusable=False)
        brackets=copy.deepcopy(primary(template)['intervals'])
        u=new_unit(template,cid,theta,label,video_hash,brackets)
        row=dict(clip_id=cid,scene_id=cid[:3],sample_id=native,reference_video_sha256=video_hash,reference_release_version=VERSION,
            condition_frame_index=4,end_frame_index=end,horizon_s=schedule['physical_observation_duration_s'],parameter=u['axis'],theta=theta,
            normalization_domain=template['normalization_domain'],normalization_span=u['normalization_span'],reference_events=events,
            fixed_context_sha256=template['fixed_context_sha256'],source_state_sha256=hashlib.sha256(gzip.decompress((folder/'source_state.json.gz').read_bytes())).hexdigest(),
            boundary_records=copy.deepcopy(template['boundary_records']),critical_units=[u],declared_gravity_mps2=abs(s['scene_overrides']['gravity'][2]),
            admitted_rgb_events=[event],rgb_reference_status='assistant_source_bound_visual_review',rgb_pending_reason=None,
            ordinary_generation_denominator_retained=True,full_EventExact_automatically_admitted=False,
            numerical_boundary_complete=True,original_family_boundary_complete=True,
            judge_protocol=copy.deepcopy(template['judge_protocol']),new_reference_measurement=measure,
            new_reference_source_proof=proof,reference_visual_review=visual[cid],
            old_outputs_or_labels_transferred=False,original_roster_replacement=True,
            parameter_outside_original_normalization_domain=not template['normalization_domain'][0]<=theta<=template['normalization_domain'][1])
        row['judge_protocol']['events']={event:row['judge_protocol']['events'][event]}
        row['boundary_records_source']='Inherited only after matching physical intervention context; original evidence retained; not an exact point root.'
        if cid.startswith('T18'):
            row['new_reference_measurement_scope']='New RGB replay of the already audited original GPU32 endpoint. Normalizer remains the original 0.08-0.8 span; 0.04 is explicitly outside that scan.'
        new_cases[cid]=row
        old=next(t for t in tasks if t['clip_id']==cid)
        mapping.append(dict(clip_id=cid,old_sample_id=old['sample_id'],old_reference_sha256=old['reference']['sha256'],new_sample_id=native,
            new_reference_sha256=video_hash,axis=u['axis'],theta=theta,event=event,label=label,brackets=brackets,
            normalized_absolute_interval=u['normalized_absolute_interval'],distance_bin=u['bin'],old_results_reusable=False))
    assert source_objects['T06_C02']==source_objects['T06_C03'],'T06_published_pair_physical_context_changed'
    assert new_cases['T06_C02']['reference_events']!=new_cases['T06_C03']['reference_events']
    assert new_cases['T18_C01']['reference_events']!=new_cases['T18_C02']['reference_events']
    updated=[new_tasks.get(t['clip_id'],copy.deepcopy(t))for t in tasks]
    assert Counter(t['clip_id'][:3]for t in updated)=={f'T{i:02}':5 for i in range(1,21)}
    assert len({t['reference']['sha256']for t in updated})==100
    assert all(t==u for t,u in zip(tasks,updated)if t['clip_id']not in TARGETS)
    write(OUT/'known_conditions.json',dict(version=VERSION,parent_version=manifest['version'],tasks=updated))
    write(OUT/'replacement_map.json',mapping);write(OUT/'previous_six_conditions.json',dict(tasks=[t for t in tasks if t['clip_id']in TARGETS]))
    write(OUT/'replacement_answers.json',dict(cases=[new_cases[cid]for cid in TARGETS]))
    write(OUT/'TRAINING_SCOPE.json',dict(new_published_source_groups=sorted(groups),current_training_overlap=train_overlap,
        existing_training_modified=False,new_T18_references_are_local_counterfactual_replays=True,
        source_family_exclusion_retained='T18 Earth friction source already held out; new states and RGB not in current training catalog',
        independent_context_claim=False,numerical_seed_variation='Published T04/T06/T10 contrast evidence retains per-source seeds; do not describe these as shared-reference-seed interventions.'))
    for name in ['FOUR_SOURCE_RECOVERY.json','T18_SOURCE_RECOVERY.json','VISUAL_REVIEW.json','AUTHOR_APPROVAL.json']:
        shutil.copyfile(WORK/name,OUT/'evidence'/name)
    write(OUT/'MANIFEST.json',dict(schema='core100-rebalanced-roster-v2',version=VERSION,registered_cases=100,
        retained=94,replaced=6,scene_counts={f'T{i:02}':5 for i in range(1,21)},
        parent_manifest=dict(path=(parent/'MANIFEST.json').relative_to(ROOT).as_posix(),sha256=sha(parent/'MANIFEST.json')),
        newly_replaced_generation_and_annotation_pending=TARGETS,
        inherited_generation_and_annotation_pending=manifest['model_generation_and_annotation_pending'],
        model_generation_and_annotation_pending=sorted(set(TARGETS+manifest['model_generation_and_annotation_pending'])),
        legacy_tasks_outputs_annotations_modified=False,training_split_modified=False,
        reference_selection_basis='Reference events, source binding and physical context; no generated-model scores used.',
        release_status='prepared; new six require independent generation and annotation; live station not migrated',
        files={p.relative_to(OUT).as_posix():sha(p)for p in sorted(OUT.rglob('*'))if p.is_file()}))
    pointer=ROOT/'catalog/core100_critical_pairs_v3.json'
    write(pointer,dict(version=VERSION,release_root='../'+OUT.relative_to(ROOT).as_posix(),manifest='MANIFEST.json',manifest_sha256=sha(OUT/'MANIFEST.json'),status='prepared_not_live'))
    result=copy.deepcopy(protocol);result.update(version=PROTOCOL.name,roster_release=VERSION,
        roster_pointer=dict(path=pointer.relative_to(ROOT).as_posix(),sha256=sha(pointer)),
        parent_registry=dict(path=protocol_path.relative_to(ROOT).as_posix(),sha256=sha(protocol_path)))
    result['cases']=[new_cases.get(r['clip_id'],copy.deepcopy(r))for r in protocol['cases']]
    result['input_bindings']=[new_inputs.get(r['clip_id'],copy.deepcopy(r))for r in protocol['input_bindings']]
    result['pairs']+=[dict(pair_id='T06_replacement_impact_force_v3',clips=['T06_C02','T06_C03'],pairing_mode='independent',source='new_reference_selection'),
        dict(pair_id='T18_original_gpu_friction_replay_v3',clips=['T18_C01','T18_C02'],pairing_mode='coupled_seed',source='same_original_simulation_seed_and_configuration')]
    summary=result['summary'];cases=result['cases']
    for name,flag in [('numerical_boundary','numerical_boundary_complete'),('original_family_boundary','original_family_boundary_complete')]:
        summary[name+'_cases']=sum(c[flag]for c in cases)
    summary['numerical_boundary_pending']=[c['clip_id']for c in cases if not c['numerical_boundary_complete']]
    summary['original_family_pending']=[c['clip_id']for c in cases if not c['original_family_boundary_complete']]
    summary['critical_rgb_distance_cases']=sum(primary(c)['rgb_distance_admitted']for c in cases)
    summary['critical_rgb_distance_pending']=[c['clip_id']for c in cases if not primary(c)['rgb_distance_admitted']]
    summary['admitted_near_cases']=sum(primary(c)['rgb_distance_admitted']and primary(c)['bin']=='near'for c in cases)
    summary['numerical_near_cases']=sum(primary(c)['bin']=='near'for c in cases)
    summary['reference_rgb_target_admitted']=summary['primary_rgb_event_cases']=sum(primary(c)['event']in c['admitted_rgb_events']for c in cases)
    summary['reference_rgb_target_pending']=summary['primary_rgb_event_pending']=[c['clip_id']for c in cases if primary(c)['event']not in c['admitted_rgb_events']]
    summary['registered_pairs']=len(result['pairs'])
    by_case={c['clip_id']:c for c in cases}
    for mode,prefix in [('independent','independent'),('coupled_seed','coupled_seed')]:
        pairs=[p for p in result['pairs']if p['pairing_mode']==mode]
        summary[prefix+'_registered_pairs']=len(pairs)
        summary[prefix+'_admitted_pairs']=sum(all(primary(by_case[cid])['rgb_distance_admitted']for cid in p['clips'])for p in pairs)
    for p in sorted(OUT.rglob('*')):
        if p.is_file():result['source_hashes'][p.relative_to(ROOT).as_posix()]=sha(p)
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();rp=PROTOCOL/('registry_'+digest[:12]+'.json');rp.write_bytes(raw)
    load_protocol(rp,digest)
    write(ROOT/'catalog/prepared_core100_critical_protocol_v3.json',dict(version=PROTOCOL.name,registry='../'+rp.relative_to(ROOT).as_posix(),registry_sha256=digest,
        status='prepared_not_live',roster_pointer=pointer.relative_to(ROOT).as_posix()))
    print(json.dumps(dict(version=VERSION,retained=94,replaced=6,registry=rp.relative_to(ROOT).as_posix(),sha256=digest,summary=summary)))


if __name__=='__main__':main()
