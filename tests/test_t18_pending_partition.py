import pytest
from scripts.parallelize_t18_remaining import partition
from scripts.t18_table_contact_boundary_worker import job_folder


def test_pending_queues_are_disjoint_balanced_and_prioritize_resource_cohort():
    jobs=[dict(job_id=str(i)) for i in range(17)];cohort={'9','10','11','12','13'}
    queues=partition(jobs,cohort)
    flattened=[j['job_id'] for queue in queues for j in queue]
    assert sorted(flattened)==sorted(j['job_id'] for j in jobs)
    assert len(flattened)==len(set(flattened))
    assert max(map(len,queues))-min(map(len,queues))<=1
    for queue in queues:
        flags=[j['job_id'] in cohort for j in queue]
        assert flags==sorted(flags,reverse=True)


def test_duplicate_jobs_cannot_be_assigned_to_two_workers():
    with pytest.raises(ValueError,match='duplicate'):
        partition([dict(job_id='same'),dict(job_id='same')],set())


def test_job_output_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError,match='invalid job'):
        job_folder(tmp_path,'../outside')


def test_shared_probe_directory_must_belong_to_original_task_root(tmp_path):
    original=tmp_path/'run'/'job';original.mkdir(parents=True)
    root=tmp_path/'resource_parallel_20261022_0';root.mkdir()
    try:(root/'job').symlink_to(original,target_is_directory=True)
    except OSError:pytest.skip('directory symlinks require Windows privileges')
    assert job_folder(root,'job').resolve()==original
    outside=tmp_path/'other'/'escape';outside.mkdir(parents=True)
    (root/'escape').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='outside original'):
        job_folder(root,'escape')
