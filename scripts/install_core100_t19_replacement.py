"""Install five reviewed Isaac references as a new Core100 version; retain v6."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'review/core100_t19_replacement_20261031'
VERSION = 'core100-t19-isaac-v1-20261031'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def context(config):
    objects = copy.deepcopy(config['objects'])
    for obj in objects:
        if obj['name']=='t19_striker':
            obj['pose']['position'][1] = 0.
    return dict(objects=objects,physics=config['physics'],gravity=config['gravity'],
                background_id=config['background_id'],camera=config['cameras']['cam01'],
                runtime_forces=config['source'].get('runtime_forces',[]))


def label(qa):
    pair = 't19_striker|t19_target'
    result = int(pair in qa.get('first_contacts_s',{}))
    assert result == int(qa['depth']>=2)
    return result


def main():
    import cv2
    from physedit.boundary import distance
    out = ROOT/'benchmarks/core100_t19_isaac_v1_20261031'
    if (out/'MANIFEST.json').exists():
        raise RuntimeError('Release already sealed; create a new version instead of overwriting it')
    out.mkdir(parents=True,exist_ok=True)
    source = json.loads((WORK/'source_selection.json').read_text(encoding='utf8'))
    recovered = json.loads((WORK/'bundle/source_receipt.json').read_text(encoding='utf8'))
    receipt = {r['clip_id']:r for r in recovered['cases']}
    base_path = ROOT/'review/core100_admission_20261023/v6_known_conditions.json'
    base = json.loads(base_path.read_text(encoding='utf8'))
    baseline = copy.deepcopy(base)
    policy_path = ROOT/'annotation_site/resources/core100_final_input_policy.json'
    old_policy = json.loads(policy_path.read_text(encoding='utf8'))
    old_assignments_path = ROOT.parent/'core100_author_audit_20261021/correction_v2/imported_core100_final/assignments.jsonl'
    assignments = [json.loads(s) for s in old_assignments_path.read_text(encoding='utf8').splitlines()]
    old_answers = json.loads((ROOT/'annotation_site/resources/core100_admission.json').read_text(encoding='utf8'))
    write(out/'previous_t19.json',dict(conditions=[r for r in base['tasks'] if r['clip_id'].startswith('T19')],
        assignments=[r for r in assignments if r['clip_id'].startswith('T19')],
        admission=[r for r in old_answers['points'] if r['clip_id'].startswith('T19')],
        policy={cid:p for cid,p in old_policy['tasks'].items() if cid.startswith('T19')},
        original_condition_file_sha256=sha(base_path),original_input_policy_sha256=sha(policy_path)))
    results, answers, replacement_conditions, protocols = [], [], {}, {}
    for item in source['cases']:
        cid, sid, video = item['clip_id'], item['native_sample_id'], item['video']
        src = WORK/'bundle'/cid; dest = out/'references'/cid
        shutil.copytree(src,dest,dirs_exist_ok=True)
        config = json.loads((dest/'config.json').read_text(encoding='utf8'))
        qa = json.loads((dest/'qa.json').read_text(encoding='utf8'))
        assert sha(dest/'reference.mp4')==video['sha256']
        assert sha(dest/'config.json')==receipt[cid]['config_sha256']
        assert qa['status']=='PASS' and config['sample_id']==sid
        # The fresh generation starts at frame zero; no inherited held prefix,
        # and its horizon covers the entire original boundary observation.
        cap = cv2.VideoCapture(str(dest/'reference.mp4'));ok, frame = cap.read();cap.release();assert ok
        cv2.imwrite(str(dest/'condition.png'),frame)
        event = label(qa); theta = config['parameter']['value']; ctx = context(config)
        ctx_hash = hashlib.sha256(json.dumps(ctx,sort_keys=True).encode()).hexdigest()
        proof = item['boundary_source']; bracket = proof['boundary']['bracket']
        provenance = dict(kind='recovered_original_solver_interval',
                          source_sha256=proof['boundary']['source_sha256'],
                          original_production_config_sha256=proof['config_sha256'])
        if cid=='T19_C05':
            # Contact is a band in eccentricity, not a globally monotone event.
            # Recover the *right* edge for the retained positive-y miss. Never
            # attach the far-away left edge merely because it was searched first.
            points = sorted([r for r in recovered['global_outcomes'] if context(r['config'])==ctx],
                            key=lambda r:r['config']['parameter']['value'])
            flips = [(a,b) for a,b in zip(points,points[1:]) if label(a['qa'])!=label(b['qa'])]
            left,right = min(flips,key=lambda pair:min(abs(theta-pair[0]['config']['parameter']['value']),abs(theta-pair[1]['config']['parameter']['value'])))
            bracket = [left['config']['parameter']['value'],right['config']['parameter']['value']]
            provenance = dict(kind='same_context_released_sample_transition_interval',
                uniqueness_claim=False,no_new_simulation=True,
                endpoints=[dict(sample_id=p['sample_id'],theta=p['config']['parameter']['value'],
                    label=label(p['qa']),config_sha256=p['config_sha256'],qa_sha256=p['qa_sha256']) for p in [left,right]],
                source_receipt_sha256=sha(WORK/'bundle/source_receipt.json'))
        boundary = dict(status='verified',bracket=bracket,normalization_span=.28,
                        normalization_domain=[-.14,.14],source='source_evidence.json',
                        scope=provenance['kind'],exact_threshold_claim=False)
        pair_id = 't19_bg01_moon_d2' if cid in ['T19_C01','T19_C02'] else 't19_bg03_moon_d2' if cid in ['T19_C03','T19_C04'] else None
        key = dict(sample_id=cid,point_id=cid,scene_id='T19',source_group_id=ctx_hash,
            family_id='impact_eccentricity_contact',theta=theta,parameter_name='impact_eccentricity',parameter_unit='m',
            target_event='striker_target_contact',events=dict(source_motion=1,striker_target_contact=event),
            required_order=[['source_motion','striker_target_contact']],
            reference_event_times_s=dict(source_motion=0.,**({'striker_target_contact':qa['first_contacts_s']['t19_striker|t19_target']} if event else {})),
            evaluation_horizon_s=209/30.,boundary=boundary,pair_ids=[pair_id] if pair_id else [],
            pairing_mode='independent',inversion=dict(status='not_applicable',reason='Supported tabletop collision has no registered ballistic gravity-fit window; retain in event denominator.'),
            reference_admission=dict(status='admitted',basis='author-approved reference selection; exact source config; original native contact QA; full decode and dense RGB identity review',
                limits='Contact labels come from native metadata. Generated grazing-contact labels may require tracking/manual review; no complete physics certification is claimed.'),
            reference_video_sha256=video['sha256'],condition_sha256=sha(dest/'condition.png'),
            source_config_sha256=sha(dest/'config.json'),source_qa_sha256=sha(dest/'qa.json'),
            boundary_provenance=provenance,reference_release_version=VERSION)
        d=distance(key);answers.append(key)
        condition = dict(clip_id=cid,sample_id=sid,source_video_sha256=video['sha256'],
            source_repo=video['download']['repo_id'],source_revision=video['download']['revision'],
            source_video_path=video['download']['path'],configuration_status='hash_bound_isaac_source_config',
            verified_parameter_truth=dict(gravity=abs(config['gravity'][2]),impact_eccentricity=theta),
            clock=dict(status='verified',physical_dt_s=1/30.,media_fps=30,release_frame=0,frame_count=210,
                       source='Isaac producer media and physics clock, no resampling',physics=config['physics']),
            reference=dict(**video['download'],sha256=video['sha256'],media_fps=30,frames=210),
            prompt_en=video['prompt_variants_en'][0],prompt_variants_en=video['prompt_variants_en'],
            prompt_variant_sha256=video['prompt_variant_sha256'],prompt_policy='compact-three-variants-isaac-t19-reference-replacement-v1',
            prompt_generation_facts=video['parameter_facts'],parameter_facts=video['parameter_facts'],
            prompt_language='en',default_variant=1,external_control_disclosure=video.get('external_control_disclosure'),
            external_control_inputs=video.get('external_control_inputs'),reference_release_version=VERSION)
        replacement_conditions[cid]=condition
        results.append(dict(clip_id=cid,native_sample_id=sid,video_sha256=video['sha256'],
            condition_sha256=sha(dest/'condition.png'),condition_frame_index=0,
            reference_video=f'references/{cid}/reference.mp4',condition_image=f'references/{cid}/condition.png',
            width=receipt[cid]['width'],height=receipt[cid]['height'],engine='isaac',
            uses_updated_media=bool(video.get('media_version_update')),distance=d,
            target_label=event,theta=theta,background=config['background_id'],
            new_generation_required=True,legacy_generated_outputs_reusable=False))
        protocols[cid]=dict(version=VERSION+'-'+cid,status='frozen',actors=['t19_striker','t19_target'],
            formal_score_event_ids=['source_motion','striker_target_contact'],required_order=key['required_order'],
            condition_frame_index=0,end_frame_index=209,horizon_s=209/30.,
            events=dict(source_motion=dict(definition='Striker exhibits physical motion in the observation window.'),
                        striker_target_contact=dict(definition='At least one physical contact between the striker can and tissue-box target in the full window. Projection overlap alone is insufficient.',time_semantics='ever')),
            reference_video_sha256=video['sha256'],target_truth_source='original_isaac_native_contact_qa',
            uncertainty_policy='Generated identity failure remains in denominator; uncertain grazing contact is referred for manual review.')
    base['tasks']=[replacement_conditions.get(r['clip_id'],r) for r in base['tasks']]
    base.update(version=VERSION,parent_release='frozen_v6',changed_cases=sorted(replacement_conditions))
    for old,new in zip(baseline['tasks'],base['tasks']):
        if not old['clip_id'].startswith('T19'):
            assert old==new
            assert new['prompt_variant_sha256']==old_policy['tasks'][new['clip_id']]['prompt_variant_sha256']
    by_condition={r['clip_id']:r for r in base['tasks']}
    for row in assignments:
        cid=row['clip_id'];row['known_conditions']=by_condition[cid];row['conditions_version']=VERSION
        if cid not in replacement_conditions:
            continue
        c=by_condition[cid];record=next(r for r in results if r['clip_id']==cid)
        row.update(sample_id=c['sample_id'],camera='cam01',sha256=c['source_video_sha256'],
                   source_repo=c['source_repo'],source_revision=c['source_revision'],source_video_path=c['source_video_path'],
                   source_class='Isaac_source_replacement',leakage_group_id=next(k['source_group_id']for k in answers if k['point_id']==cid),
                   background=record['background'],parameters=dict(gravity_mps2=c['verified_parameter_truth']['gravity'],impact_eccentricity_m=record['theta']),
                   reference_release_version=VERSION,observed_result=record['target_label'],
                   scientific_admission='event_reference_admitted',membership='fixed_core100_t19_replacement_v1',
                   original_source_kind='hash_bound_author_approved_replacement',
                   limitations='Native contact truth is bound; fresh generated video and event annotation are required.')
    write(out/'known_conditions.json',base);write(out/'event_protocols.json',protocols)
    write(out/'source_evidence.json',dict(selection=source,original_receipt=recovered))
    for name,rows in [('assignments.jsonl',assignments),('answers_t19.jsonl',answers)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in rows),encoding='utf8')
    with (out/'t19_distances.csv').open('w',encoding='utf-8-sig',newline='')as f:
        writer=csv.writer(f);writer.writerow(['clip_id','theta_m','boundary_low_m','boundary_high_m','normalized_distance_low','normalized_distance_high','bin','label'])
        for key in answers:
            d=distance(key);writer.writerow([key['point_id'],key['theta'],*key['boundary']['bracket'],*d['normalized_absolute_interval'],d['bin'],key['events'][key['target_event']]])
    # Every local input, proof and video is frozen before selecting it as active.
    files={p.relative_to(out).as_posix():sha(p)for p in sorted(out.rglob('*'))if p.is_file()}
    manifest=dict(schema='core100-reference-release-v1',version=VERSION,registered_cases=100,
        replacements=results,unchanged_cases=95,files=files,
        pairs=[dict(pair_id='t19_bg01_moon_d2',clips=['T19_C01','T19_C02']),dict(pair_id='t19_bg03_moon_d2',clips=['T19_C03','T19_C04'])],
        legacy_inputs_and_annotations_modified=False,source_train_split_modified=False,
        event_truth='native Isaac source contact metadata; generated-video labels are separate',
        new_model_scores_present=False)
    write(out/'MANIFEST.json',manifest)
    pointer=dict(version=VERSION,release_root='../benchmarks/'+out.name,manifest='MANIFEST.json',
                 manifest_sha256=sha(out/'MANIFEST.json'),known_conditions='../benchmarks/'+out.name+'/known_conditions.json',
                 activation='author_requested_five_T19_reference_replacement',legacy_prompt_revision=old_policy['v6_revision'])
    write(ROOT/'catalog/active_core100_conditions.json',pointer)
    # Website reads the same immutable release; no old tasks are edited.
    site_pointer=dict(pointer,release_root='../../benchmarks/'+out.name)
    write(ROOT/'annotation_site/resources/active_reference_release.json',site_pointer)
    print(json.dumps(dict(version=VERSION,replaced=5,unchanged=95,near=sum(distance(k)['bin']=='near'for k in answers),pairs=2,root=str(out)),ensure_ascii=False))


if __name__=='__main__':
    main()
