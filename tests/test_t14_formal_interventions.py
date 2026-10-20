import copy

import pytest

from scripts.t14_formal_boundary_worker import canonical,intervene


def fixture():
    return dict(manifest='old-T14-frozen-background.json',scene_overrides=dict(constraint_timeconst=.001,gravity=[0,0,-9.81]),
        render=dict(fps=30,frames=210,pre_static_frames=24,physics_steps_per_render_frame=128),
        experiment=dict(parameter=dict(channel_throat_width_m=.018,marker_initial_yaw_deg=0.,trigger_impulse_magnitude_Ns=.0351,
            marker_mass_kg=.018,marker_initial_speed_mps=1.95,marker_initial_velocity_mps=[1.95,0,0],trigger_impulse_vector_Ns=[.0351,0,0])),
        dynamic_objects=[dict(name='t14v2_corridor_book_left',pose=dict(position=[0,-.104,0])),dict(name='t14v2_corridor_book_right',pose=dict(position=[0,.104,0])),
            dict(name='t14v2_marker',mass=.018,pose=dict(euler_xyz=[0,0,0]),motion=dict(initial_velocity=[1.95,0,0]))])


@pytest.mark.parametrize('family,value', [('channel_throat_width_m',.019),('marker_initial_yaw_deg',8.),('trigger_impulse_magnitude_Ns',.0288)])
def test_physical_intervention_preserves_mass_solver_and_source(family,value):
    c=fixture();original=copy.deepcopy(c);new=intervene(c,family,value)
    assert c==original
    assert canonical(c,family)==canonical(new,family)
    assert new['scene_overrides']['constraint_timeconst']==.001
    assert new['dynamic_objects'][-1]['mass']==.018
    if family=='trigger_impulse_magnitude_Ns':
        assert new['dynamic_objects'][-1]['motion']['initial_velocity'][0]==pytest.approx(value/.018)
    if family=='channel_throat_width_m':
        before=c['dynamic_objects'][1]['pose']['position'][1]-c['dynamic_objects'][0]['pose']['position'][1]
        after=new['dynamic_objects'][1]['pose']['position'][1]-new['dynamic_objects'][0]['pose']['position'][1]
        assert after-before==pytest.approx(value-.018)


def test_fixed_context_keeps_solver_and_mass_changes():
    c=fixture();other=copy.deepcopy(c);other['scene_overrides']['constraint_timeconst']=.005
    assert canonical(c,'channel_throat_width_m')!=canonical(other,'channel_throat_width_m')
    other=copy.deepcopy(c);other['dynamic_objects'][-1]['mass']=.03
    assert canonical(c,'channel_throat_width_m')!=canonical(other,'channel_throat_width_m')
