"""Annotation validation, independent review routing and conservative measurement."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path

LABELS = {'yes', 'no', 'uncertain', 'not_observed', 'not_applicable'}
FAILURES = {'fusion', 'identity_loss', 'disintegration', 'severe_corruption', 'new_object_intrusion', 'scene_replacement'}
SINGLE_REVIEW_POLICY = 'vlm_human_dispute_only_v2'


def dispute_reasons(p, task):
    reasons=[]
    if p.get('request_second_review'):reasons.append('人工申请抽样二审')
    q=p.get('quality',{});status=q.get('status')
    if status=='uncertain':reasons.append('人工可测性待定')
    for name,e in p.get('events',{}).items():
        if e.get('label') in ('uncertain','not_observed'):reasons.append('事件待定：'+name)
    route=machine_route({'payload':task})
    if route=='pass' and status=='failure' or route=='auto_rejected' and status=='pass':
        reasons.append('VLM与人工可测性结论不同')
    prediction=task.get('machine',{}).get('event_prediction') or {}
    for name,e in prediction.get('events',{}).items():
        human=p.get('events',{}).get(name,{}).get('label')
        definition=task['protocol']['events'].get(name)
        if not definition or human not in ('yes','no') or e.get('label') not in ('yes','no'):continue
        from event_metrics import evidence_valid
        if evidence_valid(prediction,e,definition,task) and human!=e['label']:
            reasons.append('符合判定规则的VLM事件与人工结论不同：'+name)
    return reasons


def can_access(user, task):
    if user['role']=='admin':return True
    if task['payload'].get('annotation_hold',{}).get('active'):return False
    return user['id'] in (task['primary_id'], task['reviewer_id'])


def validate_task(t, media_root):
    for k in ['id','model','clip_id','primary_id','reviewer_id','video_sha256','media_file','protocol','window_s','fps','duration_s','prompt_variant','seed']:
        if k not in t:
            raise ValueError('任务缺字段 '+k)
    if not t['id'].replace('-','').replace('_','').isalnum():
        raise ValueError('任务ID格式错误')
    if type(t['seed']) is not int or t['seed']<0 or t['prompt_variant'] not in (1,2,3):
        raise ValueError('seed/prompt格式错误')
    if any(type(t[k]) not in (int,float) or not math.isfinite(t[k]) or t[k]<=0 for k in ['fps','window_s','duration_s']):
        raise ValueError('时间范围或帧率错误')
    if t.get('remote_media'):
        from remote_media import validate_remote
        validate_remote(t)
    else:
        root=Path(media_root).resolve()
        f=(root/t['media_file']).resolve()
        if root not in f.parents or not f.is_file() or f.suffix.lower()!='.mp4':
            raise ValueError('媒体路径无效，必须先上传到指定媒体目录')
        if hashlib.sha256(f.read_bytes()).hexdigest()!=t['video_sha256']:
            raise ValueError('实际媒体SHA256不匹配')
    p=t['protocol']
    if not p.get('version') or not p.get('target') or (not p.get('events') and p.get('critical_contract_status')!='pending_scene_specific_registration') or p.get('status') not in ('diagnostic','frozen'):
        raise ValueError('事件协议不完整')
    for e in p['events'].values():
        # Registered label-only protocols explicitly use zero timestamp entries.
        if not e.get('definition') or type(e.get('minimum_evidence_times')) is not int or e['minimum_evidence_times']<0:
            raise ValueError('事件定义/证据要求缺失')


def times_ok(values, task, minimum):
    if not isinstance(values,list):
        return False
    limit=min(task['window_s'],task['duration_s'])
    return (all(type(t) in (int,float) and math.isfinite(t) and 0<=t<=limit+.001 for t in values)
            and len(set(float(t) for t in values))>=minimum)


def validate_annotation(p, task):
    if p.get('video_sha256')!=task['video_sha256'] or p.get('protocol_version')!=task['protocol']['version']:
        raise ValueError('媒体或协议身份不匹配，请刷新任务')
    if task.get('protocol_sha256') and p.get('protocol_sha256')!=task['protocol_sha256']:
        raise ValueError('逐事件协议哈希不匹配，请刷新任务')
    q=p.get('quality',{})
    if q.get('status') not in ('pass','failure','uncertain'):raise ValueError('请填写可测性结论')
    binary=p.get('annotation_schema')=='measurability-binary-v5'
    if binary and q['status']=='failure' and q.get('failure') in (None,'','none'):
        q['failure']='not_specified'
    if q['status']=='failure' and q.get('failure') not in (FAILURES|({'not_specified'}if binary else set())):raise ValueError('不可测问题类型无效；新版表单无需填写原因，请刷新后提交')
    if q['status']=='pass' and q.get('failure') not in (None,'none'):raise ValueError('质量通过不能同时确认目标损坏')
    events=p.get('events',{})
    if not isinstance(events,dict):raise ValueError('事件格式错误')
    if q['status']!='pass':
        if events:raise ValueError('质量失败或待定时不提交事件标签')
        return
    if p.get('annotation_schema')=='label-review-v3' and p.get('window_reviewed') is not True:
        raise ValueError('请先看完整视频，并勾选已核对观察窗和末帧')
    if set(events)!=set(task['protocol']['events']):raise ValueError('请逐项选择所有登记事件的标签')
    from protocol_rules import observation_evidence_problem, derive_events
    for name, definition in task['protocol']['events'].items():
        e=events[name];label=e.get('label')
        if label not in LABELS:raise ValueError('事件 '+name+' 缺少标签')
        if label=='not_applicable' and definition.get('applicable',True):raise ValueError('不能自行排除已登记适用事件')
        if label=='no' and task['duration_s']+.001<task['window_s']:raise ValueError('视频未覆盖观察窗，不能确认未发生')
        issue=observation_evidence_problem(e,definition,task,check_measurement=False,require_actor_ids=False)
        if issue:raise ValueError(name+'：'+issue)
    auxiliary=p.get('auxiliary_events',{})
    if not isinstance(auxiliary,dict) or not set(auxiliary)<=set(task['protocol'].get('auxiliary_events',{})):raise ValueError('辅助项不在登记清单内')
    if any(not isinstance(e,dict) or e.get('label') not in LABELS for e in auxiliary.values()):raise ValueError('辅助项标签无效')
    judgements=p.get('order_judgements',{}) if p.get('annotation_schema')=='label-review-v3' else None
    if judgements is not None and (not isinstance(judgements,dict) or any(v not in ('yes','no','uncertain') for v in judgements.values())):
        raise ValueError('事件先后关系选项无效')
    derived=derive_events(events,task['protocol']['events'],judgements)
    for name,definition in task['protocol']['events'].items():
        rule=definition.get('derived_from',{})
        if judgements is not None and rule.get('order') and all(events[k].get('label')=='yes' for k in rule['all']) and name not in judgements:
            raise ValueError(name+'：请选择先后关系是否正确或不可判，无需填写时间')
        if definition.get('derived_from') and events[name].get('label')!=derived[name].get('label'):
            raise ValueError(name+'：组合事件必须按子事件和顺序选项自动计算')


def semantic_decision(p):
    return (p['quality']['status'],p['quality'].get('failure','none'),
            tuple(sorted((k,v.get('label')) for k,v in p.get('events',{}).items())))


def annotations_agree(a, b, task):
    return semantic_decision(a)==semantic_decision(b)


def final_annotation(task):
    if task['state']!='resolved':
        return None
    a=task['annotations']
    if a.get('adjudication',{}).get('submitted'):
        return a['adjudication']['payload']
    # Keep both observers' times; the primary times are used only as the recorded consensus clock.
    single=task['payload'].get('review_policy')==SINGLE_REVIEW_POLICY
    return a['primary']['payload'] if a.get('primary',{}).get('submitted') and (single or a.get('review',{}).get('submitted')) else None


def machine_route(task):
    m=task['payload'].get('machine',{})
    return m.get('quality_route','not_run')


def metrics(tasks, mode):
    c={k:0 for k in ['true_reject','false_reject','false_pass','true_pass','abstain_bad','abstain_good','not_run_bad','not_run_good']}
    resolved=pass_count=bad_count=uncertain=0
    diagnostic={'eligible_reference':0,'target_correct':0,'target_observed':0,'event_exact_correct':0,'event_exact_observed':0}
    per_model={}
    for task in tasks:
        p=final_annotation(task)
        if not p:continue
        resolved+=1;q=p['quality']['status'];model=task['payload']['model']
        per_model.setdefault(model,{'resolved':0,'pass':0,'failure':0,'uncertain':0});per_model[model]['resolved']+=1;per_model[model][q]+=1
        if q=='uncertain':uncertain+=1;continue
        bad=q=='failure';bad_count+=bad;pass_count+=not bad;r=machine_route(task)
        if r=='auto_rejected':c['true_reject' if bad else 'false_reject']+=1
        elif r=='pass':c['false_pass' if bad else 'true_pass']+=1
        elif r=='not_run':c['not_run_bad' if bad else 'not_run_good']+=1
        else:c['abstain_bad' if bad else 'abstain_good']+=1
        truth=task['payload'].get('reference',{})
        if truth.get('events'):
            diagnostic['eligible_reference']+=1
            target=truth.get('target_event');e=p.get('events',{});labels={k:(1 if v['label']=='yes' else 0 if v['label']=='no' else None) for k,v in e.items()}
            if bad:
                diagnostic['target_observed']+=1;diagnostic['event_exact_observed']+=1
            else:
                if target in labels and labels[target] is not None:
                    diagnostic['target_observed']+=1;diagnostic['target_correct']+=labels[target]==truth['events'].get(target)
                if all(labels.get(k) is not None for k in truth['events']):
                    diagnostic['event_exact_observed']+=1
                    correct=all(labels[k]==v for k,v in truth['events'].items())
                    # EventExact v3 compares event labels; temporal order is a separate observation.
                    diagnostic['event_exact_correct']+=bool(correct)
    ratio=lambda a,b:a/b if b else None
    decision_n=sum(c[k] for k in ['true_reject','false_reject','false_pass','true_pass'])
    human_n=pass_count+bad_count
    formal_ready=bool(tasks) and all(t['payload'].get('reference',{}).get('admission')=='admitted' and
                                   t['payload']['protocol']['status']=='frozen' for t in tasks)
    # Reuse the repository scorer after an explicit registered-run export; never silently invent PairAcc/NearAcc bindings.
    return {'registered':len(tasks),'resolved':resolved,'pending':len(tasks)-resolved,'human_pass':pass_count,
            'human_failure':bad_count,'human_uncertain':uncertain,'per_model':per_model,
            'pipeline':{**c,'automatic_decision_coverage':ratio(decision_n,human_n),
                        'reject_precision':ratio(c['true_reject'],c['true_reject']+c['false_reject']),
                        'recall_on_machine_decisions':ratio(c['true_reject'],c['true_reject']+c['false_pass']),
                        'all_bad_auto_capture':ratio(c['true_reject'],bad_count),
                        'false_pass_rate':ratio(c['false_pass'],c['false_pass']+c['true_pass']),
                        'conditional_accuracy':ratio(c['true_reject']+c['true_pass'],decision_n)},
            'diagnostic':diagnostic,'formal_scores':{'BalancedTargetAccuracy':None,'NearAcc':None,'IndependentPairAcc':None,'EventExact':None},
            'formal_ready':formal_ready,'mode':mode,'formal_note':('登记准入已满足；请将导出标签送入冻结评分器并提供边界/配对绑定。' if formal_ready else
              '当前为诊断批次或参考登记未准入。观察标签可导出，四项正式成绩保持N/A；待审不当成零分。')}


def csv_bytes(headers, rows):
    stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(headers)
    for row in rows:
        writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in row])
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def export_files(tasks, batch, audit):
    def jl(rows):return ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows).encode()
    manifest=[];annotations=[];reviews=[];screening=[];events=[];quality=[];machines=[];raw=[];observations=[];auxiliary=[]
    for task in tasks:
        t=task['payload'];p=final_annotation(task);manifest.append({**t,'batch_id':task['batch_id'],'state':task['state'],'version':task['version']})
        # Preserve the scorer's registered identity; synthetic QA IDs never alias real samples.
        sid=t.get('registration_sample_id',t['id']) if batch['mode']!='qa' else t['id']
        identity={'sample_id':sid,'site_task_id':t['id'],'batch_id':task['batch_id']}
        machines.append({**identity,'video_sha256':t['video_sha256'],**t.get('machine',{})})
        for stage,n in task['annotations'].items():raw.append({**identity,'stage':stage,**n})
        if not p:continue
        for name,item in p.get('auxiliary_events',{}).items():auxiliary.append({**identity,'event_id':name,**item,'scope':'auxiliary_not_scored','protocol_sha256':t.get('protocol_sha256')})
        q=p['quality'];quality.append([t['id'],t['model'],t['clip_id'],t['seed'],t['prompt_variant'],q['status'],q.get('failure'),p.get('annotation_schema','legacy'),machine_route(task),{'pass':'measurable','failure':'unmeasurable'}.get(q['status'],'unknown')])
        method='vlm_assisted_human_review' if t.get('review_policy')==SINGLE_REVIEW_POLICY else 'human_dual_review'
        observers=list(dict.fromkeys(n['user_id'] for n in task['annotations'].values() if n.get('submitted')))
        record={**identity,'video_sha256':t['video_sha256'],'reviewer':'+'.join(observers),
                'evidence':q.get('reason') or 'human_review_record:'+t['id'],'evidence_kind':'human_review_record','quality_status':'confirmed_failure' if q['status']=='failure' else q['status'],'events':{}}
        ev={};ev_times={}
        if q['status']=='pass':
            for name,e in p['events'].items():
                events.append([t['id'],name,e['label'],json.dumps(e.get('measurement'),ensure_ascii=False),json.dumps(e.get('observed_actor_ids',[])),bool(t['protocol']['events'][name].get('derived_from')),p.get('order_judgements',{}).get(name),t.get('protocol_sha256'),t['protocol']['version'],p.get('annotation_schema','legacy'),p.get('window_reviewed')])
                observations.append({**identity,'event_id':name,**e,'protocol_sha256':t.get('protocol_sha256'),'protocol_version':t['protocol']['version'],'annotation_schema':p.get('annotation_schema','legacy'),'window_reviewed':p.get('window_reviewed'),'order_judgement':p.get('order_judgements',{}).get(name),'window_s':t['window_s'],'definition':t['protocol']['events'][name]})
                if e['label'] in ('yes','no'):
                    label=1 if e['label']=='yes' else 0;ev[name]=label
                    record['events'][name]={'label':label,'evidence':e.get('reason',''),'order_judgement':p.get('order_judgements',{}).get(name)}
                    if e.get('time_s') is not None:record['events'][name]['time_s']=e['time_s'];ev_times[name]=e['time_s']
        # Unknowns remain absent/null; never coerce not_observed into zero.
        annotations.append({**identity,'video_sha256':t['video_sha256'],'events':ev,'event_times_s':ev_times,'method':method,'evidence':q.get('reason') or 'human_review_record:'+t['id'],'evidence_kind':'human_review_record','annotation_schema':p.get('annotation_schema','legacy'),'order_judgements':p.get('order_judgements',{}),'reviewer':record['reviewer']})
        if q['status']!='uncertain':reviews.append(record)
        screening.append({**identity,'video_sha256':t['video_sha256'],'status':'confirmed_failure' if q['status']=='failure' else 'pass' if q['status']=='pass' else 'suspect',
                          'reviewer':record['reviewer'],'method':method,'evidence':q.get('reason') or 'human_review_record:'+t['id'],'evidence_kind':'human_review_record',
                          'blocked_events':list(t['protocol']['events']) if q['status']=='failure' else [],'block_inversion':q['status']=='failure'})
        provenance=p.get('review_provenance',{})
        if provenance.get('kind')=='author_approved_codex_arbitration':
            # Author acceptance does not turn model review into independent human gold.
            for exported in (annotations[-1],screening[-1],record):
                exported.update(method='author_approved_codex_arbitration',
                                evidence_kind='author_approved_model_review',
                                review_provenance=provenance,
                                independent_human_gold=False)
    return {'manifest.jsonl':jl(manifest),'annotations.jsonl':jl(annotations),'reviews.jsonl':jl(reviews),'screening.jsonl':jl(screening),
            'machine_predictions.jsonl':jl(machines),'all_stage_records.jsonl':jl(raw),'audit.jsonl':jl(audit),
            'quality_audit.csv':csv_bytes(['task_id','model','clip_id','seed','prompt_variant','human_quality','failure','annotation_schema','machine_route','human_measurability'],quality),
            'auxiliary_observations.jsonl':jl(auxiliary),'auxiliary_observations.csv':csv_bytes(['task_id','event_id','label','scope'],[[r['site_task_id'],r['event_id'],r.get('label'),'auxiliary_not_scored'] for r in auxiliary]),'event_observations.jsonl':jl(observations),'events.csv':csv_bytes(['task_id','event_id','label','measurement_json','observed_actor_ids_json','derived','order_judgement','protocol_sha256','protocol_version','annotation_schema','window_reviewed'],events),
            'metrics.json':json.dumps(metrics(tasks,batch['mode']),ensure_ascii=False,indent=2).encode(),
            'batch.json':json.dumps(batch,ensure_ascii=False,indent=2).encode(),
            'README.txt':('PHY2人工复核导出。manifest含生成媒体哈希、协议、分工和参考登记，仅供管理员保管。\n'
                          'v3无需人工填写时间或理由；quality/events CSV为标签表。旧时间与理由保留在原始JSON和审计中。VLM辅助复核，仅争议抽样二审。导出method标明来源，不声称盲审金标。\n'
                          'annotations/reviews/screening仅含已解决结果；未抽中或未解决争议保留待定，草稿和争议在all_stage_records保留。\n'
                          'human_review_record是复核记录索引，不是人工撰写的视觉理由；EventExact v3按事件向量比较，顺序另列。\n'
                          '未观察到/不可判不转换为0。quality failure保留全注册分母。QA批次不进入正式数据。\n'
                          '临界评分需原冻结run及相应source/边界/配对绑定；本站不伪造NearAcc或PairAcc。\n').encode()}
