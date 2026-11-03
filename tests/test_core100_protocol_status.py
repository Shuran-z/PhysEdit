import json
import sys

import pytest

from physedit import core100_critical as critical


def test_explicit_prepared_status_does_not_switch_the_live_protocol(monkeypatch,capsys):
    pointer=critical.ROOT/'catalog/prepared_core100_critical_protocol_v3.json'
    selected=json.loads(pointer.read_text())
    path=(pointer.parent/selected['registry']).resolve()
    live=critical.POINTER.read_bytes()
    monkeypatch.setattr(sys,'argv',['core100_critical','status','--registry',str(path),
        '--expected-registry-sha256',selected['registry_sha256']])
    critical.main()
    value=json.loads(capsys.readouterr().out)
    assert value['numerical_boundary_cases']==100
    assert value['critical_rgb_distance_cases']==99
    assert value['critical_rgb_distance_pending']==['T03_C02']
    assert critical.POINTER.read_bytes()==live
    monkeypatch.setattr(sys,'argv',['core100_critical','status'])
    critical.main()
    assert json.loads(capsys.readouterr().out)==critical.load()[0]['summary']


def test_selected_status_requires_its_own_registered_digest(monkeypatch):
    pointer=critical.ROOT/'catalog/prepared_core100_critical_protocol_v3.json'
    selected=json.loads(pointer.read_text());path=(pointer.parent/selected['registry']).resolve()
    monkeypatch.setattr(sys,'argv',['core100_critical','status','--registry',str(path)])
    with pytest.raises(ValueError,match='critical_registry_changed'):critical.main()
