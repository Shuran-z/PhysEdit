import json
from types import SimpleNamespace
from scripts import t18_table_contact_boundary_worker as worker


def test_memory_pressure_waits_instead_of_marking_physics_failure(monkeypatch,tmp_path):
    free=iter([9000,15000]);waits=[]
    monkeypatch.setattr(worker.shutil,'disk_usage',lambda _:SimpleNamespace(free=100*1024**3))
    monkeypatch.setattr(worker.subprocess,'check_output',lambda *a,**k:str(next(free)).encode())
    monkeypatch.setattr(worker.time,'sleep',lambda seconds:waits.append(seconds))
    worker.wait_for_resources(tmp_path,'2')
    assert waits==[20]
    status=json.loads((tmp_path/'resource_status.json').read_text())
    assert status['status']=='waiting_for_memory' and status['free_memory_mib']==9000
