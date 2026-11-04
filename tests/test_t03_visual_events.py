import copy

from physedit.t03_visual_events import PHONE,CAN,SUPPORT,reference_events


def state(positions,*,contact_frame=1,held_until=1):
    return dict(dynamic_objects=[dict(name=SUPPORT,size=[2,2,.1],pose=dict(position=[0,0,-.05],euler_xyz=[0.,0.,0.]))],
        scene_overrides=dict(record_contacts=True,dt=1/30),render=dict(physics_steps_per_render_frame=1),
        frames=[dict(frame_index=i,objects=[dict(name=PHONE,position=p)],contacts=(
            [dict(entity_a=PHONE,entity_b=SUPPORT)]if i<=held_until else[])+(
            [dict(entity_a=PHONE,entity_b=CAN)]if i==contact_frame else[]))for i,p in enumerate(positions)])


def measure(s):return reference_events(s,condition_frame=0,end_frame=len(s['frames'])-1)


def test_stage_does_not_require_invisible_floor_or_20cm_descent():
    s=state([[0,0,.02],[.9,0,.02],[1.05,0,-.005],[1.1,0,-.02]])
    r=measure(s);assert r['label']==1 and r['can_phone_contact_frame']==1 and r['first_frame']==2
    assert s['frames'][-1]['objects'][0]['position'][2]>-.20
    s=copy.deepcopy(s)
    for f in s['frames']:f['contacts']=[c for c in f['contacts']if c['entity_b']!=CAN]
    assert measure(s)['label']==0


def test_supported_overhang_missing_track_and_tail_are_distinct():
    s=state([[1.05,0,-.01]]*3,held_until=2)
    assert measure(s)['label']==0
    assert measure(state([[0,0,.02],[.9,0,.02],[1.05,0,-.01]]))['label']is None
    s['frames'][1]['objects']=[];assert measure(s)['label']is None


def test_contact_after_fall_does_not_retroactively_create_the_stage():
    s=state([[0,0,.02],[1.05,0,-.01],[1.1,0,-.02],[1.2,0,-.03]],contact_frame=3,held_until=0)
    assert measure(s)['label']==0  # A later contact cannot create an earlier onset.
    s['frames'].append(dict(frame_index=4,objects=[dict(name=PHONE,position=[1.3,0,-.04])],contacts=[]))
    assert measure(s)['label']==0
