"""Admitted fixed-window contact cohort; pending review is an interval, not zero.

Replicates are the author's frozen (prompt_variant, seed) selections. They are
not relabeled as distinct seeds, and Cartesian output pairs are not sample size.
"""
import hashlib
import json
from pathlib import Path
from workflow import final_annotation
from remote_media import validate_remote
from input_contract import matches_frozen_input

RES=Path(__file__).parent/'resources'


def mean(values):
    return sum(values)/len(values) if values else None


def observation(task, ref, primary=False):
    p=task['payload'];human=final_annotation(task)
    if primary:
        row=task['annotations'].get('primary',{})
        human=row['payload'] if row.get('submitted') else None
    if not human:return None,'human_review_pending'
    if human.get('video_sha256')!=p['video_sha256'] or human.get('protocol_sha256')!=p.get('protocol_sha256'):
        return None,'human_media_or_protocol_identity_mismatch'
    q=human.get('quality',{}).get('status');event=ref['target_event']
    expected=ref['reference_label'];horizon=ref['horizon_s']
    if p['duration_s']+1e-6<horizon:return None,'insufficient_native_horizon'
    exact=abs(p['window_s']-horizon)<1e-6
    if not exact:
        # A confirmed absence over a longer complete window implies absence in
        # this prefix. A positive occurrence or quality failure need not do so.
        if p['window_s']>horizon and q=='pass' and human.get('events',{}).get(event,{}).get('label')=='no':
            return int(expected==0),'negative_ever_event_inherited_from_longer_window'
        return None,'human_review_for_registered_window_pending'
    if q=='failure':return 0,'confirmed_generation_quality_failure'
    if q!='pass':return None,'measurability_pending'
    label=human.get('events',{}).get(event,{}).get('label')
    if label in ('yes','no'):return int(int(label=='yes')==expected),'human_binary'
    if label in ('uncertain','not_observed') and not primary:
        return 0,'final_generated_abstention_not_reference_negative'
    return None,'target_label_pending'


def calculate_scoped(tasks):
    path=RES/'reference_window_admission.json'
    if not path.exists():return {'status':'not_registered','per_model':[]}
    registry=json.loads(path.read_text(encoding='utf-8'));refs={r['clip_id']:r for r in registry['references']}
    policy=json.loads((RES/'core100_final_input_policy.json').read_text(encoding='utf-8'))
    outputs=[];models=[]
    for task in tasks:
        p=task['payload'];ref=refs.get(p['clip_id'])
        if not ref:continue
        validate_remote(p)
        submitted=p.get('source',{}).get('generation_metadata',{}).get('prompt','')
        input_ok=matches_frozen_input(p,policy)
        verified=p.get('machine',{}).get('media_verified',{})
        media_ok=(verified.get('sha256')==p['video_sha256'] and verified.get('frames')==p['frames'] and
                  abs(verified.get('fps',0)-p['fps'])<=.02 and verified.get('size')==p['remote_media']['size'])
        correct,reason=observation(task,ref);pre,pre_reason=observation(task,ref,True)
        if not input_ok:correct=None;pre=None;reason=pre_reason='final_input_pending'
        if not media_ok:correct=None;pre=None;reason=pre_reason='native_media_verification_pending'
        outputs.append(dict(task_id=task['id'],clip_id=p['clip_id'],model=p['model'],seed=p['seed'],prompt_variant=p['prompt_variant'],
            horizon_s=ref['horizon_s'],native_horizon_s=p['duration_s'],annotation_horizon_s=p['window_s'],
            native_horizon_covers=p['duration_s']+1e-6>=ref['horizon_s'],reference_label=ref['reference_label'],
            video_sha256=p['video_sha256'],native_media_verified=media_ok,input_matches=input_ok,
            final_correct=correct,final_status=reason,primary_correct=pre,primary_status=pre_reason))
    for model in sorted({t['payload']['model'] for t in tasks}):
        own=[r for r in outputs if r['model']==model];points=[]
        for clip,ref in refs.items():
            rows=[r for r in own if r['clip_id']==clip];n=len(rows)
            known=[r['final_correct'] for r in rows if r['final_correct'] is not None]
            pending=n-len(known);pre=[r['primary_correct'] for r in rows]
            points.append(dict(clip_id=clip,reference_label=ref['reference_label'],registered=n,final_known=len(known),pending=pending,
                accuracy_bounds=[sum(known)/n,(sum(known)+pending)/n] if n else None,
                final_accuracy=mean(known) if n and not pending else None,
                primary_accuracy=mean(pre) if n and all(x is not None for x in pre) else None))
        complete=bool(points) and all(p['registered'] and p['pending']==0 for p in points)
        balanced=len({p['reference_label'] for p in points})==2
        registered_points=bool(points) and all(p['registered'] for p in points)
        native_full=bool(own) and all(r['native_horizon_covers'] for r in own)
        bounds=[mean([p['accuracy_bounds'][i] for p in points]) for i in (0,1)] if balanced and registered_points else None
        pair_bounds=[points[0]['accuracy_bounds'][i]*points[1]['accuracy_bounds'][i] for i in (0,1)] if registered_points and len(points)==2 else None
        primary_complete=all(p['primary_accuracy'] is not None for p in points)
        models.append(dict(model=model,scope='T17 initial_speed can/tissue-box contact; fixed6.4s; two near points; sampled prompt/seed combinations',
            registered=len(own),reference_points=len(refs),reference_pairs=1,native_full_horizon=native_full,
            final_known=sum(p['final_known'] for p in points),pending=sum(p['pending'] for p in points),
            status='missing_registered_points' if not registered_points else 'complete' if complete else 'pending_reviews' if native_full else 'insufficient_native_horizon',
            NearAcc=mean([p['final_accuracy'] for p in points]) if complete and balanced else None,
            PairAcc=points[0]['final_accuracy']*points[1]['final_accuracy'] if complete else None,
            NearAcc_bounds=bounds if native_full else None,PairAcc_bounds=pair_bounds if native_full else None,
            primary_only_scores={'NearAcc':mean([p['primary_accuracy'] for p in points]) if primary_complete else None,
                                 'PairAcc':points[0]['primary_accuracy']*points[1]['primary_accuracy'] if primary_complete else None,
                                 'status':'preliminary_includes_disputed_records_not_final'},points=points))
    return dict(schema='admitted-fixed-window-critical-cohort-v1',reference_registry_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        reference_cases=len(refs),reference_pairs=len(registry['pairs']),horizon_s=6.4,per_model=models,outputs=outputs,
        note='All frozen outputs stay in the cohort denominator. Pending/disputed adjudications remain unknown. Bounds assume either possible binary correctness for each pending output. Primary-only scores are explicitly not final. Unsupported native horizons are coverage gaps, not fabricated zeros.')
