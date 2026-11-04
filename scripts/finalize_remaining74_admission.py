"""Seal reviewed evidence and extend the exact live baseline without rewriting it."""
import copy
import hashlib
import json
from pathlib import Path
from scripts.admit_remaining74_original_references import extend_remaining

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining74_admission_20261101'
SITE=ROOT/'annotation_site/resources'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

proof=WORK/'PUBLISHED_INTERVAL_READBACK.json'
assert len(read(proof))==10 and all(r['status']=='verified_original_published_interval'for r in read(proof))
sealed=WORK/'sealed_intervals'/(sha(proof)+'.json');sealed.parent.mkdir(exist_ok=True)
if not sealed.exists():sealed.write_bytes(proof.read_bytes())
decisions=read(WORK/'ADMISSION_DECISIONS.json')
for d in decisions:
    if d['clip_id'].startswith(('T01','T04','T08'))and d['distance_admitted']:
        d['distance_evidence']=dict(file=sealed.relative_to(ROOT).as_posix(),sha256=sha(sealed))
write(WORK/'ADMISSION_DECISIONS.json',decisions)
old=read(WORK/'live_before/resources/core100_formal_cohorts.json')
registry=extend_remaining(copy.deepcopy(old))
assert len(decisions)==54 and registry['summary']['formally_registered_reference_cases']==80
assert registry['cohorts'][:len(old['cohorts'])]==old['cohorts']

media=read(WORK/'live_before/resources/core100_additional_media_verification.json')
by={r['sha256']:r for r in media['rows']}
for name in ('MODEL_MEDIA_VERIFICATION.json','T06_C04_MODEL_MEDIA.json'):
    extra=read(WORK/name)
    assert len(extra['rows'])==extra['expected'] and all(r['status']=='verified'for r in extra['rows'])
    for row in extra['rows']:by.setdefault(row['sha256'],row)
media['rows']=list(by.values());media['expected']=len(by)
media['remaining74_source_proof_counts']=dict(main=1080,T06_C04=24)
write(SITE/'core100_additional_media_verification.json',media)

progress=read(WORK/'live_before/resources/core100_reference_observability_progress.json')
refs={r['clip_id']:r for c in registry['cohorts']for r in c['references']}
for row in progress['cases']:
    cid=row['clip_id'];r=refs.get(cid)
    row['target_reference_admitted']=bool(r)
    if r:
        row['source_blockers']=[];row['reference_pending_reason']=None
        row['target_event']=r['target_event'];row['horizon_s']=r['horizon_s']
        row['distance_reference_admitted']=r.get('distance_admitted',True)
        row['distance_or_window_notes']=(['原协议的局部边界区间已核验；分桶不确定性保留。']if r.get('distance_admitted',True)
            else['原目标事件参考已接入；当前原边界身份或区间证据未准入，不生成NearAcc或PairAcc。'])
    else:
        if cid.startswith(('T06','T09')):
            reason='已找到旧原状态及视频候选，但与当前参考的原父视频SHA或解码帧不一致；尚不能证明原状态、事件与当前视频一一对应。'
        elif cid.startswith('T10'):
            reason='已检查原Isaac输出及现存来源记录，尚未找到与当前参考原父视频SHA对应的状态文件；同名候选不能继承。'
        elif cid.startswith('T11'):
            reason='原状态、五秒时钟及末帧世界坐标判据已恢复；目标在末段离开当前视野，尚缺可从当前RGB核验末态的证据。'
        elif cid=='T15_C04':
            reason='原状态和全子步接触记录已恢复，原标签为未接触；仍需核验遮挡下完整路径，不能从源状态负例直接推定RGB可观察。'
        else:raise AssertionError(cid)
        row['reference_pending_reason']=reason;row['source_blockers']=[reason]
progress['formally_admitted_target_references']=len(refs)
progress['formally_admitted_original_interval_references']=registry['summary']['formally_registered_interval_reference_cases']
progress['remaining_reference_cases']=[r['clip_id']for r in progress['cases']if not r['target_reference_admitted']]
assert len(progress['remaining_reference_cases'])==20
write(SITE/'core100_reference_observability_progress.json',progress)
registry['additional_media_registry_sha256']=sha(SITE/'core100_additional_media_verification.json')
registry['reference_progress_registry_sha256']=sha(SITE/'core100_reference_observability_progress.json')
write(SITE/'core100_formal_cohorts.json',registry)
print(json.dumps(dict(summary=registry['summary'],media_verified=len(by),remaining=progress['remaining_reference_cases'])))
