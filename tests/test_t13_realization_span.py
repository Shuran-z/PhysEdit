import pytest
from scripts.register_t13_current_searches import merge_realization_windows


def test_repeated_intervals_preserve_empirical_range_without_counting_extra_jobs():
    common=dict(job_id='same',backend_sha256='backend',endpoint_labels=[0,1],stable_unique_threshold_claim=False)
    a=dict(common,bracket=[.010,.011],source_root='repeat0')
    b=dict(common,bracket=[.012,.013],source_root='repeat1')
    result=merge_realization_windows([a,b])
    assert len(result)==1 and result[0]['bracket']==[.010,.013]
    assert result[0]['stable_unique_threshold_claim'] is False
    assert len(result[0]['realization_intervals'])==2
    assert a['bracket']==[.010,.011]


def test_other_backend_or_reversed_branch_cannot_be_silently_merged():
    a=dict(job_id='same',backend_sha256='one',endpoint_labels=[0,1],bracket=[0,1])
    with pytest.raises(ValueError,match='incompatible'):merge_realization_windows([a,dict(a,backend_sha256='two')])
    with pytest.raises(ValueError,match='incompatible'):merge_realization_windows([a,dict(a,endpoint_labels=[1,0])])
