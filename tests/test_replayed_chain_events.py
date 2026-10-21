import copy
import pytest
from scripts.register_t06_t10_replay_distances import replay_events,context


def test_t06_propagation_counts_contacts_across_time_not_only_final_frame():
    exp=dict(template_id='T06',required_contact_pairs=[['a','b'],['b','c']])
    frames=[dict(contacts=[dict(entity_a='b',entity_b='a')]),dict(contacts=[dict(entity_a='c',entity_b='b')]),dict(contacts=[])]
    labels=replay_events(exp,frames,{})['labels']
    assert labels==dict(adjacent_contact_0=1,adjacent_contact_1=1,complete_required_contact_chain=1)
    frames[1]['contacts']=[]
    assert replay_events(exp,frames,{})['labels']['complete_required_contact_chain']==0


def test_t06_missing_telemetry_is_not_a_negative_event():
    with pytest.raises(ValueError,match='telemetry'):replay_events(dict(template_id='T06',required_contact_pairs=[['a','b']]),[{}],{})


def test_t10_uses_source_threshold_and_rejects_nonfinite_measurement():
    exp=dict(template_id='T10',support_ejection_threshold_m=.03)
    assert replay_events(exp,[],{'t10_support_pen':dict(max_displacement_m=.035)})['labels']['support_pen_displacement_reaches_source_threshold']==1
    exp['support_ejection_threshold_m']=.04
    assert replay_events(exp,[],{'t10_support_pen':dict(max_displacement_m=.035)})['labels']['support_pen_displacement_reaches_source_threshold']==0
    with pytest.raises(ValueError,match='nonfinite'):replay_events(exp,[],{'t10_support_pen':dict(max_displacement_m=float('nan'))})


def test_t10_context_removes_only_speed_recipe_and_retains_mass():
    c=dict(experiment=dict(template_id='T10',support_ejection_threshold_m=.04),dynamic_objects=[dict(name='t10_tape_roll',mass=.1,motion=dict(initial_velocity=[0,1,0],initial_angular_velocity=[-2,0,0]))],runtime_forces=[],scene_overrides={},render={})
    changed=copy.deepcopy(c);changed['dynamic_objects'][0]['motion']['initial_velocity'][1]=3
    changed['dynamic_objects'][0]['motion']['initial_angular_velocity'][0]=-6
    assert context(c,'v_roll')==context(changed,'v_roll')
    changed['dynamic_objects'][0]['mass']=.2
    assert context(c,'v_roll')!=context(changed,'v_roll')
