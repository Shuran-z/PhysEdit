import copy

import pytest

from physedit.original_joint_path import T11_KEYS,make_joint_path,vector_at


def nodes():
    tuples=[(2.,.07,.15,.065,.22),(2.25,.055,.125,.075,.18),
            (2.45,.045,.105,.0875,.15),(2.65,.035,.085,.1,.12),
            (2.85,.03,.07,.115,.1),(3.05,.024,.055,.13,.08),
            (3.3,.018,.04,.15,.06),(3.55,.012,.03,.175,.04)]
    return [dict(zip(T11_KEYS,row))for row in tuples]


def test_original_joint_path_recovers_all_eight_nodes_without_modification():
    values=nodes();before=copy.deepcopy(values);path=make_joint_path(values)
    assert path['coordinates'][0]==0 and path['coordinates'][-1]==1
    for coordinate,node in zip(path['coordinates'],values):
        assert vector_at(path,coordinate)==node
    assert values==before
    assert path['coordinates'][5]!=pytest.approx(5/7)  # Arc length is not a row index.


def test_original_joint_path_interpolates_all_five_inputs_in_one_segment():
    values=nodes();path=make_joint_path(values)
    midpoint=(path['coordinates'][4]+path['coordinates'][5])/2
    vector=vector_at(path,midpoint)
    for key in T11_KEYS:
        assert vector[key]==pytest.approx((values[4][key]+values[5][key])/2)


def test_original_joint_path_rejects_extrapolation_and_incomplete_vectors():
    path=make_joint_path(nodes())
    with pytest.raises(ValueError,match='outside'):vector_at(path,1.01)
    values=nodes();values[0].pop('case_friction_coefficient')
    with pytest.raises(ValueError,match='five_input'):make_joint_path(values)


def test_original_friction_component_preserves_source_other_inputs_and_actuation():
    from physedit.original_joint_path import t11_case_friction_intervention
    source=nodes()[5]
    config=dict(experiment={'parameter':dict(parameter_value=copy.deepcopy(source),case_friction_coefficient=.08)},
        dynamic_objects=[dict(name='t11_eyeglasses_case',friction=.08,mass=.2,
            pose={'position':[.4,0,.02]},material_preset={'friction':.08,'restitution':.01})],
        runtime_forces=[dict(force_world=[.26,0,0],force_world_after_contact=[.41,0,0])],seed=123)
    before=copy.deepcopy(config)
    assert t11_case_friction_intervention(config,source,.08)==config
    changed=t11_case_friction_intervention(config,source,1.2)
    assert changed['runtime_forces']==config['runtime_forces'] and changed['seed']==123
    assert changed['dynamic_objects'][0]['pose']==config['dynamic_objects'][0]['pose']
    vector=changed['experiment']['parameter']['parameter_value']
    assert all(vector[k]==source[k]for k in T11_KEYS if k!='case_friction_coefficient')
    assert vector['case_friction_coefficient']==changed['dynamic_objects'][0]['friction']==1.2
    assert config==before
    with pytest.raises(ValueError,match='material_domain'):
        t11_case_friction_intervention(config,source,0.)
