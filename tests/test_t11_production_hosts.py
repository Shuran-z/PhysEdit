from scripts.launch_t11_verified_producer_searches import producer_pairs


def test_archive_location_cannot_substitute_for_production_worker():
    jobs=[dict(job_id='matched',endpoints=[dict(sample_id='a'),dict(sample_id='b')]),
          dict(job_id='mixed',endpoints=[dict(sample_id='a'),dict(sample_id='c')])]
    audit=[dict(sample_id=s,archive_host='p29',production_host=h) for s,h in [('a','p26'),('b','p26'),('c','p29')]]
    assert producer_pairs(jobs,audit,'p26')==[jobs[0]]
