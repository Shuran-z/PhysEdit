import pytest
from scripts.register_t12_remaining_grid import bind


def inputs():
    job=dict(axis='speed',fixed_context_sha256='ctx',members=[dict(sample_id='s',theta=1.0,reference_label=0,state_sha256='original')],grid=[1.0,2.0],normalization_domain=[1.0,2.0],revision='release',target_event='tissue_box_max_displacement_ge_1cm',reference_kind='supplemental',job_id='job')
    probes=[dict(theta=t,label=l) for t,l in [(1.0,0),(2.0,1),(1.500,0),(1.5005,1)]]
    result=dict(status='remaining_grid_completed',axis='speed',fixed_context_sha256='ctx',member_reference_state_sha256=['original'],verified_probes=probes,intervals=[dict(bracket=[1.5,1.5005],labels=[0,1])],backend_sha256='renderer')
    return job,result


def test_new_grid_binding_retains_published_truth_and_axis_domain():
    job,result=inputs();rows=bind(job,result)
    assert rows[0]['reference_label']==0 and rows[0]['normalized_distance_lower']==.5
    assert rows[0]['formal_nearacc_eligible'] is False
    assert rows[0]['reference_state_sha256']=='original'


def test_new_grid_cannot_override_disagreeing_published_member():
    job,result=inputs();result['verified_probes'][0]['label']=1
    with pytest.raises(ValueError,match='published member'):bind(job,result)


def test_no_flip_is_completed_but_does_not_invent_a_distance():
    job,result=inputs();result['intervals']=[]
    assert bind(job,result)==[]
