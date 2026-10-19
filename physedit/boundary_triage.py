"""Compact dual-task triage. Evidence is local to each event; labels are provisional."""
import re,json

def parse_with_closing_brace_repair(raw):
    """Only recover a missing final object brace at EOF; never alter JSON values."""
    text=raw.strip()
    if text.startswith('```json') and text.endswith('```'):text=text[7:-3].strip()
    try:return json.loads(text),None
    except json.JSONDecodeError as error:
        if error.pos!=len(text):raise
        value=json.loads(text+'}')
        return value,'appended_one_missing_final_object_brace_at_eof'

def indices(values,n):
    if not isinstance(values,list):return []
    out=[]
    for value in values:
        if isinstance(value,str):
            m=re.fullmatch(r'(?:[Ff]rame\s+)?(\d+)(?::.*)?',value.strip())
            value=int(m.group(1)) if m else None
        if type(value) is not int or not 0<=value<n:return []
        out.append(value)
    return sorted(set(out))

def route(data,frame_ids,boxes,threshold=.9):
    data=data if isinstance(data,dict) else {};n=len(frame_ids)
    def record(x):
        x=x if isinstance(x,dict) else {}
        c=x.get('confidence');ev=indices(x.get('evidence'),n)
        valid=type(c) in (int,float) and 0<=c<=1 and bool(x.get('reason')) and bool(ev)
        return x,c,ev,valid
    q,c,ev,valid=record(data.get('quality'));qr='review';reasons=[]
    if valid and c>=threshold:
        if q.get('status')=='measurable':qr='preannotated_measurable'
        elif q.get('status')=='unmeasurable' and q.get('failure') in ('fusion','identity_loss','severe_corruption') and len({frame_ids[i] for i in ev})>=2:qr='reject_measurement'
    if qr=='review':reasons=['quality_uncertain_or_insufficient_evidence']
    out={'quality':dict(q,route=qr,normalized_evidence=ev,reasons=reasons),'events':{},'retain_in_denominator':True,'version':'triage-v2','threshold':threshold}
    for name in ('departure','descent','landing'):
        events=data.get('events',{});events=events if isinstance(events,dict) else {}
        x,c,ev,valid=record(events.get(name));rs=[];label=x.get('label');relation=x.get('relation')
        if not valid:rs.append('invalid_evidence_or_confidence')
        elif c<threshold:rs.append('low_confidence')
        if label not in ('yes','no','not_observed','uncertain'):rs.append('invalid_label')
        if label=='uncertain':rs.append('uncertain_event')
        if label=='not_observed':rs.append('no_binary_event_label')
        if label=='yes' and relation!=('floor_contact' if name=='landing' else 'detached'):rs.append('contact_relation_unresolved')
        if label=='no' and relation!='supported':rs.append('negative_requires_supported_window')
        if name=='descent' and label=='yes':
            b=[boxes.get(frame_ids[i]) for i in ev]
            if len(b)<2 or any(v is None for v in b) or (b[-1][1]+b[-1][3]-b[0][1]-b[0][3])/2<=3:rs.append('descent_temporal_evidence_insufficient')
        if name=='landing' and label=='yes':
            b=[boxes.get(frame_ids[i]) for i in ev]
            if len(b)<2 or any(v is None for v in b):rs.append('landing_contact_evidence_insufficient')
            elif max((v[1]+v[3])/2 for v in b)-min((v[1]+v[3])/2 for v in b)>max(12,(b[0][3]-b[0][1])*.5):rs.append('landing_motion_conflict_review_not_disproof')
        if label=='no' and len(ev)<2:rs.append('negative_temporal_evidence_insufficient')
        if label=='no':
            b=[boxes.get(f) for f in frame_ids];available=[v for v in b if v]
            if len(available)!=n:rs.append('negative_track_incomplete')
            elif available and max((v[1]+v[3])/2 for v in b)-min((v[1]+v[3])/2 for v in b)>max(12,(b[0][3]-b[0][1])*1.5):rs.append('negative_motion_conflict')
        if qr!='preannotated_measurable':rs.append('quality_not_cleared')
        routed='preannotated' if not rs else 'review'
        if label=='not_observed' and valid and c>=threshold and qr=='preannotated_measurable':routed='observation_only'
        if qr=='reject_measurement':routed='blocked_quality'
        out['events'][name]=dict(x,route=routed,reasons=rs,normalized_evidence=ev,accepted_label=label if routed=='preannotated' else None)
    return out
