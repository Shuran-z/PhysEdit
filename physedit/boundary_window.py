"""Experimental window-aware observations; no reference labels enter routing."""
import math


def select_frames(tracks, end, count=13):
    """Keep global coverage and densify around largest tracked motion (past only)."""
    rows=[r for r in tracks if r['frame']<=end]
    anchors={round(end*i/4) for i in range(5)}
    motion=[]
    for a,b in zip(rows,rows[1:]):
        if a.get('bbox_xyxy') and b.get('bbox_xyxy'):
            aa=a['bbox_xyxy'];bb=b['bbox_xyxy']
            motion.append((math.hypot((bb[0]+bb[2]-aa[0]-aa[2])/2,
                                     (bb[1]+bb[3]-aa[1]-aa[3])/2),b['frame']))
    peak=max(motion,default=(0,end//2))[1]
    for offset in (-12,-9,-6,-3,0,3,6,9):
        anchors.add(max(0,min(end,peak+offset)))
    for i in range(count):
        if len(anchors)>=count:break
        anchors.add(round(end*i/(count-1)))
    return sorted(anchors), {'method':'5 global anchors plus motion-peak neighborhood', 'peak_frame':peak}


def route_observations(data, frame_ids, boxes):
    """Conservative candidate labels + explicit review reasons. Not truth certification."""
    result={'route':'review','departure':None,'descent':None,'landing':None,
            'landing_observation':'uncertain','reasons':[], 'version':'window-observation-v2'}
    obs=data.get('frames',[])
    if not frame_ids or not isinstance(obs,list) or len(obs)!=len(frame_ids):
        result['reasons']=['missing_frame_observations'];return result
    if any(not isinstance(x,dict) for x in obs) or [x.get('index') for x in obs]!=list(range(len(frame_ids))):
        result['reasons']=['invalid_frame_indices'];return result
    allowed={'tabletop','airborne','ground','occluded','out_of_view','uncertain'}
    if any(x.get('location') not in allowed or x.get('identity') not in {'same','uncertain','lost'} for x in obs):
        result['reasons']=['invalid_observation_enum'];return result
    valid=[(i,x) for i,x in enumerate(obs) if x['identity']=='same']
    table=[i for i,x in valid if x['location']=='tabletop']
    air=[i for i,x in valid if x['location']=='airborne']
    ground=[i for i,x in valid if x['location']=='ground']
    uncertain=any(x['identity']!='same' or x['location']=='uncertain' for x in obs)
    if air and any(t<air[0] for t in table):result['departure']=1
    if result['departure']==1 and len(air)>=2:
        # Motion alone never establishes detachment: requires visual airborne labels.
        a,b=boxes.get(frame_ids[air[0]]),boxes.get(frame_ids[air[-1]])
        if a and b and (b[1]+b[3]-a[1]-a[3])/2>3:result['descent']=1
        else:result['reasons'].append('airborne_motion_not_verified')
    landing_issue=False
    if len(ground)>=2 and any(t<ground[0] for t in table):
        gb=[boxes.get(frame_ids[i]) for i in ground]
        if any(b is None for b in gb):landing_issue=True
        elif max((b[1]+b[3])/2 for b in gb)-min((b[1]+b[3])/2 for b in gb)>max(12,(gb[0][3]-gb[0][1])*.5):landing_issue=True
        if landing_issue:result['landing_observation']='uncertain'
        else:result['landing']=1;result['landing_observation']='observed'
    elif not ground:
        result['landing_observation']='not_observed' # never a universal negative
    if len(table)==len(obs):
        available=[boxes.get(f) for f in frame_ids];available=[b for b in available if b]
        if len(available)<len(frame_ids):result['reasons'].append('supported_claim_with_missing_track')
        elif max((b[1]+b[3])/2 for b in available)-min((b[1]+b[3])/2 for b in available)>max(12,(available[0][3]-available[0][1])*1.5):
            result['reasons'].append('supported_claim_conflicts_with_large_vertical_track_change')
        else:result['departure']=0;result['descent']=0
    if uncertain:result['reasons'].append('uncertain_identity_or_location')
    if result['descent'] is None:result['reasons'].append('insufficient_descent_or_negative_evidence')
    if result['reasons']:
        result['candidate_departure']=result['departure'];result['candidate_descent']=result['descent']
        result['departure']=None;result['descent']=None
    else:result['route']='candidate_usable'
    # A disputed landing never invalidates independently supported upstream events.
    result['event_routes']={k:('candidate_usable' if result[k] is not None else 'review') for k in ('departure','descent','landing')}
    if result['landing_observation']=='not_observed':result['event_routes']['landing']='not_observed'
    if landing_issue:
        result['route']='review';result['reasons'].append('ground_claim_conflicts_with_track_requires_contact_review')
    result['version']='window-observation-v2.1'
    return result
