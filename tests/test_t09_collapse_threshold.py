import copy

import pytest

from scripts.compute_t09_collapse_threshold import measure
from scripts.t09_support_drop_boundary_worker import change, event


def config():
    return dict(experiment={'extracted_book_name':'book03','supported_book_names':['book04','book05'],'parameter':{'parameter_value':.2}},
        dynamic_objects=[dict(name='book03',size=[.2,.15,.027],collision_proxy_size=[.2,.15,.027])])


def test_height_comes_from_collision_support_and_horizontal_motion_is_not_collapse():
    c=config();metrics={n:{'initial_position':[0,0,.2],'final_position':[1,0,.1999]} for n in ['book04','book05']}
    r=measure(c,metrics)
    assert r['drop_threshold_m']==pytest.approx(.0135)
    assert r['reference_label']==0
    c['dynamic_objects'][0]['size'][2]=.1
    assert measure(c,metrics)['drop_threshold_m']==pytest.approx(.0135)


def test_coherent_upper_stack_descent_counts_without_breaking_internal_contacts():
    metrics={n:{'initial_position':[0,0,.2],'final_position':[0,0,.173]} for n in ['book04','book05']}
    r=measure(config(),metrics)
    assert r['reference_label']==1
    assert r['affected_upper_books']==['book04','book05']


def test_worker_uses_the_same_geometric_predicate():
    c=config();frame=lambda z:{'objects':[{'name':n,'position':[0,0,z]} for n in ['book04','book05']]}
    frames=[frame(.2)]+[frame(.173)]*209
    assert event(c,{'frames':frames})['label']==1
    with pytest.raises(ValueError):event(c,{'frames':frames[:10]})


def test_friction_intervention_preserves_force_and_does_not_mutate_source():
    c=config();c['dynamic_objects']=[{'name':'t09_book_03','friction':.2,'material_preset':{'friction':.2}}]
    c['runtime_forces']=[{'target':'t09_book_03','force_world':[-2.,0,0]}];original=copy.deepcopy(c)
    changed=change(c,'layer_friction',.21)
    assert changed['dynamic_objects'][0]['friction']==.21
    assert changed['runtime_forces']==c['runtime_forces']
    assert c==original
