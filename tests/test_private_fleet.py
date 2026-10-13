import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def configuration(env):
    command = [sys.executable, '-c',
               'import json; from physedit import config; '
               'print(json.dumps({"hosts":config.HOSTS,"sites":list(config.SITES)}))']
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)


def test_public_installation_does_not_enable_remote_hosts():
    env = dict(os.environ)
    env.pop('PHYSEDIT_FLEET_CONFIG', None)
    result = configuration(env)
    assert result.returncode == 0
    assert json.loads(result.stdout)['hosts'] == {}


def test_explicit_local_configuration_loads_without_connecting(tmp_path):
    private = tmp_path / 'fleet.py'
    private.write_text('SITES={"example":{"root":"/path/to/workspace"}}\n'
                       'HOSTS={"worker":{"site":"example","ssh":"ssh gpu-host",'
                       '"gpus":[0],"busy_mib":0}}\n')
    result = configuration(dict(os.environ, PHYSEDIT_FLEET_CONFIG=str(private)))
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed['sites'] == ['example']
    assert parsed['hosts']['worker']['ssh'] == 'ssh gpu-host'


def test_incomplete_private_configuration_fails_before_remote_execution(tmp_path):
    private = tmp_path / 'bad.py'
    private.write_text('SITES={}\nHOSTS="not a mapping"\n')
    result = configuration(dict(os.environ, PHYSEDIT_FLEET_CONFIG=str(private)))
    assert result.returncode != 0
    assert 'private_fleet_requires_mapping_HOSTS' in result.stderr
