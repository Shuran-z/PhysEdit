import copy

from scripts.measure_t13_current_release import context,measure


def test_t13_motion_drop_and_contact_are_distinct():
    tracks={name:[dict(position=[0,0,1]) for _ in range(168)] for name in ['t13_drink_box','t13_driver_book','t13_falling_book']}
    tracks['t13_drink_box'][100]['position']=[.02,0,.96]
    result=measure(tracks)
    assert result['events']['t13_drink_box_motion_ge_1cm']==1
    assert result['events']['drink_drop_ge_5cm']==0
    assert result['book_drink_contact'] is None
    assert result['support_loss'] is None


def test_t13_intervention_context_retains_background_and_other_physics():
    config=dict(dynamic_objects=[dict(name='t13_drink_box',pose=dict(position=[.4,0,1]),mass=.2)],
        scene_overrides=dict(gravity=[0,0,-9.81],raytracing=True),experiment={},render=dict(fps=24,frames=168),manifest='current_background')
    a=context(config,'drink_edge_distance',.1)
    changed=copy.deepcopy(config);changed['dynamic_objects'][0]['pose']['position'][0]=.3
    assert context(changed,'drink_edge_distance',.2)==a
    changed['manifest']='older_background'
    assert context(changed,'drink_edge_distance',.2)!=a
    changed=copy.deepcopy(config);changed['dynamic_objects'][0]['mass']=.3
    assert context(changed,'drink_edge_distance',.1)!=a
    changed=copy.deepcopy(config);changed['scene_overrides']['raytracing']=False
    assert context(changed,'drink_edge_distance',.1)==a
