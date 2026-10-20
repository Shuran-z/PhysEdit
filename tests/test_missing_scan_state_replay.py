import copy
import pytest
from scripts.t09_missing_state_worker import validate_state


def case():
    config={'render':{'pre_static_frames':12},'experiment':{'template_id':'T09','parameter':{'parameter_value':1},'supported_book_names':['upper']},'dynamic_objects':[{'name':'upper'}]}
    frames=[{'frame_index':i,'objects':[]} for i in range(210)]
    for f in frames[12:]:f['contacts']=[]
    state={'experiment':copy.deepcopy(config['experiment']),'dynamic_objects':[{'name':'upper','spec':{'name':'upper'}}],'frames':frames}
    return config,state


def test_pose_only_preroll_is_not_mistaken_for_broken_physics_telemetry():
    c,s=case();s['frames'][-1]['contacts']=[{'entity_a':'upper','entity_b':'frozen_tabletop_collision_slab'}]
    result=validate_state(c,s)
    assert result['label']==1
    assert result['initial_contact_telemetry_available'] is False


def test_missing_final_contacts_remains_unknown_instead_of_false():
    c,s=case();del s['frames'][-1]['contacts']
    with pytest.raises(ValueError,match='native contact'):validate_state(c,s)


def test_early_physics_telemetry_and_exact_source_objects_are_required():
    c,s=case();c['render']['pre_static_frames']=0
    with pytest.raises(ValueError,match='initial physics'):validate_state(c,s)
    c,s=case();s['dynamic_objects'][0]['spec']['mass']=2
    with pytest.raises(ValueError,match='objects differ'):validate_state(c,s)


def test_other_scene_collects_motion_without_inventing_event_threshold():
    c,s=case();c['experiment'].update(template_id='T06',tracked_objects=['upper'])
    for f in s['frames']:f['objects']=[{'name':'upper','position':[f['frame_index']/1000,0,0],'quaternion_xyzw':[0,0,0,1]}]
    result=validate_state(c,s)
    assert result['target_event'] is None
    assert result['tracked_metrics']['upper']['max_displacement_m']==pytest.approx(.209)
