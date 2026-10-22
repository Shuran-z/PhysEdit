import copy
from scripts.t18_table_contact_boundary_worker import table_event,change


def test_omitted_empty_contacts_require_explicit_original_recording_contract():
    import pytest
    config=dict(scene_overrides=dict(record_contacts=True),experiment=dict(supported_book_names=['upper'],surface_z=0),dynamic_objects=[dict(name='upper')])
    assert table_event(config,dict(frame_index=209))['label']==0
    config['scene_overrides']['record_contacts']=False
    with pytest.raises(ValueError,match='telemetry absent'):table_event(config,dict(frame_index=209))
from scripts.register_t18_table_contact_distances import nearest_distance
from physedit.boundary import distance


def config():
    return {'sample_id':'fixed_topology','seed':123,'experiment':{'supported_book_names':['t18_book_01'],
        'surface_z':.824,'parameter':{'parameter_name':'contact_friction','parameter_value':.4},'event_variant_id':'b2_e0'},
        'dynamic_objects':[{'name':'t18_book_00','friction':.4},{'name':'t18_book_01','friction':.4}]}


def test_contact_truth_requires_upper_book_and_table_surface_collision():
    c=config()
    base={'entity_a':'t18_book_01','entity_b':'static_geom_8','position':[0,0,.824],'penetration_m':.00001}
    assert table_event(c,{'contacts':[base]})['label']==1
    floor=copy.deepcopy(base);floor['position'][2]=0
    assert table_event(c,{'contacts':[floor]})['label']==0
    lower=copy.deepcopy(base);lower['entity_a']='t18_book_00'
    assert table_event(c,{'contacts':[lower]})['label']==0
    other=copy.deepcopy(base);other['entity_b']='t18_book_00'
    assert table_event(c,{'contacts':[other]})['label']==0
    assert table_event(c,{'contacts':[]})['label']==0


def test_friction_intervention_preserves_seed_and_topology():
    c=config();new=change(c,.7)
    assert new['seed']==123
    assert new['sample_id']==c['sample_id']
    assert new['experiment']['event_variant_id']=='b2_e0'
    assert [o['friction'] for o in new['dynamic_objects']]==[.7,.7]
    assert c==config()


def test_nearest_local_boundary_is_one_source_distance_not_two_scores():
    value=nearest_distance(.5,[{'bracket':[.48,.49]},{'bracket':[.8,.82]}],1.)
    assert value['bin']=='near'
    canonical=distance({'theta':.5,'boundary':{'status':'verified','bracket':[.48,.49],
        'normalization_span':1.,'source':'test'}})
    assert value['normalized_absolute_interval']==canonical['normalized_absolute_interval']
    assert nearest_distance(.5,[{'bracket':[.35,.4]},{'bracket':[.52,.58]}],1.)['status']=='ambiguous'
