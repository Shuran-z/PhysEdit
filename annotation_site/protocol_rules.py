"""Deterministic composite events and checks for calibrated numerical observations."""
import math
import hashlib
import json


def numeric_decision(definition,measurement):
    rule=definition.get('metric_rule')
    if not rule:return None
    if not isinstance(measurement,dict):return None
    if measurement.get('unit')!=rule['unit']:return None
    if any(len(str(measurement.get(k,'')).strip())<8 for k in ('method','calibration_reference')):return None
    values=measurement.get('values',{});results=[]
    for clause in rule['clauses']:
        value=values.get(clause['quantity']) if isinstance(values,dict) else None
        threshold=clause['threshold']
        if type(value) not in (int,float) or not math.isfinite(value) or type(threshold) not in (int,float):results.append(None);continue
        op=clause['operator']
        results.append(value>=threshold if op=='>=' else value>threshold if op=='>' else value<=threshold if op=='<=' else value<threshold)
    if rule['combine']=='any':return True if True in results else False if results and all(v is False for v in results) else None
    return False if False in results else True if results and all(v is True for v in results) else None


def derive_events(events,definitions,order_judgements=None):
    out=dict(events)
    for _ in range(len(definitions)):
        changed=False
        for name,d in definitions.items():
            rule=d.get('derived_from')
            if not rule:continue
            children=[out.get(key,{}) for key in rule['all']];labels=[e.get('label') for e in children]
            if 'no' in labels:
                label='no';witnesses=[e for e in children if e.get('label')=='no']
            elif all(v=='yes' for v in labels):label='yes';witnesses=children
            else:label='uncertain';witnesses=children
            if label=='yes' and rule.get('order') and order_judgements is not None:
                label={'yes':'yes','no':'no'}.get(order_judgements.get(name),'uncertain')
            if label=='yes' and order_judgements is None:
                for a,b in rule.get('order',[]):
                    first,second=out.get(a,{}).get('time_s'),out.get(b,{}).get('time_s')
                    if type(first) not in (int,float) or type(second) not in (int,float):label='uncertain';break
                    if first>second:label='no';break
            times=sorted({t for e in witnesses for t in e.get('evidence_times_s',[]) if type(t) in (int,float) and math.isfinite(t)})
            firsts=[e.get('time_s') for e in children]
            time_s=max(firsts) if label=='yes' and firsts and all(type(t) in (int,float) for t in firsts) else None
            item={'label':label,'time_s':time_s,'evidence_times_s':times,
                  'reason':'按登记子事件逻辑与及已声明顺序自动计算：'+', '.join(rule['all']),
                  'derivation':{'method':'registered_event_conjunction','inputs':rule['all'],'order':rule.get('order',[])}}
            if any('confidence' in e for e in children):
                item['confidence']=min((e.get('confidence',0.) if type(e.get('confidence')) in (int,float) else 0.) for e in witnesses) if witnesses else 0.
                item['contradictions']=[x for e in witnesses for x in e.get('contradictions',[])]
            if out.get(name)!=item:out[name]=item;changed=True
        if not changed:break
    return out


def observation_evidence_problem(item,definition,task,check_measurement=True,require_actor_ids=True):
    """Additional evidence requirements; unknown labels never require invented measurements."""
    label=item.get('label')
    if label not in ('yes','no'):return None
    if check_measurement and has_numeric_rule(definition):
        definition_hash=hashlib.sha256(json.dumps(definition,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        records=task.get('registered_measurements',{})
        if not any(isinstance(r,dict) and r.get('status')=='verified' and r.get('video_sha256')==task['video_sha256'] and r.get('protocol_sha256')==task.get('protocol_sha256') and r.get('definition_sha256')==definition_hash and len(str(r.get('artifact_sha256','')))==64 for r in records.values()):
            return '缺原单位测量或标定登记，当前标签仅作观察记录'
    if check_measurement and definition.get('metric_rule'):
        decision=numeric_decision(definition,item.get('measurement'))
        if decision is None:return '该数值事件需测量值、单位、测量方法和标定来源；无法测量请选择不可判'
        if decision!=(label=='yes'):return '标签与所填数值及登记阈值不一致'
    if check_measurement and definition.get('component_definitions'):
        numerical={k:d for k,d in definition['component_definitions'].items() if has_numeric_rule(d)}
        measured=item.get('component_measurements',{})
        if numerical and not all(numeric_decision(d,measured.get(k)) is not None for k,d in numerical.items()):
            return '原判据包含数值测量，尚缺可核对的标定结果'
    if require_actor_ids and label=='yes' and definition.get('affected_actor_options'):
        ids=item.get('observed_actor_ids')
        if not isinstance(ids,list) or not ids or not set(ids)<=set(definition['affected_actor_options']):
            return '请从登记列表选择实际涉及的原对象实体ID'
    return None


def has_numeric_rule(definition):
    return bool(definition.get('metric_rule')) or any(has_numeric_rule(d) for d in definition.get('component_definitions',{}).values())
