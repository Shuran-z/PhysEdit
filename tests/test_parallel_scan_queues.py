import pytest
from scripts.parallelize_missing_scan_replays import partition


def test_partition_preserves_each_original_job_without_changing_its_config():
    jobs=[dict(scene_id=s,sample_id=str(i),config={'seed':i}) for i,s in enumerate(['T06','T10','T06'])]
    groups=partition(jobs)
    assert groups['T06']==[jobs[0],jobs[2]]
    assert groups['T10']==[jobs[1]]
    assert groups['T10'][0] is jobs[1]


def test_partition_refuses_duplicates_and_unknown_scenes():
    with pytest.raises(ValueError,match='duplicate'):partition([dict(scene_id=s,sample_id='same') for s in ['T06','T10']])
    with pytest.raises(ValueError,match='unexpected'):partition([dict(scene_id='T09',sample_id='x')])
