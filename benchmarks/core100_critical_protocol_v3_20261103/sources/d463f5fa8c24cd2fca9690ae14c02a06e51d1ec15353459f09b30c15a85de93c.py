"""Candidate observable T11 events; never overwrite the frozen v2 protocol.

The simulator adapter supplies reference labels. Generated-video judging uses
the separately exported visual definitions, never these reference trajectories.
"""
import math

VERSION='t11-observable-events-candidate-v1'
ACTORS=('t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case')
TABLE='t11_tabletop_collision_slab'
FLOOR='t11_floor_collision_slab'


def contract():
    events={}
    for a,b,name in [(ACTORS[0],ACTORS[1],'橡皮撞到笔盒'),(ACTORS[1],ACTORS[2],'笔盒撞到眼镜盒')]:
        events[a+'_contacts_'+b]=dict(name=name,actors=[a,b],time_semantics='ever_first_confirmed_contact',
            definition='The two named original objects physically collide within the observation window. Use contact geometry and temporally consistent motion; proximity or image overlap alone is insufficient.')
    for actor in ACTORS:
        events[actor+'_edge_fall_begins']=dict(name='指定物体越过桌缘并开始跌落',actors=[actor,TABLE],time_semantics='ever_event_transition',
            definition='The named original object initially has tabletop support, passes the tabletop edge, loses support, and is visibly moving down beside the tabletop. Assess the transition, not its location in the final frame. Continued edge support, a stable overhang, disappearance, occlusion or leaving the image alone is insufficient. Floor impact is not required.',
            positive_evidence='Identify the same object before and after support loss, the tabletop edge, and downward motion after crossing that edge.',
            negative_evidence='Observe the complete registered window with a continuous usable track; the required edge-fall transition never occurs.',
            unknown_evidence='The relevant transition is hidden, the track is lost, or the clip ends before the transition can be established.')
        events[actor+'_contacts_floor']=dict(name='指定物体接触地面',actors=[actor,FLOOR],time_semantics='ever_first_confirmed_contact',
            definition='Actual floor contact by the same named original object is visible. Falling below the tabletop or leaving the image does not establish floor contact.',role='optional_visible_extension')
    return dict(version=VERSION,status='candidate_not_active',events=events,
        primary_outcome_candidates=[a+'_edge_fall_begins'for a in ACTORS],
        initial_primary_outcome=ACTORS[0]+'_edge_fall_begins',
        causal_chain=[ACTORS[0]+'_contacts_'+ACTORS[1],ACTORS[1]+'_contacts_'+ACTORS[2]],
        causal_scope='Contact order and each object fall outcome are separate. Contacts in the expected order alone do not prove causal attribution or a complete chain.',
        uncertainty_policy='Use yes/no/unknown per event with evidence times. Occlusion is not nonoccurrence. Identity failure follows the separate quality router and stays in the overall denominator.',
        migration='New event IDs require fresh labels and event-matched boundary readback; old final-world-z labels/thresholds are never copied by name.')


def _components(edges,start):
    found={start};pending=[start]
    while pending:
        node=pending.pop()
        for edge in edges:
            if node in edge:
                for other in edge-found:found.add(other);pending.append(other)
    return found


def _unknown(reason):
    return dict(label=None,first_frame=None,evidence_frames=[],reason=reason)


