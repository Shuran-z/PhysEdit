from scripts.register_five_scene_refinements import index_attempts


def test_restarting_partial_status_does_not_erase_previously_failed_attempts():
    old=[dict(job_id='failed',status='failed'),dict(job_id='ok',status='refined_local_interval')]
    current=[dict(job_id='new',status='refined_local_interval')]
    assert set(index_attempts(old,current))=={'failed','ok','new'}


def test_successful_retry_replaces_failure_but_failure_never_replaces_success():
    prior=[dict(job_id='a',status='failed'),dict(job_id='b',status='refined_local_interval')]
    resumed=[dict(job_id='a',status='refined_local_interval'),dict(job_id='b',status='failed')]
    assert all(r['status']=='refined_local_interval' for r in index_attempts(prior,resumed).values())
