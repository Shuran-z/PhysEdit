"""Seal the full-frame result, retain the exact live80 baseline, and stage resources."""
import csv,gzip,hashlib,json,sys,zipfile
from pathlib import Path
from scripts.admit_remaining20_references import extend_remaining20
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_remaining20_20261101'
BEFORE=WORK/'live_before';STAGE=WORK/'stage';STAGE.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda raw:hashlib.sha256(raw).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
old=read(BEFORE/'resources/core100_formal_cohorts.json');formal=extend_remaining20(read(BEFORE/'resources/core100_formal_cohorts.json'))
assert formal['cohorts'][:-1]==old['cohorts']and formal['summary']['formally_registered_reference_cases']==81
media=read(BEFORE/'resources/core100_additional_media_verification.json');by={r['sha256']:r for r in media['rows']}
extra=read(WORK/'T15_C04_MEDIA.json');assert len(extra['rows'])==extra['expected']==26
assert all(r['status']=='verified'for r in extra['rows'])
for row in extra['rows']:by.setdefault(row['sha256'],row)
media.update(rows=list(by.values()),expected=len(by),remaining20_additional_verification_count=26)
progress=read(BEFORE/'resources/core100_reference_observability_progress.json')
trace={x['clip_id']:x for x in read(WORK/'ARCHIVED_STATE_TRACE.json')}
for row in progress['cases']:
    cid=row['clip_id']
    if cid=='T15_C04':
        row.update(target_reference_admitted=True,target_event='laptop_contacts_phone',horizon_s=5,
            reference_pending_reason=None,source_blockers=[],distance_reference_admitted=False,
            distance_or_window_notes=['原五秒目标事件参考已接入；不继承不同原状态或求解器的边界。'],full_native_frames_reviewed=210)
    elif cid.startswith('T11'):
        reason='210帧完整核验完成；三目标在原五秒末帧154均不可见。原协议要求末态世界z判据，不能以较早可见的下落替代。原状态已恢复，当前RGB末态可观察性未通过。'
        row.update(reference_pending_reason=reason,source_blockers=[reason],full_native_frames_reviewed=210)
    elif cid in trace:
        state=trace[cid]['states'][0]
        reason='原视频及配置已按上传清单SHA核实；已找回的旧状态内部指向其他机位，尚无证据证明其与当前cam01为同一次轨迹。不能仅按文件名、相同参数或转码说明转移真值。'
        row.update(reference_pending_reason=reason,source_blockers=[reason],
            original_video_and_config_transfer_hashes_verified=True,located_state_sha256=state['sha256'],
            located_state_declared_video=state['declared_video'],source_state_binding_status='different_declared_camera_pending_original_trajectory_identity')
progress.update(formally_admitted_target_references=81,remaining_reference_cases=[r['clip_id']for r in progress['cases']if not r['target_reference_admitted']],
    remaining20_full_frame_extraction_sha256=sha((WORK/'FULL_FRAME_EXTRACTION.json').read_bytes()),
    remaining20_archived_state_trace_sha256=sha((WORK/'ARCHIVED_STATE_TRACE.json').read_bytes()),
    remaining20_backup_search_sha256=sha((WORK/'BACKUP_STATE_SEARCH.json').read_bytes()))
assert len(progress['remaining_reference_cases'])==19
files={}
for name,value in [('resources/core100_additional_media_verification.json',media),('resources/core100_reference_observability_progress.json',progress)]:
    files[name]=json.dumps(value,ensure_ascii=False,indent=2).encode()
formal['additional_media_registry_sha256']=sha(files['resources/core100_additional_media_verification.json'])
formal['reference_progress_registry_sha256']=sha(files['resources/core100_reference_observability_progress.json'])
files['resources/core100_formal_cohorts.json']=json.dumps(formal,ensure_ascii=False,indent=2).encode()
sys.path.insert(0,str(ROOT/'annotation_site'))
from formal_critical_cohorts import calculate
tasks=json.loads(gzip.decompress((WORK/'TASKS.json.gz').read_bytes()))
prior=read(ROOT/'review/core100_remaining74_admission_20261101/LIVE_FORMAL.json')
stub={'admitted_cohort':{'outputs':prior['cohorts'][0]['outputs']}}
policy=read(ROOT/'annotation_site/resources/core100_final_input_policy.json')
oldmedia={r['sha256']:r for r in read(BEFORE/'resources/core100_additional_media_verification.json')['rows']}
before=calculate(old,stub,tasks,policy,oldmedia);after=calculate(formal,stub,tasks,policy,by)
index={c['cohort_id']:c for c in after['cohorts']}
assert all(index[c['cohort_id']]==c for c in before['cohorts'])
write(WORK/'CALCULATED_FORMAL.json',after)
new=index['t15_c04-original-observable']
write(WORK/'T15_C04_RESULTS.json',new)
with (WORK/'SCENE_MODEL_RESULTS.csv').open('w',encoding='utf-8-sig',newline='')as f:
    writer=csv.DictWriter(f,fieldnames=list(after['per_scene_model'][0]));writer.writeheader();writer.writerows(after['per_scene_model'])
spec=dict(schema='core100-remaining20-original-admission-v1',formal_summary=formal['summary'],
    registry_summary=read(BEFORE/'resources/active_distance_join_manifest.json')['registry_summary'],files=[])
for name,raw in files.items():
    p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    spec['files'].append(dict(target=name,before_sha256=sha((BEFORE/name).read_bytes()),after_sha256=sha(raw)))
write(STAGE/'DEPLOY_INPUT.json',spec)
with zipfile.ZipFile(WORK/'overlay.zip','w',zipfile.ZIP_DEFLATED)as z:
    for name in files:z.write(STAGE/name,name)
    z.write(STAGE/'DEPLOY_INPUT.json','DEPLOY_INPUT.json')
# These resources belong to this admission workflow. The numerical-axis registry is not changed.
for name,raw in files.items():(ROOT/'annotation_site'/name).write_bytes(raw)
print(json.dumps(dict(summary=formal['summary'],old_cohorts_preserved=len(before['cohorts']),
    new_scored=sum(r['final_correct']is not None for r in new['outputs']),new_correct=sum(r['final_correct']or 0 for r in new['outputs']),
    per_model=[{k:m[k]for k in('model','known','matching_registered','TargetAccuracy')}for m in new['per_model']]),ensure_ascii=True))
