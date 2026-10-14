import json
import sys
from pathlib import Path

import pytest

from physedit.__main__ import main


def config_file(tmp_path):
    path = tmp_path / 'experiment.json'
    path.write_text(json.dumps({'model': 'ltx_i2v'}))
    return path


@pytest.mark.parametrize('command', ['plan', 'run'])
def test_short_command_is_read_only_by_default(tmp_path, monkeypatch, capsys, command):
    from physedit import phyediting
    monkeypatch.chdir(tmp_path)
    spec = config_file(tmp_path)
    monkeypatch.setattr(phyediting, 'execution_plan', lambda data: {'model': data['model'], 'gpu_started': False})
    monkeypatch.setattr(phyediting, 'pipeline', lambda *a: pytest.fail('planning must not execute'))
    assert main([command, str(spec)]) == 0
    assert json.loads(capsys.readouterr().out) == {'model': 'ltx_i2v', 'gpu_started': False}
    assert not (tmp_path / 'runs').exists()


def test_short_run_passes_explicit_execution_and_default_directory(tmp_path, monkeypatch):
    from physedit import phyediting
    monkeypatch.chdir(tmp_path)
    spec = config_file(tmp_path)
    calls = []
    monkeypatch.setattr(phyediting, 'pipeline', lambda data, out: calls.append((data, out)) or {'failed': 1})
    assert main(['run', str(spec), '--execute']) == 1
    assert calls == [({'model': 'ltx_i2v'}, 'runs/experiment')]


def test_short_run_honors_explicit_directory(tmp_path, monkeypatch):
    from physedit import phyediting
    calls = []
    monkeypatch.setattr(phyediting, 'pipeline', lambda data, out: calls.append(out) or {'failed': 0})
    assert main(['run', str(config_file(tmp_path)), '--run-dir=other', '--execute']) == 0
    assert calls == ['other']


def test_plan_cannot_execute(tmp_path, monkeypatch):
    from physedit import phyediting
    monkeypatch.setattr(phyediting, 'pipeline', lambda *a: pytest.fail('plan must not execute'))
    with pytest.raises(SystemExit) as exc:
        main(['plan', str(config_file(tmp_path)), '--execute'])
    assert exc.value.code == 2


def test_existing_default_directory_retains_partial_output(tmp_path, monkeypatch):
    from physedit import phyediting
    monkeypatch.chdir(tmp_path)
    spec = config_file(tmp_path)
    partial = Path('runs/experiment/partial.mp4')
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b'original interrupted output')
    monkeypatch.setattr(phyediting, 'execution_plan', lambda data: {})
    with pytest.raises(FileExistsError):
        main(['run', str(spec), '--execute'])
    assert partial.read_bytes() == b'original interrupted output'


def test_short_status_reads_existing_output(tmp_path, capsys):
    root = tmp_path / 'runs/experiment'
    root.mkdir(parents=True)
    (root / 'registered.json').write_text('{"model":"ltx_i2v"}')
    assert main(['status', str(root)]) is None
    assert json.loads(capsys.readouterr().out) == {'registered.json': {'model': 'ltx_i2v'}}


def test_short_evaluate_preserves_plan_and_output_paths(tmp_path, monkeypatch, capsys):
    from physedit import evaluations
    calls = []
    monkeypatch.setattr(evaluations, 'existing_run', lambda data, run, out, execute:
                        calls.append((run, out, execute)) or {'evaluation_failed': 0})
    assert main(['evaluate', str(config_file(tmp_path)), '--run', 'runs/experiment', '--out', 'runs/metrics']) == 0
    assert calls == [('runs/experiment', 'runs/metrics', False)]
    assert json.loads(capsys.readouterr().out)['evaluation_failed'] == 0


def test_legacy_command_keeps_explicit_paths(tmp_path, monkeypatch):
    from physedit import phyediting
    calls = []
    monkeypatch.setattr(phyediting, 'pipeline', lambda data, out: calls.append(out) or {'failed': 0})
    assert main(['run', 'phyediting', '--spec', str(config_file(tmp_path)), '--run-dir', 'runs/legacy', '--execute']) == 0
    assert calls == ['runs/legacy']


@pytest.mark.parametrize('command,module', [('track', 'sam31_frontend'), ('measure', 'phyediting_motion_parameters')])
def test_measurement_aliases_pass_arguments_to_existing_entry(monkeypatch, command, module):
    import importlib
    target = importlib.import_module('scripts.' + module)
    calls = []
    monkeypatch.setattr(target, 'main', lambda: calls.append(sys.argv[1:]) or 0)
    arguments = ['--help'] if command == 'track' else ['friction', 'inputs.jsonl', 'results.json']
    assert main([command, *arguments]) == 0
    assert calls == [arguments]


@pytest.mark.parametrize('command', ['track', 'measure'])
def test_real_measurement_help_and_argv_restoration(command, capsys):
    original = sys.argv
    with pytest.raises(SystemExit) as exc:
        main([command, '--help'])
    assert exc.value.code == 0
    assert sys.argv is original
    assert 'usage: physedit ' + command in capsys.readouterr().out
