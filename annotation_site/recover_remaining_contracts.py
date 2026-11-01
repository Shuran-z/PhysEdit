"""Recover original outcome predicates and recompute exact Core100 source states.

This is a source audit, not generated-video accuracy or reference admission.
Never infer a missing motion threshold from measured examples.
"""
import ast
import collections
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import tempfile

ROOT = Path('review/original_contract_audit_20261023')
SRC = ROOT / 'remaining_sources'
BASE = Path('review/scene_family_completion_20261018')
RES = Path('annotation_site/resources')
SCENES = ('T03', 'T04', 'T08', 'T11', 'T12', 'T13', 'T16', 'T17', 'T19', 'T20')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def definition(name, text, actors, source, rule=None, **extra):
    d = dict(name=name, definition=text, definition_zh=name, actors=actors,
             applicable=True, minimum_evidence_times=0, original_source=str(source),
             original_source_sha256=sha(source), **extra)
    if rule:
        quantity, op, threshold, unit = rule
        d['metric_rule'] = dict(unit=unit, combine='all', clauses=[dict(
            quantity=quantity, operator=op, threshold=threshold, unit=unit)])
    return d


def recover():
    headers = json.loads(Path('review/annotation_event_contracts_20261023/merged_source_headers.json').read_text(encoding='utf-8'))
    states = json.loads(gzip.decompress((SRC/'exact_original_states.json.gz').read_bytes()))
    qa = json.loads((SRC/'original_production_qa.json').read_text(encoding='utf-8'))
    source_t03 = SRC/'6132aa3599_audit_t03_v5_multilevel_cascade.py'
    source_t04 = BASE/'original_completion_sources/audit_t04_v4_quality.py'
    source_t08 = BASE/'original_completion_sources/analyze_t08_v3_metrics.py'
    source_multi = SRC/'fd4e8c6a1d_qa_pipeline.py'
    source_t13 = SRC/'cf2f017578_run_t13_frozen_v4_queue.py'
    # Execute only the original pure outcome/contact function AST nodes. No renderer,
    # video QA, command-line main or simulation is run.
    tree = ast.parse(source_multi.read_text(encoding='utf-8'))
    names = {'contact_names', 'pair_contact', 'first_pair_contact_key', 'outcome'}
    mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    env = {'math': math, 'Any': object}
    exec(compile(mod, str(source_multi), 'exec'), env)
    t03 = runpy.run_path(str(source_t03))
    t04 = runpy.run_path(str(source_t04))
    rows = []; recovered = {}
    for clip, header in sorted(headers.items()):
        scene = clip[:3]
        if scene not in SCENES:
            continue
        if clip in states:
            bound = states[clip]; state = bound['data']; path = bound['path']; digest = bound['sha256']
        else:
            p = BASE/'completion_states'/scene/(header['sample_id']+'.json.gz')
            state = json.loads(gzip.decompress(p.read_bytes())); path = str(p); digest = sha(p)
        exp = state['experiment']
        sid = exp.get('trajectory_id') or exp.get('case')
        # Some original T12/T13 exports omit a trajectory ID; exact path + original
        # source-header projection must agree instead. Compare every saved experiment field.
        changed=[k for k,v in header['experiment'].items() if exp.get(k)!=v]
        if any(k!='camera_revision' and not (scene=='T08' and k=='formal_sampling') for k in changed):
            raise ValueError('source experiment mismatch: '+clip)
        binding_notes=['原配置有camera_revision修复标记，原状态未带该标记；物理字段一致，但仍缺修复后参考RGB绑定'] if changed else []
        source_specs={o['name']:o.get('spec',o) for o in header['dynamic_objects']}
        state_specs={o['name']:o.get('spec',o) for o in state['dynamic_objects']}
        spec_differences={n:[k for k,v in s.items() if state_specs.get(n,{}).get(k)!=v] for n,s in source_specs.items()}
        spec_differences={n:keys for n,keys in spec_differences.items() if keys}
        if spec_differences:
            binding_notes=['同名发布状态与源配置候选存在对象规格差异，参考标签仅诊断；须核验生成条件对应的确切参考媒体/渲染状态']
        published_reference_binding=None
        if scene=='T08' and Path('review/core100_admission_20261023/t08_pinned_paths_info.json').exists():
            proof_root=Path('review/core100_admission_20261023')
            conditions=json.loads((proof_root/'v6_known_conditions.json').read_text(encoding='utf-8'))
            ref=next(t['reference'] for t in conditions['tasks'] if t['clip_id']==clip)
            info={r['path']:r for r in json.loads((proof_root/'t08_pinned_paths_info.json').read_text(encoding='utf-8'))}
            video=ref['source_video_path'];metadata=video.replace('/videos/','/metadata/').replace('.mp4','.json.gz')
            assert info[video]['lfs']['oid']==ref['sha256'] and info[metadata]['lfs']['oid']==digest
            published_reference_binding={**ref,'metadata_path':metadata,'metadata_sha256':digest,'binding_kind':'same_pinned_release_sample_and_camera_LFS_hashes','evidence_sha256':sha(proof_root/'t08_pinned_paths_info.json')}
            binding_notes=['已核对v6冻结参考：视频与同目录cam01状态LFS哈希全部匹配；先前配置为求解器v5之前的候选，不能代表实际发布渲染规格。旧规格差异保留审计，实际状态版本对应已闭合；RGB可观察性和共同窗仍单独准入']
        if sid != header['sample_id'] and header['sample_id'] not in path:
            raise ValueError('source identity mismatch: '+clip)
        frames = state['frames']
        if len(frames) != (168 if scene == 'T13' else 210):
            raise ValueError('incomplete original state: '+clip)
        tracks = {}
        for f in frames:
            for obj in f['objects']:
                p = obj['position']
                if not all(math.isfinite(v) for v in p):
                    raise ValueError('nonfinite state: '+clip)
                tracks.setdefault(obj['name'], []).append(obj)
        if any(len(v) != len(frames) for v in tracks.values()):
            raise ValueError('incomplete object track: '+clip)
        moves = {n: math.dist(s[0]['position'], s[-1]['position']) for n, s in tracks.items()}
        main = {}; labels = {}; metrics = {}; gaps = []; outcome = None; source = None
        telemetry = any('contacts' in f for f in frames)
        def contact(a,b):
            return any({c.get('entity_a'),c.get('entity_b')} == {a,b} for f in frames for c in f.get('contacts',[])) if telemetry else None
        if scene in ('T03', 'T04'):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/'original.json'; p.write_text(json.dumps(state), encoding='utf-8')
                data = t03['audit_one'](p) if scene == 'T03' else t04['analyze'](p)
            if scene == 'T03':
                source = source_t03; outcome = data['observed_outcome']; metrics = data
                main['book_contacts_upper_can'] = definition('书本接触上层罐子', 'The original book contacts the upper can at least once.', ['t03v5_impulsed_book','t03v5_upper_edge_can'], source)
                main['can_lands_on_lower_shelf'] = definition('罐子接触下层托架', 'The original upper can contacts the lower transfer ramp at least once.', ['t03v5_upper_edge_can','t03v5_lower_transfer_ramp'], source)
                main['phone_second_fall_original'] = definition('手机完成二次跌落', 'Original C2 outcome: book-can, can-lower-shelf and can-phone contacts all occur, phone-floor contact occurs, and the phone center drops strictly more than 0.20 m from the pre-static-frame baseline. Contacts are source branch prerequisites, not a new contact-order test.', ['t03v5_impulsed_book','t03v5_upper_edge_can','t03v5_lower_edge_phone'], source, component_definitions={'phone_drop':definition('手机下落量','Original phone-center drop relative to the pre-static baseline.',['t03v5_lower_edge_phone'],source,('phone_center_drop_from_pre_static_m','>',.20,'m'))},source_boolean_expression='book_can AND can_shelf AND can_phone AND phone_floor AND phone_drop')
                labels = dict(book_contacts_upper_can=data['first_contact_frame']['book_can'] is not None, can_lands_on_lower_shelf=data['first_contact_frame']['can_lower_shelf'] is not None, phone_second_fall_original=outcome=='C2_full_chain_phone_second_fall')
            else:
                source = source_t04; outcome = data['outcome_label']; metrics = data
                rule = {'unit':'m_or_degree','combine':'any','clauses':[
                    {'quantity':'mug_max_rotation_from_first_frame_deg','operator':'>=','threshold':18.,'unit':'degree'},
                    {'quantity':'mug_max_3d_displacement_from_first_frame_m','operator':'>=','threshold':.040,'unit':'m'}]}
                d = definition('末端杯子达到原完整链判据', 'Original V4 full_chain: can2 contacts the mug AND (maximum mug rotation from its first pose is at least 18 degrees OR maximum 3D mug displacement from its first pose is at least 0.040 m).', ['t04v3_chain_can_2','t04v3_chain_mug'], source)
                # Mixed units are represented as independent component rules, never
                # treated as one fabricated common unit.
                d['component_definitions'] = {
                    'rotation':definition('杯子转角', 'Original maximum quaternion angle from first pose.', ['t04v3_chain_mug'], source, ('mug_max_rotation_from_first_frame_deg','>=',18.,'degree')),
                    'displacement':definition('杯子位移', 'Original maximum 3D displacement from first pose.', ['t04v3_chain_mug'], source, ('mug_max_3d_displacement_from_first_frame_m','>=',.040,'m'))}
                d['source_boolean_expression']='can2_mug_contact AND (rotation OR displacement)'
                main['original_full_chain']=d; labels['original_full_chain']=outcome=='full_chain'
        elif scene == 'T08':
            source=source_t08
            for actor,short in [('t08_lower_impactor_book','下层书'),('t08_upper_payload_book','上层书'),('t08_target_mug','杯子')]:
                threshold=exp['table_top_z']-.08; key=actor+'_below_table_8cm'
                main[key]=definition(short+'达到原离桌判据', 'The original '+actor+' center reaches z strictly below the original table top minus 0.08 m at any frame. This is original left_table, not verified floor landing.', [actor], source, (actor+'_min_center_world_z_m','<',threshold,'m'))
                z=min(o['position'][2] for o in tracks[actor]);metrics[actor+'_min_center_world_z_m']=z;labels[key]=z<threshold
            outcome=';'.join(k for k,v in labels.items() if v) or 'all_centers_above_departure_threshold'
        elif scene in ('T16','T17','T19','T20'):
            source=source_multi
            data=env['outcome'](scene,state,{'displacements_m':moves});outcome=data['outcome_label'];metrics={**data,'final_3d_displacements_m':moves}
            old=qa[clip]['data']
            if old['sample_id']!=header['sample_id'] or old['outcome_label']!=outcome:
                raise ValueError('Original QA outcome mismatch: '+clip)
            metrics['original_production_qa_sha256']=qa[clip]['sha256'];metrics['original_production_qa_match']=True
            if scene=='T16':
                native=Path('scripts/collect_t16_t20_published_events.py')
                main['folder_downstream_contact']=definition('文件夹接触下游盒子','The original folder and downstream box contact at least once in the observation window. This is the native contact event in the source event sequence, distinct from downstream displacement.', ['t16_folder','t16_downstream_box'],native)
                main['downstream_response_original']=definition('下游盒子产生响应', 'Original tips_and_triggers_downstream predicate: downstream box final-to-first 3D displacement strictly exceeds 0.015 m. Maximum excursion and contact alone are not this predicate.', ['t16_downstream_box'],source,('downstream_box_final_3d_displacement_m','>',.015,'m'))
                main['folder_motion_original']=definition('文件夹达到原运动判据', 'Original folder final-to-first 3D displacement strictly exceeds 0.08 m; original outcome gives downstream response priority over this secondary condition.', ['t16_folder'],source,('folder_final_3d_displacement_m','>',.08,'m'))
                labels=dict(folder_downstream_contact=contact('t16_folder','t16_downstream_box'),downstream_response_original=moves['t16_downstream_box']>.015,folder_motion_original=moves['t16_folder']>.08)
            elif scene=='T17':
                native=Path('scripts/collect_t16_t20_published_events.py')
                main['can_tissue_box_contact']=definition('罐子接触纸巾盒','The original can and tissue box contact at least once in the observation window. The motion-based hit surrogate and final-frame contact are different events.', ['t17_can','t17_tissue_box'],native)
                main['hit_tissue_box_original']=definition('罐子触发纸巾盒命中分支', 'Original hit predicate: native can/tissue-box contact occurs OR tissue-box final-to-first 3D displacement exceeds 0.02 m. This is the original hits_tissue_box classifier, not contact alone.', ['t17_can','t17_tissue_box'],source,component_definitions={'box_motion':definition('纸巾盒末态位移','Original final-to-first 3D box displacement.',['t17_tissue_box'],source,('tissue_box_final_3d_displacement_m','>',.02,'m'))},source_boolean_expression='native_can_box_contact OR box_motion')
                main['can_below_table_original']=definition('罐子末态达到原离桌判据', 'Original fell predicate: can final center z is strictly below source surface_z minus 0.05 m; hit has priority when deriving the outcome category.', ['t17_can'],source,('can_final_center_world_z_m','<',exp['surface_z']-.05,'m'))
                labels=dict(can_tissue_box_contact=contact('t17_can','t17_tissue_box'),hit_tissue_box_original=contact('t17_can','t17_tissue_box') or moves['t17_tissue_box']>.02,can_below_table_original=tracks['t17_can'][-1]['position'][2]<exp['surface_z']-.05)
            elif scene=='T19':
                if exp.get('event_variant_version') or 't19_can2' not in tracks:raise ValueError('Not the original two-can scene')
                main['can2_transfer_original']=definition('第二个罐子达到原动量传播判据','Original two-can target response: can2 final-to-first 3D displacement strictly exceeds 0.015 m. This does not assert a later Isaac or multi-object target.', ['t19_can2'],source,('can2_final_3d_displacement_m','>',.015,'m'))
                main['target_edge_original']=definition('第二个罐子达到原边缘判据','Original two-can edge_event: can2 final center planar distance to support_center strictly exceeds support_radius OR final center z is below surface_z minus 0.05 m. The historical dual_can_edge_event label tests the target can only.', ['t19_can2'],source,component_definitions={'radial':definition('末态径向距离','Original planar distance from support center.',['t19_can2'],source,('can2_final_radial_distance_m','>',exp['support_radius'],'m')),'height':definition('末态高度','Original target height test.',['t19_can2'],source,('can2_final_center_world_z_m','<',exp['surface_z']-.05,'m'))},source_boolean_expression='radial OR height')
                p=tracks['t19_can2'][-1]['position'];center=exp['support_center'];edge=math.hypot(p[0]-center[0],p[1]-center[1])>exp['support_radius'] or p[2]<exp['surface_z']-.05
                labels=dict(can2_transfer_original=moves['t19_can2']>.015,target_edge_original=edge)
            else:
                main['complete_propagation_original']=definition('三段接触依次完成且杯子响应','Original complete_propagation: first book-can, can-box and box-cup contacts all occur in nondecreasing (frame_index, physics_step_index) order AND cup final-to-first 3D displacement strictly exceeds 0.015 m. Three unordered contacts alone are insufficient.', ['t20_book','t20_can','t20_box','t20_cup'],source,component_definitions={'cup_response':definition('杯子末态响应','Original cup final-to-first 3D displacement.',['t20_cup'],source,('cup_final_3d_displacement_m','>',.015,'m'))},required_contact_pairs=exp['required_contact_pairs'],source_order='nondecreasing first (frame_index, physics_step_index)',source_boolean_expression='ordered_three_contact_chain AND cup_response')
                labels['complete_propagation_original']=outcome=='complete_propagation'
        else:
            if scene=='T11':
                source=SRC/'0a6ff459b8_run_t11_r010_formal.py'
                pairs=exp['required_contact_pairs'];keys=[]
                for a,b in pairs:
                    hits=[(i,c.get('physics_step_index',0)) for i,f in enumerate(frames) for c in f.get('contacts',[]) if {c.get('entity_a'),c.get('entity_b')}=={a,b}]
                    keys.append(min(hits) if hits else None)
                metrics={'ordered_chain':all(k is not None for k in keys) and keys==sorted(keys,key=lambda v:v if v else (-1,-1)), 'first_contact_frame_steps':keys,'final_center_z_m':{n:tracks[n][-1]['position'][2] for n in exp['tracked_objects']}}
                release_path=Path('review/core100_admission_20261023/remaining15_original_release_evidence.json')
                if release_path.exists():
                    releases=json.loads(release_path.read_text(encoding='utf-8'))
                    accepted=next(r for r in releases if r['path'].endswith('/pilot_acceptance.json'))
                    release=next(r for r in releases if r['path'].endswith('/pilot_release.json'))
                    assert accepted['data']['contract']=='T11_R011_FOUR_OUTCOME_SLOW_CHAIN_RELEASE_WIDE_FLOOR'
                    assert release['data']['quality']=='formal_r011_720p' and release['data']['evidence_sha256'][accepted['path']]==accepted['sha256']
                    matrix_file=release_path.parent/'t11_R011_matrix_binding.json'
                    matrix=json.loads(matrix_file.read_text(encoding='utf-8'))
                    assert matrix['matrix_sha256']==matrix['expected_sha256']==release['data']['matrix_sha256']
                    assert matrix['rows'][clip]['config_sha256']==header['sha256']
                    source=SRC/'9039954de6_release_t11_r010_formal.py'
                    for actor,short in [('t11_driver_eraser','橡皮'),('t11_relay_pencil_case','接力笔盒'),('t11_eyeglasses_case','眼镜盒')]:
                        key=actor+'_final_center_below_minus_10cm'
                        main[key]=definition(short+'达到原末态跌落判据','Original R011 release-gate fallen_objects predicate: the '+actor+' final center world z is strictly below -0.10 m. The parameterized release script supports R011 through T11_FORMAL_QUALITY/REVISION; R011 pilot_release seals its four-outcome acceptance. Do not substitute the R009 -0.20 m probe predicate.',[actor],source,(actor+'_final_center_world_z_m','<',-.10,'m'))
                        labels[key]=tracks[actor][-1]['position'][2]<-.10
                    metrics['R011_release_binding']={'acceptance_sha256':accepted['sha256'],'release_sha256':release['sha256'],'matrix_binding_sha256':sha(matrix_file),'source_hash_is_current_recovered_code_not_historical_execution_attestation':True}
                    outcome='fallen_count_'+str(sum(labels.values()))
                else:gaps=['R011原生产链条审计可恢复，但尚无R011正式跌落目标提取合同；旧探针不迁移为正式阈值']
            elif scene=='T12':
                source=SRC/'63c7df20a8_build_t12_formal_r001.py'
                metrics={'tissue_box_final_3d_displacement_m':moves['t12_tissue_box'], 'tissue_box_max_3d_displacement_m':max(math.dist(tracks['t12_tissue_box'][0]['position'],o['position']) for o in tracks['t12_tissue_box']), 'native_contacts_present':telemetry}
                gaps=['R002原配置只列no_contact/subcritical_transfer/sustained_transfer，未给运动阈值；原生产worker只做视频校验，未实现分支提取；该批5条状态均无原生接触遥测，不能把缺接触记录算未接触']
            else:
                source=source_t13
                labels={k:contact(*pair) for k,pair in {'driver_to_falling_book_contact':('t13_driver_book','t13_falling_book'),'falling_book_to_drink_contact':('t13_falling_book','t13_drink_box')}.items()}
                ss=tracks['t13_drink_box'];metrics={'drink_max_displacement_from_frame18_m':max(math.dist(ss[18]['position'],o['position']) for o in ss[18:]),'drink_drop_from_frame18_m':ss[18]['position'][2]-min(o['position'][2] for o in ss[18:]),'native_contacts_present':telemetry}
                gaps=['F5原队列明确两个接触和先后约束，但未找到complete_chain_fallen的正式二分类提取合同；原release audit的1cm仅为运动起始检测，不是跌落阈值；不采用新增5cm']
        if main:
            if any(a not in tracks for d in main.values() for a in d['actors']):
                raise ValueError('event actor not in original state: '+clip)
            recovered[clip]={'events':main,'source':str(source),'source_sha256':sha(source),
                'scope':'original_outcome_predicates; per-family boundary target and reference admission still required'}
        rows.append(dict(clip_id=clip,source_sample_id=header['sample_id'],source_config_sha256=header['sha256'],source_state_path=path,source_state_sha256=digest,frame_count=len(frames),original_experiment_exact_match=not changed,original_physical_experiment_match=not spec_differences and not any(k!='camera_revision' for k in changed),source_spec_differences=spec_differences,state_binding_notes=binding_notes,published_reference_binding=published_reference_binding,extraction_source=str(source),extraction_source_sha256=sha(source),contract_recovered=bool(main),reference_labels={k:(int(v) if v is not None else None) for k,v in labels.items()},original_outcome=outcome,metrics=metrics,missing=gaps,reference_admission='pending_media_window_visual_observability',NearAcc_eligible=False,PairAcc_eligible=False))
    summary=dict(audited_remaining_cases=len(rows),same_id_source_states_found=len(rows),original_outcome_contracts_recovered=len(recovered),critical_contracts_still_missing=sum(not r['contract_recovered'] for r in rows),source_spec_mismatch_cases=[r['clip_id'] for r in rows if r['source_spec_differences']],published_video_state_bindings_verified=sum(bool(r['published_reference_binding']) for r in rows),original_qa_recomputed_and_matched=sum(bool(r['metrics'].get('original_production_qa_match')) for r in rows),NearAcc_eligible=0,PairAcc_eligible=0)
    report={'schema':'remaining50-original-source-recovery-v1','summary':summary,'rows':rows}
    for folder in [ROOT,RES]:
        (folder/'remaining50_recovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'recovered_event_definitions.json').write_text(json.dumps(recovered,ensure_ascii=False,indent=2),encoding='utf-8')
        s=io.StringIO(newline='');w=csv.writer(s);w.writerow(['clip_id','sample_id','contract_recovered','original_outcome','reference_labels_diagnostic','state_sha256','extractor_source','extractor_sha256','missing','state_binding_notes','source_spec_differences','reference_admission'])
        for r in rows:w.writerow([r['clip_id'],r['source_sample_id'],r['contract_recovered'],r['original_outcome'],json.dumps(r['reference_labels'],ensure_ascii=False),r['source_state_sha256'],r['extraction_source'],r['extraction_source_sha256'],';'.join(r['missing']),';'.join(r['state_binding_notes']),json.dumps(r['source_spec_differences'],ensure_ascii=False),r['reference_admission']])
        (folder/'remaining50_recovery.csv').write_text('\ufeff'+s.getvalue(),encoding='utf-8')
    print(json.dumps(summary))
    for r in rows:print(r['clip_id'],r['original_outcome'],r['reference_labels'])


if __name__=='__main__':recover()
