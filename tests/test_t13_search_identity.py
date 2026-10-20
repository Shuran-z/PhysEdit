import copy

from scripts.t13_current_boundary_worker import job_identity


def test_same_parameter_interval_in_other_context_has_distinct_identity():
    job=dict(family='drink_edge_distance',target_event='motion',bracket=[.1,.12],endpoints=[dict(sample_id='home_low',state_sha256='a',config=dict(manifest='home')),dict(sample_id='home_high',state_sha256='b',config=dict(manifest='home'))])
    other=copy.deepcopy(job)
    for r in other['endpoints']:
        r['sample_id']=r['sample_id'].replace('home','library');r['config']['manifest']='library'
    assert job_identity(job)!=job_identity(other)
    other=copy.deepcopy(job);other['endpoints'][0]['config']['solver_dt']=.001
    assert job_identity(job)!=job_identity(other)
