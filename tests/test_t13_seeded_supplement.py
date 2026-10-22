import pytest
from scripts.register_t13_seeded_supplement import bind


def inputs():
    job=dict(job_id='j',family='edge',target_event='fall',endpoints=[dict(sample_id='original_a',state_sha256='a'),dict(sample_id='original_b',state_sha256='b')],supplemental_grid=[dict(theta=0),dict(theta=1)])
    result=dict(status='supplemental_grid_completed',supplemental_init_seed=0,source_state_sha256=['a','b'],local_intervals=[dict(bracket=[.4998,.5002],endpoint_labels=[0,1])])
    probes=[dict(theta=t,events=dict(fall=label),supplemental_init_seed=0,state_sha256='s',config_sha256='c',state_path='/state') for t,label in [(0,0),(.4998,0),(.5002,1),(1,1)]]
    return job,result,probes


def test_seeded_distances_keep_both_sides_and_separate_original_truth():
    rows=bind(*inputs())
    assert len(rows)==4 and {r['reference_label'] for r in rows}=={0,1}
    assert all(not r['formal_nearacc_eligible'] and not r['original_publication_reference'] for r in rows)
    assert all(r['sample_id'].startswith('T13_seed0_') for r in rows)
    assert rows[0]['distances'][0]['distance_lower']==.4998


def test_no_flip_retains_probes_without_inventing_boundary():
    job,result,probes=inputs();result['local_intervals']=[]
    rows=bind(job,result,probes)
    assert len(rows)==4 and all(r['distances']==[] for r in rows)


def test_endpoint_contradiction_is_rejected():
    job,result,probes=inputs();probes[2]['events']['fall']=0
    with pytest.raises(ValueError,match='opposite'):bind(job,result,probes)