def reference_events(state,*,condition_frame=4,end_frame=154,spatial_tolerance_m=.001,min_descent_duration_s=1/30):
    """Conservative reference witnesses for this scene's horizontal tabletop.

    Require prior table connection, then an unconnected actor beyond the
    footprint and below the tabletop, descending for >=1/30 physical second.
    Any contact path to the table conservatively prevents a positive witness;
    this is NOT a general load-bearing-contact or arbitrary-scene detector.
    """
    if not state.get('scene_overrides',{}).get('record_contacts'):
        return dict(version=VERSION,status='reference_measurement_missing',events={a+'_edge_fall_begins':_unknown('contact_recording_not_attested')for a in ACTORS})
    specs={o['name']:o.get('spec',o)for o in state['dynamic_objects']}
    table=specs[TABLE]
    if table['pose']['euler_xyz']!=[0.,0.,0.]:raise ValueError('t11_candidate_requires_original_horizontal_table')
    if not 0<spatial_tolerance_m<.01 or min_descent_duration_s<=0:raise ValueError('invalid_event_tolerance')
    origin=table['pose']['position'];half=[v/2 for v in table['size']];top=origin[2]+half[2]
    dt=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']
    if not math.isfinite(dt)or dt<=0:raise ValueError('invalid_reference_clock')
    frames=[f for f in state['frames']if condition_frame<=f['frame_index']<=end_frame]
    if [f['frame_index']for f in frames]!=list(range(condition_frame,end_frame+1)):
        return dict(version=VERSION,status='reference_measurement_missing',events={a+'_edge_fall_begins':_unknown('incomplete_reference_window')for a in ACTORS})
    support_seen={a:False for a in ACTORS};runs={a:[]for a in ACTORS};out={};contact_hits={};missing=set();tail_candidates=set()
    previous_height={};contact_connected_descent=set()
    for frame in frames:
        index=frame['frame_index'];poses={o['name']:o for o in frame['objects']}
        # An instrumented replay must preserve the producer's exterior contact
        # semantics; internal depth-max records are never substituted here.
        contacts=frame.get('original_exterior_contacts',frame.get('contacts',[]))
        edges=[{c['entity_a'],c['entity_b']}for c in contacts]
        table_connected=_components(edges,TABLE)
        for actor in ACTORS:
            p=poses.get(actor,{}).get('position')
            if not p or not all(math.isfinite(v)for v in p):missing.add(actor);runs[actor]=[];continue
            attached=actor in table_connected
            if attached:support_seen[actor]=True
            outside=any(abs(p[i]-origin[i])>half[i]+spatial_tolerance_m for i in [0,1])
            if attached and outside and p[2]<top-spatial_tolerance_m and previous_height.get(actor,p[2])-p[2]>=spatial_tolerance_m:
                contact_connected_descent.add(actor)
            previous_height[actor]=p[2]
            candidate=support_seen[actor]and not attached and outside and p[2]<top-spatial_tolerance_m
            if not candidate:runs[actor]=[]
            else:
                run=runs[actor]
                if run and p[2]>run[-1][1]+spatial_tolerance_m:run=[]
                run.append((index,p[2]));runs[actor]=run
                if (run[-1][0]-run[0][0])*dt+1e-12>=min_descent_duration_s and run[0][1]-run[-1][1]>=spatial_tolerance_m:
                    event=actor+'_edge_fall_begins'
                    out.setdefault(event,dict(label=1,first_frame=run[0][0],confirmed_frame=index,evidence_frames=[run[0][0],index],
                        reason='Prior table connection, no remaining table contact path, beyond tabletop footprint and sustained downward motion below the tabletop.'))
            if index==end_frame and candidate and actor+'_edge_fall_begins'not in out:tail_candidates.add(actor)
            if any({actor,FLOOR}==edge for edge in edges):contact_hits.setdefault(actor+'_contacts_floor',index)
        for a,b in zip(ACTORS,ACTORS[1:]):
            if any({a,b}==edge for edge in edges):contact_hits.setdefault(a+'_contacts_'+b,index)
    for actor in ACTORS:
        event=actor+'_edge_fall_begins'
        if actor in missing:out[event]=_unknown('actor_state_missing_in_registered_window')
        elif event not in out:
            if not support_seen[actor]:out[event]=_unknown('initial_table_support_not_attested')
            elif actor in tail_candidates:out[event]=_unknown('possible_onset_at_window_end_insufficient_temporal_evidence')
            elif actor in contact_connected_descent:out[event]=_unknown('descending_beside_table_with_contact_connection_requires_force_or_visual_review')
            else:out[event]=dict(label=0,first_frame=None,evidence_frames=[condition_frame,end_frame],reason='Complete native state window; no qualifying edge-fall transition.')
    for event,index in contact_hits.items():out[event]=dict(label=1,first_frame=index,evidence_frames=[index],reason='Original named exterior contact record.')
    for event in contract()['events']:
        if event not in out:out[event]=dict(label=0,first_frame=None,evidence_frames=[condition_frame,end_frame],reason='Complete recorded reference window; no named contact.')
    return dict(version=VERSION,status='candidate_reference_readback_not_formal_rgb_admission',events=out,
        physical_frame_period_s=dt,window_frames=[condition_frame,end_frame],spatial_tolerance_m=spatial_tolerance_m,
        min_descent_duration_s=min_descent_duration_s,
        source='simulator state and original exterior contacts; never supplied to generated-video judge',
        limitations='Conservative contact-connectivity witness for the original horizontal-table T11 scene only. Simultaneous side contacts can delay detection; this is not proof of general contact-force support or physical causality.')
