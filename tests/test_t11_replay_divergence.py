import copy
from scripts.diagnose_t11_original_host_replays import compare_states


def state():
    return dict(frames=[dict(objects=[dict(name='t11_eyeglasses_case',position=[0.,0.,0.])]) for _ in range(210)],
        dynamic_objects=[],scene_overrides=dict(dt=.001,raytracing=True),
        runtime_force_summary=[dict(first_contact_frame=77)])


def test_divergence_does_not_conflate_render_flags_with_physics_or_early_errors():
    a=state();b=copy.deepcopy(a);b['scene_overrides']['raytracing']=False
    b['frames'][100]['objects'][0]['position'][0]=.01
    b['frames'][-1]['objects'][0]['position'][2]=-.7
    r=compare_states(a,b,'t11_eyeglasses_case_final_center_below_minus_20cm')
    assert r['original_label']==0 and r['replay_label']==1
    assert r['pre_first_contact_max_difference_m']==0
    assert r['first_difference_frames']['0.001']==100
    assert r['physical_scene_overrides_match'] and not r['scene_overrides_match']


def test_actual_solver_setting_difference_remains_visible():
    a=state();b=copy.deepcopy(a);b['scene_overrides']['dt']=.002
    assert not compare_states(a,b,'t11_eyeglasses_case_final_center_below_minus_20cm')['physical_scene_overrides_match']
