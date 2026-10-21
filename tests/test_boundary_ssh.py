import subprocess
from types import SimpleNamespace
import pytest
from scripts import boundary_ssh as ssh


def test_transport_retry_keeps_command_unchanged(monkeypatch):
    calls=[];results=iter([SimpleNamespace(returncode=255,stdout=b'',stderr=b'connection reset'),SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')])
    monkeypatch.setattr(ssh.subprocess,'run',lambda cmd,**kw:(calls.append(cmd),next(results))[1]);monkeypatch.setattr(ssh.time,'sleep',lambda _:None)
    assert ssh.remote_text('p25','print(1)')=='{}'
    assert calls[0]==calls[1] and 'ConnectTimeout=10' in calls[0]


def test_validation_failure_never_becomes_a_transport_retry(monkeypatch):
    calls=[]
    monkeypatch.setattr(ssh.subprocess,'run',lambda *a,**kw:(calls.append(1),SimpleNamespace(returncode=1,stdout=b'',stderr=b'numeric state changed'))[1])
    with pytest.raises(RuntimeError,match='validation'):ssh.remote_text('p25','code')
    assert len(calls)==1


def test_timeout_is_bounded_and_reported_as_transport_failure(monkeypatch):
    monkeypatch.setattr(ssh.subprocess,'run',lambda *a,**kw:(_ for _ in ()).throw(subprocess.TimeoutExpired('ssh',1)))
    with pytest.raises(ssh.SSHTransportError,match='timed out'):ssh.remote_text('p29','code',timeout=1,attempts=1)
