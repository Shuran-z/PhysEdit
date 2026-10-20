import copy

import pytest

from scripts.bind_current_release_parameter_families import bind_t13


def fixture():
    return dict(sample_metadata=dict(main_parameter_name='drink_edge_distance',main_parameter_value=.02),
        experiment=dict(drink_edge_distance=.12),t13_parameters=dict(drink_edge_distance=.35),
        dynamic_objects=[dict(name='t13_shelf_plank',size=[.79,.34,.04],pose=dict(position=[3.915,2.7,1.1],euler_xyz=[0.,0.,0.])),
            dict(name='t13_drink_box',size=[.06,.06,.18],collision_proxy_size=[.065,.045,.145],pose=dict(position=[4.2575,2.7,1.1927],euler_xyz=[0.,0.,0.]))])


def test_edge_coordinate_uses_collision_proxy_and_ignores_stale_fields():
    result=bind_t13(fixture())
    assert result['theta']==.02
    assert result['physical_edge_distance_m']==pytest.approx(.02)
    assert result['stale_experiment_edge_distance']==.12


def test_wrong_declared_coordinate_is_rejected():
    c=fixture();c['sample_metadata']['main_parameter_value']=.12
    with pytest.raises(ValueError,match='physical edge parameter mismatch'):bind_t13(c)


def test_rotated_initial_geometry_requires_different_adapter():
    c=fixture();c['dynamic_objects'][1]['pose']['euler_xyz'][2]=20.
    with pytest.raises(ValueError,match='axis-aligned'):bind_t13(c)
