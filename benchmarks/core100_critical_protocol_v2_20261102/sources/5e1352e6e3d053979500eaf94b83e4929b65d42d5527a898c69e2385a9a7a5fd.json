"""Build a separate published-contrast pilot without changing Core100."""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
from fractions import Fraction

from physedit.core100_bindings import interval_distance
from physedit.prompt_contract import validate_text
from physedit.compact_prompt import counts,number
from scripts.recover_core100_released_scans import observe,normalized

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/critical_supplement_20261101'
OUT=ROOT/'benchmarks/critical_supplement_v1_20261101'
DOMAINS={'T04':[.08,.14],'T05':[1.11,1.16],'T10':[.08,.217],'T11':[1.8,3.6]}
AXES={'T04':'bottom_book_friction_coefficient','T05':'gap_ratio','T10':'support_x',
      'T11':'driver_initial_speed_command_mps'}
EVENTS={'T04':'original_full_chain','T05':'gate_passage',
        'T10':'support_pen_displacement_reaches_source_threshold',
        'T11':'t11_driver_eraser_final_center_below_minus_10cm'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def declared_schedule_and_prompts(state,row,scene,theta,end,proof):
    """Read declared settings only; never use contact outcomes or event labels."""
    pre=state['render']['pre_static_frames'];fps=float(Fraction(proof['media']['r_frame_rate']))
    period=proof['physics_dt_s']*proof['physics_steps_per_frame']
    # Saved static frames do not advance dynamics. Keep their declared hold
    # clock instead of treating them as physical integration steps (T10).
    remaining_static=max(0,min(end,pre-1)-4)
    active=max(0,end-max(4,pre-1))
    hold=remaining_static/fps;horizon=hold+active*period
    hold_text=str(Fraction(remaining_static,1)/Fraction(str(fps)))
    facts={key:value for key,value,_ in row['parameter_facts']}
    p=state['experiment']['parameter'];g=abs(state['scene_overrides']['gravity'][2])
    schedule=dict(remaining_static_frames=remaining_static,static_clock_hz=fps,
        initial_hold_duration_s=hold,active_state_frames=active,active_frame_period_s=period,
        physical_observation_duration_s=horizon,
        clock_convention='After condition frame 4: remaining saved static frames at source media FPS, then each saved active state at dt*steps_per_frame.')
    base=' Hold initial state for '+hold_text+' s. Gravity '+number(g)+' m/s^2. '
    if scene=='T04':
        assert p['support_pull_force_magnitude_n']==.46 and p['support_pull_force_duration_s']==1.1
        assert facts['ramp_angle_deg']==7.3 and facts['commanded_extraction_distance_m']==.175
        assert facts['t04v3_removable_support_bar.initial_speed']==.15
        body=('Then pull the support bar off-screen in +Y: 0.46 N for 1.1 s; bar initial speed 0.15 m/s. '
            'Extraction setting 0.175 m. Ramp 7.3 deg; bottom book and ramp friction '+number(theta)+'.')
    elif scene=='T05':
        assert facts['tray_angle_deg']==3
        body=('Then phone initial speed '+number(p['initial_speed_mps'])+' m/s; yaw '+number(p['initial_yaw_deg'])+
            ' deg. Tray 3 deg; phone/tray friction '+number(p['phone_tray_friction_coefficient'])+
            '; guide friction '+number(p['guide_friction_coefficient'])+'. Guide gap ratio '+number(theta)+
            '; width '+number(p['gap_width_m'])+' m.')
    elif scene=='T10':
        assert facts['t10_tape_roll.initial_speed']==1.8
        assert [facts['t10_support_pen.initial_Y'],facts['t10_support_pen.initial_Z']]==[.08,.16]
        assert [facts[n+'.mass']for n in ['t10_supported_folder','t10_support_pen','t10_tape_roll']]==[.05,.095,.18]
        body=('Then tape roll speed 1.8 m/s. Pen initial position ['+number(theta)+',0.08,0.16] m. Folder angle '+
            number(facts['t10_supported_folder.initial_angle'])+' deg. Masses: folder 0.05 kg, pen 0.095 kg, roll 0.18 kg.')
    else:
        force=state['runtime_force_summary'][0]
        assert p['driver_initial_speed_mps']==0 and force['frame_start']==0 and force['frame_end']==105 and fps==30
        assert force['force_world'][0]==p['driver_force_before_first_contact_n']
        assert force['force_world_after_first_contact'][0]==p['driver_force_between_contacts_n']
        assert force['force_world_after_contact'][0]==p['driver_force_after_second_contact_n']
        body=('Then eraser initial speed 0 m/s. Nominal drive '+number(theta)+' m/s. Off-screen +X eraser force: '+
            number(force['force_world'][0])+' N before eraser-relay contact; '+number(force['force_world_after_first_contact'][0])+
            ' N until relay-case contact; '+number(force['force_world_after_contact'][0])+' N for '+
            str(force['stop_after_contact_delay_frames'])+' frames afterward. Active force frames 0-105 at 30 Hz.')
        schedule['conditional_force_recipe']={k:force[k]for k in ['target','force_world','force_world_after_first_contact',
            'force_world_after_contact','first_contact_pair','stop_on_contact_pair','stop_after_contact_delay_frames','frame_start','frame_end']}
    variants=[lead+base+body for lead in ['Fixed camera.','Continue this scene with a fixed camera.','Preserve the scene and camera.']]
    for text in variants:validate_text(text)
    return schedule,variants


def measurement(state,scene):
    frames=state['frames'];p=state['experiment']['parameter']
    if scene=='T04':
        _,events=observe(state,scene);theta=p['bottom_book_friction_coefficient'];end=154
        track=[next(o for o in f['objects']if o['name']=='t04v3_chain_mug')for f in frames[4:155]]
        q=track[0]['quaternion_xyzw']
        angle=max(math.degrees(2*math.acos(min(1.,abs(sum(a*b for a,b in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(a*a for a in q)*sum(b*b for b in o['quaternion_xyzw'])))))for o in track)
        extra=dict(predicate='can2-mug contact AND (mug rotation >=18 degrees OR displacement >=0.04 m)',
            mug_maximum_displacement_m=max(math.dist(track[0]['position'],o['position'])for o in track),
            mug_maximum_rotation_deg=angle)
    elif scene=='T05':
        theta=p['gap_ratio'];end=209;threshold=state['experiment']['geometry_contract']['phone_center_full_pass_x_m']
        maximum=max(o['position'][0]for f in frames[5:end+1]for o in f['objects']if o['name']=='t05v2_moving_phone')
        events={EVENTS[scene]:int(maximum>=threshold)}
        extra=dict(maximum_phone_center_x_m=maximum,full_passage_threshold_x_m=threshold)
    elif scene=='T10':
        theta=state['experiment']['t10_design']['support_x_m'];end=209
        initial=next(o['position']for o in frames[4]['objects']if o['name']=='t10_support_pen')
        maximum=max(math.dist(initial,o['position'])for f in frames[5:end+1]for o in f['objects']if o['name']=='t10_support_pen')
        events={EVENTS[scene]:int(maximum>=.04)}
        extra=dict(maximum_pen_displacement_m=maximum,threshold_m=.04)
    else:
        value=p['parameter_value'];theta=value['driver_initial_speed_mps']if isinstance(value,dict)else value;end=154
        last={o['name']:o['position'][2]for o in frames[end]['objects']}
        events={EVENTS[scene]:int(last['t11_driver_eraser']<-.1)}
        extra=dict(driver_final_z_m=last['t11_driver_eraser'],threshold_z_m=-.1,
            actual_initial_driver_speed_mps=p.get('driver_initial_speed_mps'),
            intervention_is_a_released_force_recipe_command=True)
    if any(type(v)is not int or v not in [0,1]for v in events.values()):raise ValueError('reference_event_unknown')
    return float(theta),events,end,extra


def fixed_context(state,scene):
    specs={o['name']:copy.deepcopy(o.get('spec',o))for o in state['dynamic_objects']}
    if scene=='T04':
        for name in ['t04v3_folder_ramp_pbr','t04v3_stack_book_bottom']:
            specs[name]['friction']=0.
    elif scene=='T05':
        half=state['experiment']['parameter']['gap_ratio']*.076/2
        for name in ['t05v2_guide_left','t05v2_guide_right']:
            y=specs[name]['pose']['position'][1];specs[name]['pose']['position'][1]-=half*(1 if y>0 else-1)
    elif scene=='T10':
        for name in ['t10_supported_folder','t10_support_pen','t10_tape_roll']:
            # The released support_x recipe jointly places and tilts these
            # objects. All masses, materials, dimensions and actuation stay.
            specs[name].pop('pose',None)
    forces=copy.deepcopy(state.get('runtime_forces',[]))
    if scene=='T11':
        for force in forces:
            for name in ['force_world','force_world_after_contact','stop_after_contact_delay_frames']:
                force.pop(name,None)
    keys=['gravity','dt','substeps','use_gjk_collision','box_box_detection','enable_multi_contact',
          'static_scene_collision','layout_collision','add_ground_plane']
    payload=normalized(dict(objects=specs,forces=forces,physics={k:state['scene_overrides'].get(k)for k in keys},
        pre_static_frames=state['render'].get('pre_static_frames')))
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def main():
    catalog=json.loads((WORK/'selected_catalog_rows.json').read_text(encoding='utf8'))
    source_proofs={r['supplement_id']:r for r in json.loads((WORK/'SOURCE_RECOVERY.json').read_text())['sources']}
    from physedit.core100_release import load
    _,core_manifest,core_conditions,_=load()
    core_ids={r['sample_id']for r in core_conditions['tasks']}
    training_groups=set();training_hashes=set()
    with gzip.open(ROOT.parent/'prompts_72000_unified/videos.jsonl.gz','rt',encoding='utf8')as handle:
        for line in handle:
            row=json.loads(line)
            if row.get('split')=='train_final':training_groups.add(row.get('source_group_id'));training_hashes.add(row['sha256'])
    inputs=[];answers=[];ledger=[]
    review_path=WORK/'VISUAL_REVIEW.json'
    reviews=json.loads(review_path.read_text(encoding='utf8'))['cases']if review_path.exists()else{}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'assets').mkdir(exist_ok=True);(OUT/'evidence').mkdir(exist_ok=True)
    for row in catalog:
        cid=row['supplement_id'];scene=cid[:3];folder=WORK/'sources'/cid;proof=source_proofs[cid]
        assert proof['state_video_byte_identity_verified'],'source_state_video_link_unverified:'+cid
        assert row['native_sample_id']not in core_ids and row['sha256']not in training_hashes
        assert row['source_group_id']not in training_groups,'source_group_overlaps_training'
        for name,digest in proof['files'].items():assert sha(folder/name)==digest
        state=json.loads(gzip.decompress((folder/'source_state.json.gz').read_bytes()))
        theta,events,end,measured=measurement(state,scene)
        period=proof['physics_dt_s']*proof['physics_steps_per_frame']
        schedule,variants=declared_schedule_and_prompts(state,row,scene,theta,end,proof)
        horizon=schedule['physical_observation_duration_s']
        assert 0<period<1 and 0<horizon<10
        asset='assets/'+cid+'.png';shutil.copyfile(folder/'condition.png',OUT/asset)
        state_name='evidence/'+cid+'.json.gz';shutil.copyfile(folder/'source_state.json.gz',OUT/state_name)
        visual_name='evidence/'+cid+'_visual.png'
        shutil.copyfile(folder/'visual_audit_sheet.png',OUT/visual_name)
        assert len(variants)==3
        for text in variants:validate_text(text)
        inputs.append(dict(point_id=cid,scene_id=scene,native_sample_id=row['native_sample_id'],
            reference_video_sha256=row['sha256'],reference_download=row['download'],
            condition_image=asset,condition_image_sha256=sha(OUT/asset),condition_frame_index=4,
            source_width=proof['media']['width'],source_height=proof['media']['height'],
            source_group_id=row['source_group_id'],family_id=AXES[scene],theta=theta,
            evaluation_duration_s=horizon,physical_frame_period_s=period,end_frame_index=end,
            reference_media_fps=proof['media']['r_frame_rate'],
            prompt_variants_en=variants,prompt_sha256=[hashlib.sha256(t.encode()).hexdigest()for t in variants],
            source_prompt_sha256=row['prompt_sha256'],prompt_policy='compact-three-variants-declared-source-schedule-v1',
            declared_schedule=schedule,prompt_token_counts=[counts(t)for t in variants],
            parameter_facts=row.get('parameter_facts'),external_control_disclosure=row.get('external_control_disclosure'),
            external_control_inputs=row.get('external_control_inputs'),
            training_partition=row['split']))
        review=reviews.get(cid,{})
        if review:
            assert review['video_sha256']==row['sha256'] and review['status']=='pass_for_registered_target'
            assert sha(folder/'visual_audit_sheet.png')==review['sheet_sha256']
        admission=(dict(status='admitted',scope='registered_target_reference_for_separate_pilot',
            state_and_video_identity_verified=True,reviewer='assistant_visual_and_state_audit',
            review=review,independent_human_reviewer_claimed=False,whole_video_physical_certification_granted=False)
            if review else dict(status='pending_visual_review',state_and_video_identity_verified=True))
        answers.append(dict(point_id=cid,source_group_id=row['source_group_id'],scene_id=scene,
            family_id=AXES[scene],theta=theta,target_event=EVENTS[scene],events=events,
            end_frame_index=end,evaluation_duration_s=horizon,reference_video_sha256=row['sha256'],
            gravity=abs(state['scene_overrides']['gravity'][2]),required_order=[],
            event_vector_scope='target_event_only; full causal EventExact is not registered by this supplement',
            inversion=dict(status='pending_reference_validation',reason='No new inversion-eligibility registration; event generation remains retained.'),
            reference_admission=admission,
            fixed_context_sha256=fixed_context(state,scene),
            measurements=measured,source_state=state_name,source_state_sha256=sha(OUT/state_name)))
        ledger.append(dict(point_id=cid,proof=proof,source_download=row['source_download'],
            raw_metadata_sha256=proof['source_state_raw_sha256'],
            split=row['split'],source_group_id=row['source_group_id'],training_hash_overlap=False,training_group_overlap=False,
            quality_admission_status=row['quality_admission_status'],reference_download=row['download'],
            visual_evidence=visual_name,visual_evidence_sha256=sha(OUT/visual_name)))
    pairs=[]
    for scene in ['T04','T05','T10','T11']:
        own=[a for a in answers if a['scene_id']==scene];assert len(own)==2
        own.sort(key=lambda a:a['theta']);low,high=own
        event=EVENTS[scene]
        assert low['events'][event]!=high['events'][event],'reference_pair_does_not_flip:'+scene
        assert low['source_group_id']==high['source_group_id']
        assert low['fixed_context_sha256']==high['fixed_context_sha256'],'unregistered_physics_context_changed:'+scene
        assert abs(low['evaluation_duration_s']-high['evaluation_duration_s'])<1e-8
        bracket=[low['theta'],high['theta']];domain=DOMAINS[scene]
        pair_id=scene+'_published_contrast_01'
        for a in own:
            a.update(pair_ids=[pair_id],pairing_mode='independent',normalization_domain=domain,
                boundary=dict(status='verified',bracket=bracket,normalization_span=domain[1]-domain[0],
                    source='reference_ledger.json',scope='Observed published local contrast interval; not a unique deterministic or nearest-global physical threshold.',
                    physical_threshold_certified=False),
                distance=interval_distance(a['theta'],bracket,domain[1]-domain[0]))
        pairs.append(dict(pair_id=pair_id,scene_id=scene,source_group_id=low['source_group_id'],
            family_id=AXES[scene],points=[low['point_id'],high['point_id']],
            endpoint_labels=[low['events'][event],high['events'][event]],bracket=bracket,
            normalization_domain=domain,pairing_mode='independent'))
    for name,value in [('conditions.json',dict(schema='critical-supplement-conditions-v1',version=OUT.name,tasks=inputs)),
                       ('answers.json',dict(schema='critical-supplement-answers-v1',points=answers,pairs=pairs)),
                       ('reference_ledger.json',ledger)]:
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    preserved={}
    pointer=ROOT/'catalog/active_core100_conditions.json';policy=json.loads(pointer.read_text());base=(pointer.parent/policy['release_root']).resolve()
    for p in [pointer,base/policy['manifest'],base/'known_conditions.json']:preserved[p.relative_to(ROOT).as_posix()]=sha(p)
    manifest=dict(schema='critical-supplement-release-v1',version=OUT.name,
        authorized_scope='Separate supplement; frozen Core100 and historical outputs/labels unchanged.',
        core100_version=core_manifest['version'],core100_preserved=preserved,
        summary=dict(reference_videos=len(inputs),published_cross_boundary_pairs=len(pairs),
            numerically_near_points=sum(a['distance']['bin']=='near'for a in answers),
            target_reference_admitted=sum(a['reference_admission']['status']=='admitted'for a in answers),
            visual_admission_pending=sum(a['reference_admission']['status']!='admitted'for a in answers),
            generated_model_outputs=0,formal_model_scores_computed=False,
            distinct_scene_source_contexts=len(pairs),EventExact_applicable=False),
        files={p.relative_to(OUT).as_posix():sha(p)for p in sorted(OUT.rglob('*'))if p.is_file()and p.name!='MANIFEST.json'})
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    pointer=dict(schema='active-critical-supplement-v1',version=OUT.name,
        release_root='../'+OUT.relative_to(ROOT).as_posix(),manifest='MANIFEST.json',
        manifest_sha256=sha(OUT/'MANIFEST.json'),separate_from_core100=True,
        generated_model_outputs=0)
    (ROOT/'catalog/active_critical_supplement.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    print(json.dumps(manifest['summary']))


if __name__=='__main__':main()
