"""Quality screening and per-event preannotation. Self confidence is not calibrated."""
from physedit.boundary_window import route_observations
import copy
import re

EVENTS=('departure','descent','landing')

def route_dual(data, frame_ids, boxes, threshold=.9):
    # Lossless format normalization only; never infer an unmentioned time or label.
    data=copy.deepcopy(data) if isinstance(data,dict) else {}
    normalization=[]
    records=[('quality',data.get('quality'))]
    events=data.get('events',{})
    if isinstance(events,dict):records.extend((k,events.get(k)) for k in EVENTS)
    for name,record in records:
        if not isinstance(record,dict) or not isinstance(record.get('evidence'),list):continue
        values=record['evidence'];converted=[]
        for value in values:
            match=re.fullmatch(r'Frame ([0-9]+):\s*.+',value) if isinstance(value,str) else None
            converted.append(int(match.group(1)) if match else value)
        if converted!=values:
            record['raw_evidence']=values;record['evidence']=converted
            normalization.append(name+': explicit Frame N strings converted to indices')
    def valid(record):
        if not isinstance(record,dict):return False
        c=record.get('confidence');e=record.get('evidence',[])
        return (type(c) in (int,float) and 0<=c<=1 and isinstance(e,list)
                and all(type(i) is int and 0<=i<len(frame_ids) for i in e)
                and len({frame_ids[i] for i in e})>=2
                and isinstance(record.get('reason'),str) and bool(record['reason'].strip()))
    if not isinstance(data,dict):data={}
    q=data.get('quality',{});q=q if isinstance(q,dict) else {};qr='review'
    if valid(q) and q['confidence']>=threshold:
        if q.get('status')=='measurable':qr='preannotated_measurable'
        elif q.get('status')=='unmeasurable' and q.get('failure') in {'identity_loss','fusion','severe_corruption'}:qr='reject_measurement'
    baseline=route_observations(data,frame_ids,boxes)
    out={'quality':dict(q,route=qr),'events':{},'retain_in_denominator':True,
         'threshold':threshold,'confidence_kind':'uncalibrated_self_report','version':'dual-v1.1',
         'format_normalization':normalization}
    for name in EVENTS:
        events=data.get('events',{});events=events if isinstance(events,dict) else {}
        raw=events.get(name,{});raw=raw if isinstance(raw,dict) else {}
        reasons=[];label=raw.get('label');derived=baseline.get(name)
        if not valid(raw):reasons.append('invalid_or_insufficient_evidence')
        elif raw['confidence']<threshold:reasons.append('low_self_confidence')
        if label not in ('yes','no','not_observed','uncertain'):reasons.append('invalid_label')
        if label in ('uncertain','not_observed'):reasons.append('unresolved_event')
        if label in ('yes','no') and derived != int(label=='yes'):reasons.append('frame_or_track_evidence_does_not_support_label')
        if valid(raw) and label=='yes':
            frames=data.get('frames',[])
            selected=[frames[i] for i in raw['evidence'] if i<len(frames) and isinstance(frames[i],dict)]
            state='ground' if name=='landing' else 'airborne'
            required=2 if name=='descent' else 1
            if sum(f.get('location')==state and f.get('identity')=='same' for f in selected)<required:
                reasons.append('cited_frames_do_not_show_required_event_state')
        if qr!='preannotated_measurable':reasons.append('quality_not_cleared')
        route='preannotated' if not reasons else 'review'
        if qr=='reject_measurement':route='blocked_quality'
        out['events'][name]=dict(raw,route=route,reasons=reasons,accepted_label=label if route=='preannotated' else None)
    return out
