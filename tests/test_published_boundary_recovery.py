import copy

import pytest

from scripts.bind_t03_current_parameters import context, original_label
from scripts.supplement_t12_published_boundaries import fixed_context, measure
from scripts.t12_original_boundary_worker import set_parameter
from scripts.supplement_t11_published_boundaries import context as t11_context


def test_t12_uses_maximum_excursion_even_when_target_returns():
    frames=[{'objects':[{'name':'t12_tissue_box','position':p}]} for p in [[0,0,0],[.02,0,0],[0,0,0]]]
    assert measure(frames)==pytest.approx(.02)
    with pytest.raises(ValueError):measure([])


def t12_config():
    return dict(dynamic_objects=[dict(name='t12_stapler',motion={'initial_velocity':[1.,0,0]},friction=.1),dict(name='t12_tissue_box',mass=.2)],
        scene_overrides={'gravity':[0,0,-9.8]},render={'fps':30},t12_parameters={'stapler_initial_velocity_mps':[1.,0,0],'stapler_friction':.1,'tissue_mass_kg':.2},
        experiment={'controlled_physics':{'stapler':{'initial_velocity_mps':[1.,0,0],'friction':.1},'tissue_box':{'mass_kg':.2}}})


@pytest.mark.parametrize('axis,value',[('speed',2.),('friction',.3),('target_mass',.5)])
def test_t12_intervention_keeps_fixed_context_and_other_inputs(axis,value):
    config=t12_config();changed=set_parameter(config,axis,value)
    assert fixed_context(config,axis)==fixed_context(changed,axis)
    changed['scene_overrides']['gravity'][2]=-1.62
    assert fixed_context(config,axis)!=fixed_context(changed,axis)
    assert config==t12_config()


def t03_experiment():
    return dict(parameter={'book_initial_speed_mps':1.,'upper_can_com_edge_distance_m':.1,'lower_phone_com_edge_distance_m':.2,'lower_transfer_ramp_slope_deg':0},
        geometry_contract={'upper_can_center_m':[1.,0,0],'lower_phone_center_m':[2.,0,0],'initial_can_phone_horizontal_gap_m':.3,'initial_book_can_surface_gap_m':.4},
        background_id='home',gravity_id='earth',replicate_id=1)


def test_t03_upper_edge_coordinate_normalizes_only_affine_geometry():
    original=t03_experiment();changed=copy.deepcopy(original)
    changed['parameter']['upper_can_com_edge_distance_m']+=.05
    changed['geometry_contract']['upper_can_center_m'][0]-=.05
    changed['geometry_contract']['initial_can_phone_horizontal_gap_m']+=.05
    changed['geometry_contract']['initial_book_can_surface_gap_m']-=.05
    assert context(original,'B')==context(changed,'B')
    changed['parameter']['book_initial_speed_mps']=2
    assert context(original,'B')!=context(changed,'B')


def test_t03_target_labels_distinguish_stages():
    report={'first_contact_frame':{'book_can':4},'observed_outcome':'B1_upper_can_first_fall'}
    assert original_label(report,'A')[0]==1
    assert original_label(report,'B')[0]==1
    assert original_label(report,'C')[0]==0


def test_t11_mass_recipe_keeps_other_force_changes_separate():
    config={'dynamic_objects':[{'name':'t11_relay_pencil_case','mass':.1,'material_preset':{'mass':.1}}],
        'runtime_forces':[{'target':'t11_driver_eraser','force_world_after_first_contact':[.55,0,0],'force_world_relay_phase':[.55,0,0],'force_world_after_contact':[.3,0,0]}],
        'scene_overrides':{'gravity':[0,0,-9.8]},'render':{'fps':30},'experiment':{'background_id':'home','gravity_id':'earth','simulation_seed':42}}
    changed=copy.deepcopy(config);changed['dynamic_objects'][0]['mass']=.12;changed['dynamic_objects'][0]['material_preset']['mass']=.12
    for key in ['force_world_after_first_contact','force_world_relay_phase']:changed['runtime_forces'][0][key][0]=.75
    assert t11_context(config,'relay_block_mass_kg',.1)==t11_context(changed,'relay_block_mass_kg',.12)
    changed['runtime_forces'][0]['force_world_after_contact'][0]=.6
    assert t11_context(config,'relay_block_mass_kg',.1)!=t11_context(changed,'relay_block_mass_kg',.12)
