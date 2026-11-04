import copy

from physedit.t11_visual_events import ACTORS,TABLE,reference_events


def scene(positions,*,table_height=0.,contact_until=1):
    objects=[dict(name=TABLE,size=[2,2,.1],pose=dict(position=[0,0,table_height-.05],euler_xyz=[0.,0.,0.]))]
    frames=[]
    for i,p in enumerate(positions):
        frames.append(dict(frame_index=i,objects=[dict(name=a,position=[p[0],p[1],p[2]+table_height])for a in ACTORS],
            contacts=[dict(entity_a=a,entity_b=TABLE)for a in ACTORS]if i<=contact_until else[]))
    return dict(dynamic_objects=objects,frames=frames,render=dict(physics_steps_per_render_frame=1),
        scene_overrides=dict(record_contacts=True,dt=1/30))


def outcome(s):return reference_events(s,condition_frame=0,end_frame=len(s['frames'])-1)['events'][ACTORS[0]+'_edge_fall_begins']


def test_fall_onset_does_not_require_final_frame_visibility_or_floor_contact():
    s=scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.10,0,-.02]])
    event=outcome(s)
    assert event['label']==1 and event['first_frame']==2 and event['confirmed_frame']==3
    # No final-world-z <-.10 rule, and no floor actor/contact exists here.
    assert s['frames'][-1]['objects'][0]['position'][2]>-.10


def test_event_is_invariant_to_world_height_origin():
    positions=[[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.10,0,-.02]]
    assert outcome(scene(positions))==outcome(scene(positions,table_height=12.))


def test_supported_overhang_and_stationary_air_are_not_positive_falls():
    positions=[[1.05,0,-.02]]*4
    assert outcome(scene(positions,contact_until=3))['label']==0
    assert outcome(scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.05,0,-.005]]))['label']is None


def test_missing_tracks_or_contacts_are_unknown_instead_of_negative():
    s=scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.10,0,-.02]])
    s['frames'][-1]['objects']=[o for o in s['frames'][-1]['objects']if o['name']!=ACTORS[0]]
    assert outcome(s)['label']is None
    s=scene([[0,0,.02]]*4);s['scene_overrides']['record_contacts']=False
    assert outcome(s)['label']is None


def test_onset_is_not_replaced_by_final_outcome_and_tail_is_not_forced_negative():
    s=scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.1,0,-.02],[.5,0,.02]])
    assert outcome(s)['label']==1
    assert outcome(scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005]]))['label']is None


def test_contact_through_another_supported_actor_prevents_false_support_loss():
    s=scene([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.10,0,-.02]])
    for f in s['frames'][2:]:
        f['contacts']=[dict(entity_a=ACTORS[0],entity_b=ACTORS[1]),dict(entity_a=ACTORS[1],entity_b=TABLE)]
    assert outcome(s)['label']!=1


def test_side_contact_descent_is_reviewed_instead_of_forced_negative():
    s=scene([[0,0,.02],[1.02,0,-.005],[1.05,0,-.02],[1.06,0,-.04]],contact_until=3)
    assert outcome(s)['label']is None
