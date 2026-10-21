import pytest
from scripts.parallelize_missing_scan_replays import partition
from scripts.register_t06_t10_replay_distances import replay_launches


def test_partition_preserves_each_original_job_without_changing_its_config():
    jobs=[dict(scene_id=s,sample_id=str(i),config={'seed':i}) for i,s in enumerate(['T06','T10','T06'])]
    groups=partition(jobs)
    assert groups['T06']==[jobs[0],jobs[2]]
    assert groups['T10']==[jobs[1]]
    assert groups['T10'][0] is jobs[1]


def test_partition_refuses_duplicates_and_unknown_scenes():
    with pytest.raises(ValueError,match='duplicate'):partition([dict(scene_id=s,sample_id='same') for s in ['T06','T10']])
    with pytest.raises(ValueError,match='unexpected'):partition([dict(scene_id='T09',sample_id='x')])


def test_distance_measurement_discovers_both_split_queues(tmp_path):
    names=['t06_t10_missing_state_replay_launch_20261020.json','t10_parallel_state_replay_launch_20261020.json']
    for n in names:(tmp_path/n).write_text('{}')
    assert [p.name for p in replay_launches(tmp_path)]==names
