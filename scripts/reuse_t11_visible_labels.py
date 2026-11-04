"""Reuse compatible final human auxiliary labels without fabricating new reviews."""
from pathlib import Path
import copy
import json
import hashlib
import sys
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'annotation_site'))
from workflow import final_annotation

CONTACTS={'driver_pencil_contact':'driver_pencil_case_contact',
          'pencil_eyeglasses_contact':'pencil_case_eyeglasses_case_contact'}
FALLS={a+'_visible_fall':a+'_leaves_table'for a in
    ('t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case')}

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()

def compatible(task,binding,event,rule):
    p=task['payload'];f=final_annotation(task)
    if not f:return None
    if f.get('protocol_sha256')!=p['protocol_sha256']or f.get('video_sha256')!=binding['video_sha256']:return None
    if p['video_sha256']!=binding['video_sha256']or p['window_s']<binding['horizon_s']:return None
    if (p['frames']-1)/p['fps']+1e-6<binding['horizon_s']:return None
    stage=next((v for v in task['annotations'].values()if isinstance(v,dict)and v.get('payload')==f),{})
    source=dict(task_id=task['id'],original_annotation_sha256=digest(task['annotations']),
        final_payload_sha256=digest(f),user_id=stage.get('user_id'),stage=stage.get('stage'),
        original_protocol_sha256=p['protocol_sha256'],video_sha256=p['video_sha256'],
        original_window_s=p['window_s'],source='frozen_original_final_annotation',
        independent_new_native_review=False,original_label_modified=False)
    q=f.get('quality',{})
    if q.get('status')=='failure':
        # A failure in a longer video might occur after the new cutoff.
        if p['window_s']!=binding['horizon_s']:return None
        source['original_quality']=q
        return dict(label=None,physical_correct=0,status='reused_final_quality_failure',source=source)
    if q.get('status')!='pass':return None
    old=CONTACTS.get(event)or FALLS.get(event)
    definition=p['protocol'].get('auxiliary_events',{}).get(old,{})
    actors=definition.get('actors',[])
    if event in CONTACTS:
        if actors!=rule['actors']or 'Proximity or pixel overlap alone is insufficient.'not in definition.get('definition',''):return None
    else:
        if actors!=rule['actors']+['@original_tabletop']or 'completely loses support/contact'not in definition.get('definition',''):return None
    label=f.get('auxiliary_events',{}).get(old,{}).get('label')
    if label not in ('yes','no'):return None
    if label=='yes'and p['window_s']!=binding['horizon_s']:return None
    if event in FALLS and label=='yes':return None  # Loss of support alone does not prove downward movement.
    source.update(old_event_id=old,original_label=label,old_definition=definition,
        mapping='same_visible_contact'if event in CONTACTS else 'no_support_loss_implies_no_visible_fall',
        window_mapping='same_window'if p['window_s']==binding['horizon_s']else 'negative_over_longer_window_implies_negative_in_five_second_prefix')
    return dict(label=label,status='compatible_final_visible_label_reused',source=source)

def main():
    r=ROOT/'review/all20_completion_20261101';w=r/'t11_execution_20261102';load=lambda p:json.loads(p.read_text(encoding='utf8'))
    snap=load(r/'existing_reuse_audit_20261102/snapshot.json');assert digest(snap['tasks'])==snap['task_sha256']
    tasks={t['id']:t for t in snap['tasks']};registry=load(r/'camera_rule_fix_20261102/t11_visible/REGISTRY.json')
    original=load(r/'camera_rule_fix_20261102/t11_visible/RESULTS.json');result=copy.deepcopy(original)
    bindings={x['id']:x for x in registry['outputs']};reference_reviews=load(w/'REFERENCE25_OBSERVATIONS.json')
    refs={(x['id'],x['event']):x['label']for x in reference_reviews};reused=[]
    verified={x['id']:x for x in load(w/'EXTRACTION_AND_TRIAGE.json')['rows']}
    for row in result['rows']:
        if row['correct']is not None:continue
        b=bindings[row['id']]
        assert verified[b['id']]['status']=='evidence_extracted'and verified[b['id']]['video_sha256']==b['video_sha256']
        value=compatible(tasks[row['id']],b,row['event'],registry['protocol']['events'][row['event']])
        reference=refs.get((row['clip_id'],row['event']))
        if value is None or reference not in ('yes','no'):continue
        row.update(correct=value.get('physical_correct',int(reference==value['label'])),
            status=value['status'],reused_label=value['label'],reuse_source=value['source'],
            native_review_added=False)
        reused.append(copy.deepcopy(row))
    result['scored_event_slots']=sum(x['correct']is not None for x in result['rows'])
    result['new_native_review_slots']=original['scored_event_slots']
    result['reused_final_annotation_slots']=len(reused)
    result['native_quality_failure_slots']=original['quality_failure_slots']
    result['reused_quality_failure_slots']=sum(x['status']=='reused_final_quality_failure'for x in reused)
    result['quality_failure_slots']=result['native_quality_failure_slots']+result['reused_quality_failure_slots']
    result['complete_outputs']=sum(all(row['correct']is not None for row in result['rows']if row['id']==b['id'])for b in registry['outputs'])
    result['reuse_scope']='Compatible original final labels retained with provenance; separate from new Codex native-frame reviews.'
    result['quality_policy']='New native foreign-actor/identity-loss reviews and exact-window final human quality-failure judgments score physical correctness 0; event labels remain null. Unspecified historical reasons are retained, not invented.'
    result['source_task_snapshot_sha256']=snap['task_sha256']
    result['per_model']={m:dict(registered=75,known=sum(x['correct']is not None for x in result['rows']if x['model']==m),
        correct=sum(x['correct']==1 for x in result['rows']if x['model']==m))for m in sorted({x['model']for x in result['rows']})}
    (w/'HISTORICAL_LABEL_REUSE.json').write_text(json.dumps(reused,ensure_ascii=False,indent=2),encoding='utf8')
    (w/'RESULTS_WITH_REUSED_LABELS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    assert digest(snap['tasks'])==snap['task_sha256']
    print(json.dumps({k:v for k,v in result.items()if k not in ('rows','per_model')}))
    print(json.dumps(result['per_model']))

if __name__=='__main__':main()
