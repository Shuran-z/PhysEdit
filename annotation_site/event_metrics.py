"""VLM event judgements vs human observations, with explicit evidence and coverage."""
import math
from collections import defaultdict
from workflow import final_annotation, times_ok


def binary(value):
    if value=='yes':return 1
    if value=='no':return 0
    if type(value) is int and value in (0,1):return value
    return None


def evidence_valid(prediction, item, definition, task):
    # v3 validates the decision contract. Times, free-text rationales and self-reported
    # confidence do not determine label agreement or decision eligibility.
    if (prediction.get('status')!='ok' or prediction.get('video_sha256')!=task['video_sha256']
        or binary(item.get('label')) is None or item.get('contradictions',[])!=[]):return False
    from protocol_rules import observation_evidence_problem
    if observation_evidence_problem(item,definition,task,require_actor_ids=False):return False
    if definition.get('time_semantics')=='window_end_state':
        end=min(task['window_s'],task['duration_s'])
        last=min(task.get('frames',round(task['duration_s']*task['fps'])+1)-1,int(end*task['fps']+1e-6))
        if last not in prediction.get('frame_indices',[]):return False
    return True


def counts():
    return {k:0 for k in ['registered','machine_binary','machine_valid_evidence','invalid_evidence','machine_missing',
                          'human_binary','human_unknown','quality_blocked','comparable','correct',
                          'validated_comparable','validated_correct','tp','fp','fn','tn','v_tp','v_fp','v_fn','v_tn']}


def summary(c):
    def ratio(a,b):return a/b if b else None
    result=dict(c);result['contract_qualified']=c['machine_valid_evidence']
    for prefix,out in [('', 'raw'),('v_', 'validated')]:
        tp,fp,fn,tn=[c[prefix+k] for k in ['tp','fp','fn','tn']]
        result[out]={'accuracy':ratio(tp+tn,tp+fp+fn+tn),'precision':ratio(tp,tp+fp),
                     'recall':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fp+fn),'n':tp+fp+fn+tn}
    result['human_coverage']=ratio(c['human_binary'],c['registered'])
    result['machine_evidence_coverage']=ratio(c['machine_valid_evidence'],c['registered'])
    result['comparison_coverage']=ratio(c['comparable'],c['registered'])
    return result


def aggregate(tasks, preliminary=False, derived=False, scope=None):
    events=defaultdict(counts);models=defaultdict(counts)
    for task in tasks:
        t=task['payload'];human=final_annotation(task)
        if preliminary and not human:
            primary=task['annotations'].get('primary',{})
            if primary.get('submitted'):human=primary['payload']
        prediction=t.get('machine',{}).get('event_prediction') or {}
        payload=prediction.get('events') or {}
        for event,definition in t['protocol']['events'].items():
            if bool(definition.get('derived_from'))!=derived:continue
            if scope=='formal_definition' and event not in t['protocol'].get('formal_score_event_ids',[]):continue
            if scope=='pending_protocol' and event in t['protocol'].get('formal_score_event_ids',[]):continue
            if definition.get('applicable',True) is False:continue
            item=payload.get(event) or {};mlabel=binary(item.get('label'))
            valid=evidence_valid(prediction,item,definition,t)
            delta=counts();delta['registered']=1
            delta['machine_binary']=int(mlabel is not None)
            delta['machine_valid_evidence']=int(valid)
            delta['invalid_evidence']=int(mlabel is not None and not valid)
            delta['machine_missing']=int(mlabel is None)
            quality=human.get('quality',{}).get('status') if human else None
            hlabel=binary(human.get('events',{}).get(event,{}).get('label')) if human and quality=='pass' else None
            if quality=='failure':delta['quality_blocked']=1
            elif hlabel is None:delta['human_unknown']=1
            else:
                delta['human_binary']=1
                # Raw-label agreement remains separate from evidence-qualified comparison.
                if mlabel is not None and prediction.get('video_sha256')==t['video_sha256'] and prediction.get('status')=='ok':
                    key='tp' if mlabel==1 and hlabel==1 else 'fp' if mlabel==1 else 'fn' if hlabel==1 else 'tn'
                    delta[key]=1;delta['comparable']=1;delta['correct']=int(mlabel==hlabel)
                    if valid:
                        delta['v_'+key]=1;delta['validated_comparable']=1;delta['validated_correct']=int(mlabel==hlabel)
            for c in (events[t['clip_id'][:3]+'/'+event],models[t['model']]):
                for k,v in delta.items():c[k]+=v
    total=counts()
    for c in events.values():
        for k,v in c.items():total[k]+=v
    result={'micro':summary(total),'per_event':{k:summary(v) for k,v in sorted(events.items())},
            'per_model':{k:summary(v) for k,v in sorted(models.items())}}
    vals=[r['raw']['accuracy'] for r in result['per_event'].values() if r['raw']['accuracy'] is not None]
    result['macro_event_accuracy']=sum(vals)/len(vals) if vals else None
    return result


def event_metrics(tasks):
    return {'schema':'vlm-event-audit-v4-original-source','review_policy':'label-review-v3','final':aggregate(tasks),'preliminary':aggregate(tasks,True),
            'derived_final':aggregate(tasks,derived=True),'original_definition_final':aggregate(tasks,scope='formal_definition'),'pending_protocol_final':aggregate(tasks,scope='pending_protocol'),
            'note':'raw=有效媒体身份和预评状态下的二分类标签一致率，不要求时间、理由或置信度；validated=另核验数值标定、对象ID、末帧采样和矛盾记录。人工可见VLM，不是独立盲审金标。',
            'selection_note':'主统计仅含源配置核对后的主观察项；辅助项和撤下阈值不计入。原评分定义与待登记观察项另外分表，不能把一致率称为正式临界成绩。final仅已解决记录；preliminary包含仍争议的初步判断。需报告覆盖率，不能外推总体准确率。'}
