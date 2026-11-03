"""Candidate T03 stage witnesses, separate from original complete C2 outcome."""
import math

VERSION='t03-observable-stage-candidate-v1'
PHONE='t03v5_lower_edge_phone'
CAN='t03v5_upper_edge_can'
SUPPORT='t03v5_lower_transfer_ramp'
EVENT='phone_edge_fall_after_can_contact'


def contract():
    return dict(version=VERSION,status='candidate_not_active',event=EVENT,
        definition='The original can contacts the original lower phone; subsequently the same phone passes the lower support edge, loses support and begins moving down. Floor impact and a 20cm displacement are separate outcomes. Contact timing is an observed prerequisite, not proof of physical causality.',
        unknown_policy='A lost identity, occlusion, leaving the image, or a clip ending at possible onset is unknown, not a negative. A supported overhang is not a fall.',
        original_complete_C2_preserved=True)


def reference_events(state,*,condition_frame=4,end_frame=154,tolerance_m=.001,min_descent_s=1/30):
    def unknown(reason):return dict(label=None,reason=reason,evidence_frames=[])
    if not 0<tolerance_m<.01 or not math.isfinite(min_descent_s)or min_descent_s<=0:
        raise ValueError('invalid_stage_measurement_tolerance')
    frames=[f for f in state['frames']if condition_frame<=f['frame_index']<=end_frame]
    if [f['frame_index']for f in frames]!=list(range(condition_frame,end_frame+1)):
        return unknown('incomplete_registered_window')
    if state.get('scene_overrides',{}).get('record_contacts')is not True:
        return unknown('contact_recording_not_attested')
    objects={o['name']:o.get('spec',o)for o in state['dynamic_objects']}
    support=objects[SUPPORT]
    if support['pose']['euler_xyz']!=[0.,0.,0.]:raise ValueError('candidate_requires_original_horizontal_lower_support')
    origin=support['pose']['position'];half=[v/2 for v in support['size']];top=origin[2]+half[2]
    dt=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame']
    if not math.isfinite(dt)or dt<=0:raise ValueError('invalid_reference_clock')
    supported_before=False;can_contact=None;run=[];onset=None;missing=False;connected_descent=False;previous_z=None;uncontacted_onset=None
    for f in frames:
        index=f['frame_index'];poses={o['name']:o for o in f['objects']}
        position=poses.get(PHONE,{}).get('position')
        if not position or not all(math.isfinite(v)for v in position):missing=True;continue
        contacts=f.get('original_exterior_contacts',f.get('contacts',[]))
        edges=[{c['entity_a'],c['entity_b']}for c in contacts]
        if {PHONE,CAN}in edges and can_contact is None:can_contact=index
        connected={SUPPORT}
        while True:
            added=set().union(*(edge for edge in edges if edge&connected))if edges else set()
            if added<=connected:break
            connected|=added
        attached=PHONE in connected
        if attached:supported_before=True
        outside=any(abs(position[i]-origin[i])>half[i]+tolerance_m for i in [0,1])
        if attached and outside and position[2]<top-tolerance_m and previous_z is not None and previous_z-position[2]>=tolerance_m:
            connected_descent=True
        previous_z=position[2]
        candidate=supported_before and outside and not attached and position[2]<top-tolerance_m
        if not candidate:run=[];uncontacted_onset=None;continue
        if run and position[2]>run[-1][1]+tolerance_m:run=[];uncontacted_onset=None
        run.append((index,position[2]))
        if (run[-1][0]-run[0][0])*dt+1e-12>=min_descent_s and run[0][1]-run[-1][1]>=tolerance_m:
            if can_contact is not None and can_contact<=run[0][0]:
                onset=onset or dict(label=1,can_phone_contact_frame=can_contact,first_frame=run[0][0],confirmed_frame=index,evidence_frames=[can_contact,run[0][0],index])
            else:uncontacted_onset=uncontacted_onset or dict(first_frame=run[0][0],confirmed_frame=index)
    if missing:return unknown('phone_track_missing')
    if onset:return dict(onset,version=VERSION,window_frames=[condition_frame,end_frame],physical_frame_period_s=dt,
                         scope='Observed contact then edge-fall onset; not complete C2 floor outcome or causal attribution.')
    if not supported_before:return unknown('initial_lower_support_not_attested')
    if run and uncontacted_onset is None:return unknown('possible_onset_at_window_end')
    if connected_descent:return unknown('descending_with_contact_connection_needs_visual_or_force_review')
    return dict(label=0,version=VERSION,window_frames=[condition_frame,end_frame],evidence_frames=[condition_frame,end_frame],
                can_phone_contact_frame=can_contact,reason='Complete reference window; no qualifying contact-then-edge-fall stage.')
