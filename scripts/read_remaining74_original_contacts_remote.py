"""Read pinned native source states and existing endpoints; CPU media only."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import zipfile

ROOT=Path('/data2/liyuhan/core100_remaining74_admission_20261101')
plan=json.loads((ROOT/'PLAN.json').read_text())
rows=[]
for job in plan:
    row=dict(clip_id=job['clip_id'],points=[])
    try:
        for point in job['points']:
            p=Path(point['state_path']);stored=p.read_bytes();raw=gzip.decompress(stored)if p.suffix=='.gz'else stored
            assert point['state_sha256'] in (hashlib.sha256(raw).hexdigest(),hashlib.sha256(stored).hexdigest()), 'state digest mismatch: '+str(p)
            state=json.loads(raw)
            native_isaac=state.get('metadata',{}).get('schema')=='isaac_genesis_repro_v1'
            if native_isaac:
                fs=[]
                for f in state['trajectory']:
                    contacts=[]
                    for c in f['contacts']:
                        actors=c['actors'];assert len(actors)==2
                        contacts.append(dict(entity_a=actors[0].rsplit('/',1)[-1],entity_b=actors[1].rsplit('/',1)[-1]))
                    fs.append(dict(f,contacts=contacts))
            else:fs=state['frames']
            a=job['condition_frame_index'];b=job['end_frame_index']
            if job['clip_id'].startswith(('T16','T17')):
                from recover_core100_released_scans import read_point
                fresh=read_point(p,job['clip_id'][:3])
                assert all(fresh[k]==point[k]for k in ('theta','labels','fixed_context_sha256','state_sha256'))
            selected=[f for f in fs if a<=f['frame_index']<=b]
            assert len(selected)==b-a+1
            if native_isaac:
                period=state['metadata']['physics_dt']*state['metadata']['steps_per_frame'];fps=state['metadata']['fps']
            elif 'scene_overrides'in state:
                period=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame'];fps=state['render']['fps']
            else:
                diag=state['time_diagnostic'];period=diag['sim_dt']*diag['physics_steps_per_render_frame'];fps=diag['render_fps']
            assert abs((b-a)*period-job['horizon_s'])<1e-6, 'native clock mismatch'
            pairs={};terminal=[]
            for f in selected:
                for c in f.get('contacts',[]):
                    pair=' / '.join(sorted([str(c.get('entity_a')),str(c.get('entity_b'))]))
                    pairs.setdefault(pair,[f['frame_index'],c.get('physics_step_index',-1)])
                    if f['frame_index']==b and pair not in terminal:terminal.append(pair)
            r=dict(point)
            r.update(stored_state_sha256=hashlib.sha256(stored).hexdigest(),native_fps=fps,
                   decoded_state_sha256=hashlib.sha256(raw).hexdigest(),record_contacts=state.get('scene_overrides',{}).get('record_contacts'),
                   physical_frame_period_s=period,condition_frame_index=a,end_frame_index=b,
                   first_contacts=pairs,terminal_contact_pairs=terminal,
                   all_frames_have_contacts=all('contacts'in f for f in selected[1:]),
                   experiment=state.get('experiment'),dynamic_objects=state.get('dynamic_objects'),
                   first_objects=selected[0]['objects'],last_objects=selected[-1]['objects'])
            if job.get('table_event_code'):
                ns={};exec(job['table_event_code'],ns)
                r['original_terminal_event']=ns['table_event'](state,selected[-1])
            if job['clip_id'].startswith('T14'):
                contract=state['experiment']['classification_contract'];name=contract['marker_name']
                exit_frame=next((f['frame_index']for f in selected[1:]if next(o['position'][0]for o in f['objects']if o['name']==name)>=contract['channel_exit_center_x_m']),None)
                r['original_gate_event']=dict(label=int(exit_frame is not None),first_exit_frame=exit_frame,classification_contract=contract)
            scene=job['clip_id'][:3]
            def position(frame,name):return next(o['position']for o in frame['objects']if o['name']==name)
            def contact_pair(a,b):
                hits=[(f['frame_index'],c.get('physics_step_index',0))for f in selected[1:]for c in f.get('contacts',[])if {c.get('entity_a'),c.get('entity_b')}=={a,b}]
                return min(hits)if hits else None
            if scene=='T01':
                delta=math.dist(position(selected[0],'t01v2_chain_mug'),position(selected[-1],'t01v2_chain_mug'))
                hit=contact_pair('t01v2_chain_can_2','t01v2_chain_mug')
                r['original_metric_events']=dict(labels=dict(full_chain=0 if delta<=.03 else 1 if hit else None),mug_final_displacement_m=delta,first_contact=hit,original_rule='can2/mug contact AND mug final displacement >0.03 m')
            if scene=='T02':
                baseline=int(state['render']['pre_static_frames']);signal='t02v2_signal_brass_ball'
                x0=position(fs[baseline],signal)[0];dx=max(position(f,signal)[0]-x0 for f in fs[baseline:b+1])
                r['original_metric_events']=dict(labels=dict(C2_signal_displaced_0p05m=int(dx>=.05)),signal_max_forward_dx_m=dx,original_release_baseline_frame=baseline,original_rule='original signal forward world-x displacement >=0.050 m from settled release baseline')
            if scene=='T03':
                hit=contact_pair('t03v5_impulsed_book','t03v5_upper_edge_can')
                r['original_metric_events']=dict(labels=dict(book_contacts_upper_can=int(hit is not None)),first_contact=hit,original_rule='original book / original upper can contact within original window; no cascade or second-fall substitution')
            if scene=='T05':
                threshold=state['experiment']['geometry_contract']['phone_center_full_pass_x_m']
                x=max(position(f,'t05v2_moving_phone')[0]for f in selected[1:])
                r['original_metric_events']=dict(labels=dict(gate_passage=int(x>=threshold)),phone_max_center_world_x_m=x,original_full_pass_x_m=threshold,original_rule='original phone center reaches original full-pass geometry threshold')
            if scene=='T06':
                required=job['required_contact_pairs'];hits=[contact_pair(a,b)for a,b in required]
                assert all('contacts'in f for f in selected)
                r['original_metric_events']=dict(labels=dict(complete_required_contact_chain=int(all(hits))),required_pairs=required,first_required_contacts=hits,original_rule='original required adjacent-pair recorded contact conjunction; original native exterior sampling retained, no new toppling/angle threshold')
                r['native_engine_metadata']=state['metadata']
            if scene=='T04':
                name='t04v3_chain_mug';track=[next(o for o in f['objects']if o['name']==name)for f in selected];q=track[0]['quaternion_xyzw']
                angles=[math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(x*x for x in q)*sum(x*x for x in o['quaternion_xyzw'])))))for o in track]
                delta=max(math.dist(track[0]['position'],o['position'])for o in track);hit=contact_pair('t04v3_chain_can_2',name);moved=max(angles)>=18 or delta>=.04
                r['original_metric_events']=dict(labels=dict(original_full_chain=0 if not moved else 1 if hit else None),mug_max_displacement_m=delta,mug_max_orientation_change_deg=max(angles),first_contact=hit,original_rule='can2/mug contact AND (max angle >=18 deg OR max displacement >=0.04 m)')
            if scene=='T08':
                threshold=state['experiment']['table_top_z']-.08;names=['t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug'];z={name:min(position(f,name)[2]for f in selected[1:])for name in names}
                r['original_metric_events']=dict(labels={n+'_below_table_8cm':int(z[n]<threshold)for n in names},minimum_world_z_m=z,original_threshold_world_z_m=threshold,original_rule='original object center z < original table_top_z -0.08 m')
            if scene=='T07':
                initial=position(fs[0],'t07_smartphone');delta=max(math.dist(initial,position(f,'t07_smartphone'))for f in fs[:b+1])
                r['original_metric_events']=dict(labels=dict(motion_ge_1cm=int(delta>=.01)),phone_max_displacement_m=delta,original_rule='original phone max 3D displacement from initial frame >=0.01 m')
            if scene=='T11':
                names=['t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case'];z={n:position(selected[-1],n)[2]for n in names}
                r['original_metric_events']=dict(labels={n+'_final_center_below_minus_10cm':int(z[n]<-.1)for n in names},final_world_z_m=z,original_rule='R011 final center world-z < -0.10 m')
            if scene=='T15'and job['clip_id']in('T15_C01','T15_C02','T15_C03'):
                z=min(position(f,'t15v4_closed_laptop')[2]for f in selected[1:])
                r['original_metric_events']=dict(labels=dict(laptop_reaches_original_fall_criterion=int(z<-.15)),laptop_min_center_world_z_m=z,original_rule='original V11 laptop center world-z < -0.15 m')
                r['review_target_frame']=next((f['frame_index']for f in selected[1:]if position(f,'t15v4_closed_laptop')[2]<-.15),b)
            if scene=='T15'and job['clip_id']in('T15_C04','T15_C05'):
                hit=contact_pair('t15v4_closed_laptop','t15v4_floor_phone')
                complete='all solver steps sampled'in state.get('physical_provenance',{}).get('contact_aggregation','')
                r['original_metric_events']=dict(labels=dict(laptop_contacts_phone=int(hit is not None)if complete or hit else None),first_contact=hit,original_contact_recording_contract=state.get('physical_provenance'),original_rule='same original laptop contacts same original floor phone')
            if scene=='T20':
                names=['t20_book','t20_can','t20_box','t20_cup'];hits=[contact_pair(a,b)for a,b in zip(names,names[1:])];delta=math.dist(position(selected[0],names[-1]),position(selected[-1],names[-1]))
                label=0 if delta<=.015 else int(hits==sorted(hits))if all(hits)else None
                r['original_metric_events']=dict(labels=dict(complete_propagation_original=label),first_contacts=hits,cup_final_displacement_m=delta,original_rule='ordered original three contacts AND cup final displacement >0.015 m')
            row['points'].append(r)
        native=job['points'][0];identity=json.loads(Path(job['video_identity_path']).read_text())
        assert identity['video_sha256']==job['video_sha256']
        video=Path(identity['video_path']);assert hashlib.sha256(video.read_bytes()).hexdigest()==job['video_sha256']
        if job.get('parent_video_path'):
            parent=Path(job['parent_video_path']);assert hashlib.sha256(parent.read_bytes()).hexdigest()==job['parent_video_sha256']
            def frame_hashes(p):
                output=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(p),'-vsync','0','-f','framemd5','-'])
                return [line.rsplit(b',',1)[-1].strip().decode()for line in output.splitlines()if line and not line.startswith(b'#')]
            a_hashes=frame_hashes(parent);assert len(a_hashes)==210 and a_hashes==frame_hashes(video)
            row['original_parent_video_sha256']=job['parent_video_sha256'];row['all_original_and_retimed_decoded_frames_identical']=True
        first=next(iter(row['points'][0]['first_contacts'].values()),[job['condition_frame_index']])[0]
        target=job.get('contact_pair')
        if target:
            first=row['points'][0]['first_contacts'].get(' / '.join(sorted(target)),[first])[0]
        first=row['points'][0].get('review_target_frame',first)
        indices=sorted(set([job['condition_frame_index'],job['end_frame_index'],*[max(job['condition_frame_index'],min(job['end_frame_index'],first+d))for d in range(-4,5)]]))
        dest=ROOT/job['clip_id'];dest.mkdir(exist_ok=True)
        expr='+'.join('eq(n,%d)'%x for x in indices)
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(video),'-vf',
                        "select='%s',scale=640:-1,tile=3x4"%expr,'-frames:v','1','-y',str(dest/'contact_sheet.jpg')],check=True)
        row.update(status='source_hash_clock_readback_verified',video_sha256=job['video_sha256'],review_frame_indices=indices,
                   contact_sheet_sha256=hashlib.sha256((dest/'contact_sheet.jpg').read_bytes()).hexdigest())
    except Exception as error:row.update(status='readback_failed',error_type=type(error).__name__,error=str(error))
    rows.append(row)
(ROOT/'READBACK.json').write_text(json.dumps(rows,indent=2))
with zipfile.ZipFile(ROOT/'READBACK.zip','w',zipfile.ZIP_DEFLATED)as z:
    z.write(ROOT/'READBACK.json','READBACK.json')
    for p in ROOT.glob('*/contact_sheet.jpg'):z.write(p,p.relative_to(ROOT))
print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'])for r in rows]))
