"""Supplemental human observations, separate from every frozen scoring contract."""
import collections
import hashlib
import json
from workflow import final_annotation


def definitions(p):
    if not p.get('clip_id', '').startswith('T'):
        return []
    items = []
    def add(key, name, text, contact=None):
        d = dict(id=key, version='process-observation-v1', name=name,
                 definition=text, contact_event_id=contact,
                 scope='supplemental_not_original_score')
        items.append(dict(definition=d, definition_sha256=hashlib.sha256(
            json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()))
    common = '追踪原对象并对照至少两个时刻，排除镜头运动、遮挡和物体替换；看不清选不可判。'
    if p['clip_id'].startswith('T20_'):
        for actor, name, contact, upstream in [
            ('can', '罐子', 'contact_book_can', '书本'),
            ('box', '盒子', 'contact_can_box', '罐子'),
            ('cup', '杯子', 'contact_box_cup', '盒子')]:
            add('t20_' + actor + '_translation_v1', '原' + name + '是否发生平移',
                common + '只记录是否发生可辨认的平移，不要求先接触；不设厘米阈值，不等同于末态位移。', contact)
            add('t20_' + actor + '_precontact_motion_v1', '原' + name + '是否在' + upstream + '首次接触前已平移',
                common + '确认原' + name + '在' + upstream + '首次接触前已发生平移；若完整视频中明确从未接触但发生平移，也选发生。未看清接触或先后关系选不可判。此项记录时间关系，已声明初速度、画外施力或其他接触可能解释运动，不能仅凭此项认定违反物理。', contact)
    if p['clip_id'].startswith('T17_'):
        add('t17_box_precontact_motion_v1', '原纸巾盒是否在罐子首次接触前已平移',
            common + '若明确从未接触但发生平移，也选发生；接触或先后看不清选不可判。记录时间关系，不自动等同于无因运动；须另核对初始运动和其他作用。', 'can_tissue_box_contact')
    add('original_actor_unsupported_hover_v1', '原目标物体是否出现不合理悬空',
        common + '记录可确认的持续无支撑停留或明显不合理的缓慢漂浮；正常抛掷、下落、弹跳、接触瞬间离地、短暂腾空、已声明的托举或运动控制不算。仅凭一帧或没看见支撑不能确认；月球和火星低重力下运动较慢本身不算异常。')
    add('original_actor_interpenetration_v1', '原目标物体是否出现可确认的穿模',
        common + '原目标物体穿过其他物体或支撑面，或出现明显不可能的实体内部重叠。仅像素重叠、遮挡、接触、阴影和难以辨认的微小接缝不算；不据此声称超过1毫米。')
    return items


def view(task, user):
    primary = task['annotations'].get('primary', {}).get('payload', {})
    return dict(items=[dict(item, record=task.get('independent_observations', {}).get(item['definition']['id']))
                       for item in definitions(task['payload'])],
                can_edit=user['id'] == task['primary_id'] and not task['payload'].get('annotation_hold', {}).get('active'),
                saved_quality_is_measurable=primary.get('quality', {}).get('status') == 'pass')


def rows(tasks):
    for t in tasks:
        for item in definitions(t['payload']):
            record = t.get('independent_observations', {}).get(item['definition']['id'])
            if record:
                yield dict(task_id=t['id'], batch_id=t['batch_id'], model=t['payload']['model'],
                           clip_id=t['payload']['clip_id'], **record)


def statistics(tasks, preliminary=False):
    groups = {}
    for t in tasks:
        p = t['payload']
        for item in definitions(p):
            d = item['definition']; key = (p['model'], p['clip_id'][:3], d['id'])
            entry = groups.setdefault(key, dict(model=key[0], scene=key[1], observation_id=key[2],
                name=d['name'], counts=collections.Counter(), target_cross=collections.Counter(),
                contact_cross=collections.Counter(), admitted_correctness_cross=collections.Counter()))
            c = entry['counts']; c['registered'] += 1
            if p.get('annotation_hold', {}).get('active'):
                c['held'] += 1; continue
            c['active'] += 1
            h = final_annotation(t)
            if not h and preliminary:
                a = t['annotations'].get('primary', {})
                if a.get('submitted'): h = a['payload']
            if not h:
                c['human_pending'] += 1; continue
            if h.get('quality', {}).get('status') != 'pass':
                c['quality_blocked'] += 1; continue
            c['measurable_human'] += 1
            r = t.get('independent_observations', {}).get(d['id'])
            if not r:
                c['missing'] += 1; continue
            if r.get('video_sha256') != p['video_sha256'] or r.get('definition_sha256') != item['definition_sha256']:
                c['binding_invalid'] += 1; continue
            label = r.get('label')
            if label not in ('yes', 'no'):
                c['uncertain'] += 1; continue
            c['binary'] += 1; c[label] += 1
            for event in p['protocol'].get('formal_score_event_ids', []):
                v = h.get('events', {}).get(event, {}).get('label')
                entry['target_cross'][event + ':' + str(v if v in ('yes', 'no') else 'unknown') + ':' + label] += 1
            contact = d.get('contact_event_id')
            if contact:
                v = h.get('auxiliary_events', {}).get(contact, h.get('events', {}).get(contact, {})).get('label')
                entry['contact_cross'][str(v if v in ('yes', 'no') else 'unknown') + ':' + label] += 1
            truth = p.get('reference', {})
            if truth.get('admission') == 'admitted' and truth.get('events'):
                labels = {k: h.get('events', {}).get(k, {}).get('label') for k in truth['events']}
                if all(v in ('yes', 'no') for v in labels.values()):
                    correct = all((labels[k] == 'yes') == bool(v) for k, v in truth['events'].items())
                    entry['admitted_correctness_cross'][('correct' if correct else 'incorrect') + ':' + label] += 1
    result = []
    for entry in groups.values():
        c = entry['counts']
        entry['counts'] = {k: c[k] for k in ('registered','held','active','human_pending','quality_blocked',
            'measurable_human','missing','binding_invalid','uncertain','binary','yes','no')}
        entry['yes_rate_among_binary'] = c['yes'] / c['binary'] if c['binary'] else None
        entry['binary_coverage_active'] = c['binary'] / c['active'] if c['active'] else None
        result.append(entry)
    return result


def report(tasks):
    return dict(version='process-observation-v1', final=statistics(tasks), preliminary=statistics(tasks, True),
        note='独立补充观察，不修改原协议、原标签或NearAcc/PairAcc/EventExact。按模型、场景和观察项交叉统计原目标发生标签；仅reference.admission=admitted时另列原事件向量正确性，未准入不冒充评分。target_cross键为事件:原标签:新标签；contact_cross键为接触标签:新标签。未填、不可判、不可测、待人工和暂缓分别计数；分母为二元可判数，须同时报告覆盖率。接触前运动不自动证明无其他作用。final仅已解决人工记录，preliminary另含争议初判。')
