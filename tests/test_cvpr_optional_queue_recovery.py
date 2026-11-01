"""Optional prefetch errors must not kill primary training or ignore busy GPUs."""
import ast
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
import pytest

SOURCE=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/h3_queue_recovery/cluster_queue.py'
def helpers(tmp_path):
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in {'health','health_optional','idle_enough'}]
    writes={};ns=dict(subprocess=subprocess,time=time,R=tmp_path,children=[dict(pid=123,name='optional')],atomic=lambda p,v:writes.update({p.name:v}))
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns,writes

def test_optional_failure_reported_but_required_failure_still_raises(tmp_path):
    ns,writes=helpers(tmp_path);worker=SimpleNamespace(pid=123,returncode=1,poll=lambda:1)
    ns['health_optional']([worker])
    assert writes['optional_prefetch_failures.json']['status']=='optional_feature_failure_primary_queue_continues'
    assert writes['optional_prefetch_failures.json']['failures'][0]['returncode']==1
    with pytest.raises(RuntimeError):ns['health']([worker])

def test_running_optional_worker_is_not_reported_as_failed(tmp_path):
    ns,writes=helpers(tmp_path);ns['health_optional']([SimpleNamespace(pid=123,returncode=None,poll=lambda:None)])
    assert not writes

def test_busy_and_missing_gpus_do_not_pass_headroom_gate(tmp_path,monkeypatch):
    ns,_=helpers(tmp_path);monkeypatch.setattr(subprocess,'check_output',lambda *a,**k:'0, 24000\n2, 8500\n4, 24000\n')
    assert ns['idle_enough']([0,4])
    assert not ns['idle_enough']([0,2])
    assert not ns['idle_enough']([7])

def test_observation_error_waits_instead_of_aborting_primary(tmp_path,monkeypatch):
    ns,_=helpers(tmp_path)
    def fail(*a,**k):raise subprocess.CalledProcessError(1,'nvidia-smi')
    monkeypatch.setattr(subprocess,'check_output',fail)
    assert ns['idle_enough']([0]) is False
