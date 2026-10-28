from scripts.collect_t18_p26_migration import merge_completed_rows


def test_resumed_queue_keeps_verified_results_beyond_status_cursor():
    completed=dict(job_id='later',status='conditional_event_search_completed')
    failure=dict(job_id='earlier',status='failed')
    assert merge_completed_rows([failure],[completed])==[failure,completed]


def test_successful_canonical_retry_replaces_stale_failure_without_duplicate():
    completed=dict(job_id='same',status='conditional_event_search_completed')
    assert merge_completed_rows([dict(job_id='same',status='failed')],[completed])==[completed]
