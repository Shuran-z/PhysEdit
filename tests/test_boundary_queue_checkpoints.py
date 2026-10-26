import base64
import gzip
import json
import pytest
from scripts import register_remaining_family_distances as collector


def test_disconnected_queue_retains_only_matching_checkpoint(monkeypatch,tmp_path):
    launch=dict(host='p25',root='/original/run',plan_sha256='a')
    data=dict(results=[dict(job_id='completed')],status=[])
    payload=base64.b64encode(gzip.compress(json.dumps(data).encode())).decode()
    monkeypatch.setattr(collector,'remote_text',lambda *a,**k:payload)
    assert collector.fetch_queue(launch,'query',tmp_path)==(data,None)
    def offline(*a,**k):raise RuntimeError('SSH offline')
    monkeypatch.setattr(collector,'remote_text',offline)
    assert collector.fetch_queue(launch,'query',tmp_path)==(data,'SSH offline')
    # A changed source plan must never borrow another queue's results.
    with pytest.raises(RuntimeError,match='SSH offline'):
        collector.fetch_queue(dict(launch,plan_sha256='b'),'query',tmp_path)


def test_disk_pressure_waits_without_failed_physics_label(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from scripts import t18_table_contact_boundary_worker as worker
    free=iter([19,81]);waits=[]
    monkeypatch.setattr(worker.shutil,'disk_usage',lambda _:SimpleNamespace(free=next(free)*1024**3))
    monkeypatch.setattr(worker.subprocess,'check_output',lambda *a,**k:b'12000')
    monkeypatch.setattr(worker.time,'sleep',lambda n:waits.append(n))
    worker.wait_for_resources(tmp_path,'0',8192)
    assert waits==[20]
    assert json.loads((tmp_path/'resource_status.json').read_text())['status']=='waiting_for_disk'


def test_absent_contact_frames_remain_unknown_in_failure_audit():
    from scripts.audit_t18_source_failures import contact_history
    config=dict(experiment=dict(supported_book_names=['upper'],surface_z=0),dynamic_objects=[dict(name='upper')])
    unknown=contact_history(config,[{},{}])
    assert unknown['ever'] is None and unknown['terminal'] is None
    assert unknown['unknown_frame_count']==2
    known=contact_history(config,[{},dict(contacts=[])])
    assert known['terminal']==0 and known['ever'] is None
