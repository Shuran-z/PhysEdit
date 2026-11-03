"""Build the author-approved T03_C02 cam02 input as a new sealed version.

Never changes old rosters, live pointers, model outputs or human annotations.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np

from physedit.core100_critical import ROOT,load,primary,sha
from physedit.core100_rebalanced import load as load_roster
from physedit.runners.media_contract import validate_video

WORK=ROOT/'review/core100_six_replacements_20261103'
OUT=ROOT/'benchmarks/core100_critical_pairs_v4_20261103'
PROTOCOL=ROOT/'benchmarks/core100_critical_protocol_v6_20261103'
VERSION='core100-critical-pairs-v4-20261103'
CID='T03_C02'


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,value):
    with Path(p).open('x',encoding='utf8')as f:json.dump(value,f,ensure_ascii=False,indent=2)


def physical_config(config):
    """Remove only camera identity/view and image output destinations."""
    value=copy.deepcopy(config);value.pop('camera_id')
    for k in ['fixed_view','save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir']:
        value['render'].pop(k)
    return value


def build():
    if OUT.exists()or PROTOCOL.exists():raise ValueError('camera_revision_exists_create_new_version')
    selected=ROOT/'catalog/prepared_core100_critical_protocol_v3.json';pointer=read(selected)
    base,path=load((selected.parent/pointer['registry']).resolve(),pointer['registry_sha256'])
    parent,manifest,tasks,_=load_roster(ROOT/'catalog/core100_critical_pairs_v3.json')
    candidate=read(WORK/'T03_CAMERA_REVIEW_CANDIDATE.json')
    cameras=read(WORK/'T03_OTHER_CAMERA_CANDIDATES.json')
    video=ROOT/candidate['video_path'];image=ROOT/candidate['condition_image']
    assert sha(video)==candidate['video_sha256']and sha(image)==candidate['condition_sha256']
    configs={name:read(WORK/'t03_camera_candidates'/(name+'_source_config.json'))for name in ['cam02','cam03']}
    for name in configs:
        assert sha(WORK/'t03_camera_candidates'/(name+'_source_config.json'))==next(c['config_sha256']for c in cameras if c['camera']==name)
    assert physical_config(configs['cam02'])==physical_config(configs['cam03'])
    assert configs['cam02']['camera_id']=='cam02'and configs['cam03']['camera_id']=='cam03'
    old=next(c for c in base['cases']if c['clip_id']==CID);unit=primary(old)
    assert candidate['event']==unit['event']and candidate['observed_stage_label']==unit['label']==1
    assert old['condition_frame_index']==candidate['condition_frame']==4
    media=validate_video(video,fps=30,frames=210,width=854,height=480)
    cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_POS_FRAMES,4);ok,frame=cap.read();cap.release()
    condition=cv2.imdecode(np.frombuffer(image.read_bytes(),dtype=np.uint8),cv2.IMREAD_COLOR)
    assert ok and np.array_equal(frame,condition),'condition_not_exact_native_frame4'
    protected={name:sha(ROOT/name)for name in ['catalog/active_core100_conditions.json','catalog/active_core100_critical_protocol.json',
        'catalog/prepared_core100_critical_protocol_v3.json','catalog/core100_critical_pairs_v3.json']}
    OUT.mkdir();(OUT/'assets').mkdir();(OUT/'references').mkdir();(OUT/'evidence').mkdir();PROTOCOL.mkdir()
    local_video=OUT/'references/T03_C02_cam02.mp4';shutil.copyfile(video,local_video)
    local_image=OUT/'assets'/('T03_C02_'+sha(image)[:12]+'.png');shutil.copyfile(image,local_image)
    for name in ['cam02','cam03']:
        shutil.copyfile(WORK/'t03_camera_candidates'/(name+'_source_config.json'),OUT/'evidence'/(name+'_source_config.json'))
    for name in ['T03_CAMERA_REVIEW_CANDIDATE.json','T03_OTHER_CAMERA_CANDIDATES.json','T03_CAMERA_CANDIDATE_RECOVERY.json','T03_C02_PRIMARY_STAGE_VISIBILITY_REVIEW.json']:
        shutil.copyfile(WORK/name,OUT/'evidence'/name)
    approval=dict(date='2026-11-03',source='explicit_user_reply',question_item_id='call_73469455023e4f7094cb54d4db79be53',
        user_reply='换成cam02，补齐100条参考',clip_id=CID,old_camera='cam03',new_camera='cam02',
        old_inputs_outputs_labels_retained=True,new_input_requires_independent_generation_and_annotation=True)
    write(OUT/'evidence/AUTHOR_APPROVAL.json',approval)
    visual=dict(clip_id=CID,reference_video_sha256=sha(local_video),status='observable_for_registered_target',label=1,
        event=unit['event'],evidence_frames=candidate['visual_evidence_frames'],
        reviewer='assistant_visual_reference_review_20261103',independent_human_gold=False,
        definition_scope='Can contacts the original phone, then that phone passes the support edge and begins descending. No floor impact required.')
    write(OUT/'evidence/VISUAL_REVIEW.json',visual)
    proof=dict(clip_id=CID,previous_video_sha256=old['reference_video_sha256'],new_video_sha256=sha(local_video),
        previous_camera='cam03',new_camera='cam02',source_video_path=next(c['video']for c in cameras if c['camera']=='cam02'),
        source_config_sha256=sha(OUT/'evidence/cam02_source_config.json'),
        old_config_sha256=sha(OUT/'evidence/cam03_source_config.json'),
        physical_config_sha256=hashlib.sha256(json.dumps(physical_config(configs['cam02']),sort_keys=True).encode()).hexdigest(),
        physical_objects_solver_seed_controls_equal=True,physical_state_source_unchanged=old['reference_native_state_binding'],
        separate_cam02_native_state_file_claimed=False,
        same_physical_configuration_identity_not_new_trajectory_convergence_validation=True,
        source_media=media,condition_frame_index=4,condition_sha256=sha(local_image),
        horizon_s=old['horizon_s'],physical_parameters_or_prompt_changed=False,
        prior_generated_labels_or_inversion_calibration_transferred=False)
    write(OUT/'evidence/CAMERA_BINDING.json',proof)
    new_reference=dict(local_path=local_video.relative_to(ROOT).as_posix(),sha256=sha(local_video),
        publication_status='prepared_local_recovered_reference_not_newly_published',
        source_host='p25',source_video_path=proof['source_video_path'],camera_id='cam02')
    updated=copy.deepcopy(tasks);task=next(t for t in updated if t['clip_id']==CID)
    old_task=copy.deepcopy(task)
    for key in ['source_repo','source_revision','source_video_path','header_provenance']:
        task.pop(key,None)
    task.update(reference=new_reference,source_video_sha256=sha(local_video),camera_id='cam02',
        condition_image=local_image.relative_to(ROOT).as_posix(),condition_sha256=sha(local_image),condition_frame_index=4,
        source_width=854,source_height=480,evaluation_duration_s=old['horizon_s'],reference_release_version=VERSION,
        camera_source_binding='evidence/CAMERA_BINDING.json',new_generation_required=True,new_annotation_required=True,
        legacy_generated_outputs_reusable=False,legacy_annotations_reusable=False,
        legacy_inversion_calibration_reusable=False)
    assert all(a==b for a,b in zip(tasks,updated)if a['clip_id']!=CID)
    assert task['prompt_variants_en']==old_task['prompt_variants_en']
    write(OUT/'known_conditions.json',dict(version=VERSION,parent_version=manifest['version'],tasks=updated))
    write(OUT/'previous_camera_input.json',old_task)
    write(OUT/'replacement_map.json',[dict(clip_id=CID,kind='camera_only',old_camera='cam03',new_camera='cam02',
        old_sample_id=old_task['sample_id'],new_sample_id=task['sample_id'],old_reference_sha256=old['reference_video_sha256'],
        new_reference_sha256=sha(local_video),physical_parameters_changed=False,prompt_changed=False,old_results_reusable=False)])
    pending=sorted(set(manifest['model_generation_and_annotation_pending']+[CID]))
    write(OUT/'MANIFEST.json',dict(schema='core100-rebalanced-roster-v3',version=VERSION,registered_cases=100,
        retained=99,replaced=1,scene_counts={f'T{i:02}':5 for i in range(1,21)},
        parent_manifest=dict(path=(parent/'MANIFEST.json').relative_to(ROOT).as_posix(),sha256=sha(parent/'MANIFEST.json')),
        newly_replaced_generation_and_annotation_pending=[CID],inherited_generation_and_annotation_pending=manifest['model_generation_and_annotation_pending'],
        model_generation_and_annotation_pending=pending,legacy_tasks_outputs_annotations_modified=False,training_split_modified=False,
        release_status='prepared; original live tasks unchanged',
        files={p.relative_to(OUT).as_posix():sha(p)for p in OUT.rglob('*')if p.is_file()}))
    roster_pointer=ROOT/'catalog/core100_critical_pairs_v4.json'
    write(roster_pointer,dict(version=VERSION,release_root='../'+OUT.relative_to(ROOT).as_posix(),manifest='MANIFEST.json',
        manifest_sha256=sha(OUT/'MANIFEST.json'),status='prepared_not_live'))
    result=copy.deepcopy(base);result.update(version=PROTOCOL.name,roster_release=VERSION,
        roster_pointer=dict(path=roster_pointer.relative_to(ROOT).as_posix(),sha256=sha(roster_pointer)),
        camera_revision_parent=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path)))
    row=next(r for r in result['cases']if r['clip_id']==CID)
    row['reference_video_sha256']=sha(local_video);row['reference_release_version']=VERSION
    row.update(rgb_reference_status='author_approved_camera_source_bound_visual_review',rgb_pending_reason=None,
        reference_visual_review=visual,camera_revision=proof,camera_id='cam02',old_outputs_or_labels_transferred=False)
    row['admitted_rgb_events']=list(dict.fromkeys(row['admitted_rgb_events']+[unit['event']]))
    current=primary(row);current['rgb_distance_admitted']=True;current['rgb_blockers']=[]
    current['reference_id']=hashlib.sha256(json.dumps(dict(previous=unit['reference_id'],video=sha(local_video),
        condition=sha(local_image),event=current['event'],horizon_s=row['horizon_s']),sort_keys=True).encode()).hexdigest()
    row['reference_native_state_binding']=dict(row['reference_native_state_binding'],reference_video_sha256=sha(local_video),
        prior_camera_reference_video_sha256=old['reference_video_sha256'],
        camera_binding_evidence='evidence/CAMERA_BINDING.json',
        scope='Original physical-state source retained after camera-only config comparison and cam02 RGB event review; no separate cam02 native-state recording claimed.')
    binding=next(r for r in result['input_bindings']if r['clip_id']==CID)
    binding.update(reference_video_sha256=sha(local_video),condition_image=task['condition_image'],condition_sha256=sha(local_image))
    summary=result['summary']
    for prefix in ['critical_rgb_distance','reference_rgb_target','primary_rgb_event']:
        if prefix=='critical_rgb_distance':summary[prefix+'_cases']=100
        elif prefix=='reference_rgb_target':summary[prefix+'_admitted']=100
        else:summary[prefix+'_cases']=100
        summary[prefix+'_pending']=[]
    assert summary['admitted_near_cases']==14
    result['author_approved_camera_revision']=dict(clip_id=CID,camera='cam02',previous_camera='cam03',
        source_physics_prompt_window_and_interval_unchanged=True,new_output_and_annotation_required=True)
    for p in OUT.rglob('*'):
        if p.is_file():result['source_hashes'][p.relative_to(ROOT).as_posix()]=sha(p)
    result['source_hashes'][Path(__file__).resolve().relative_to(ROOT).as_posix()]=sha(__file__)
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    registry=PROTOCOL/('registry_'+digest[:12]+'.json');registry.write_bytes(raw)
    load(registry,digest)
    write(ROOT/'catalog/prepared_core100_critical_protocol_v4.json',dict(version=PROTOCOL.name,
        registry='../'+registry.relative_to(ROOT).as_posix(),registry_sha256=digest,status='prepared_not_live',
        roster_pointer=roster_pointer.relative_to(ROOT).as_posix()))
    assert all(sha(ROOT/name)==h for name,h in protected.items())
    print(json.dumps(dict(roster=VERSION,registry=registry.relative_to(ROOT).as_posix(),registry_sha256=digest,
        numerical=100,rgb=100,near=14,pending=[],new_generation_pending=len(pending),protected=protected)))


if __name__=='__main__':build()
