from scripts.expand_t12_p26 import assign_remaining


def test_completed_jobs_are_not_reassigned_and_partial_probes_keep_original_host():
    jobs=[dict(job_id=str(i),grid=list(range(i%3+1))) for i in range(24)]
    queues=assign_remaining(jobs,{'0','1'},{'0':['0','2'],'1':['1','3']})
    ids=[j['job_id'] for q in queues for j in q]
    assert set(ids)=={str(i) for i in range(2,24)} and len(ids)==len(set(ids))
    assert '2' in [j['job_id'] for j in queues[0]]
    assert '3' in [j['job_id'] for j in queues[1]]
