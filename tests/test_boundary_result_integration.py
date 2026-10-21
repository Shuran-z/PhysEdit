import json
import sys
from types import SimpleNamespace
from scripts import run_boundary_result_integration as runner
from scripts.boundary_ssh import SSHTransportError


def setup(monkeypatch,tmp_path,targets):
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'TARGETS',targets)
    for name in targets:
        (tmp_path/name).write_text(json.dumps(dict(host=name.split('.')[0],root='/run',pid=1)))
    monkeypatch.setattr(sys,'argv',['integration'])
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)


def test_unreachable_host_does_not_block_other_collectors(monkeypatch,tmp_path):
    setup(monkeypatch,tmp_path,{'bad.json':'collector.bad','good.json':'collector.good'})
    calls=[]
    def query(host,code,**kwargs):
        if host=='bad':raise SSHTransportError('offline')
        return json.dumps([dict(name='good.json',running=True,fingerprint='x')])
    # Transport errors are handled per host, irrespective of their exact class.
    monkeypatch.setattr(runner,'remote_text',query)
    monkeypatch.setattr(runner.subprocess,'run',lambda command,**kwargs:(calls.append(command[-1]),SimpleNamespace(returncode=0))[1])
    runner.main()
    status=json.loads((tmp_path/'result_integration_20261020/status.json').read_text())
    assert 'collector.good' in calls and 'collector.bad' not in calls
    assert status['unreachable_hosts']==['bad']
    assert next(j for j in status['jobs'] if j['name']=='bad.json')['running'] is None


def test_failed_postprocessing_retries_without_changed_remote_results(monkeypatch,tmp_path):
    setup(monkeypatch,tmp_path,{'good.json':'collector.good'})
    monkeypatch.setattr(sys,'argv',['integration','--watch'])
    monkeypatch.setattr(runner,'remote_text',lambda *a,**k:json.dumps([dict(name='good.json',running=False,fingerprint='x')]))
    calls=[]
    def run(command,**kwargs):
        module=command[-1];calls.append(module)
        return SimpleNamespace(returncode=int(module=='scripts.combine_recovered_boundary_distances' and calls.count(module)==1))
    monkeypatch.setattr(runner.subprocess,'run',run)
    runner.main()
    assert calls.count('collector.good')==1
    assert calls.count('scripts.combine_recovered_boundary_distances')==2
    status=json.loads((tmp_path/'result_integration_20261020/status.json').read_text())
    assert status['status']=='listed_jobs_ended_review_results'
