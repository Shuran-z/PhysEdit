import json
import time

import pytest

from scripts.boundary_ssh import transport_options


def test_temporary_proxy_is_scoped_to_named_hosts_and_expiration(tmp_path):
    route=tmp_path/'route.json';connector=tmp_path/'Git tools/connect.exe';connector.parent.mkdir();connector.touch()
    data=dict(endpoint='127.0.0.1:7897',hosts=['p25'],expires_at=time.time()+60)
    route.write_text(json.dumps(data))
    args=transport_options('p25',route_path=route,connector=connector)
    assert args[0]=='-o' and '-H 127.0.0.1:7897 %h %p'in args[1]
    assert transport_options('p26',route_path=route,connector=connector)==[]
    data['expires_at']=0;route.write_text(json.dumps(data))
    assert transport_options('p25',route_path=route,connector=connector)==[]


def test_proxy_route_cannot_inject_an_arbitrary_shell_endpoint(tmp_path):
    route=tmp_path/'route.json';connector=tmp_path/'connect.exe';connector.touch()
    route.write_text(json.dumps(dict(endpoint='bad & command',hosts=['p25'],expires_at=time.time()+60)))
    with pytest.raises(ValueError,match='unsupported_boundary_proxy_endpoint'):
        transport_options('p25',route_path=route,connector=connector)


def test_scoped_jump_does_not_depend_on_http_connector(tmp_path,monkeypatch):
    from pathlib import Path
    route=tmp_path/'route.json'
    route.write_text(json.dumps(dict(transport='sg88_jump',endpoint='yangkaiyuan@172.25.72.115:22',
        hosts=['p25'],expires_at=time.time()+60)))
    exists=Path.exists
    monkeypatch.setattr(Path,'exists',lambda p:True if p.name=='id_ed25519_sg88n5'else exists(p))
    args=transport_options('p25',route_path=route,connector=tmp_path/'missing.exe')
    assert args[0]=='-o' and '-W %h:%p yangkaiyuan@172.25.72.115'in args[1]
    assert transport_options('p26',route_path=route)==[]
    data=json.loads(route.read_text());data['endpoint']='bad & command';route.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='unsupported_boundary_jump_endpoint'):
        transport_options('p25',route_path=route)
