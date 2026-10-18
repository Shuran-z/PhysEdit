import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from physedit import gravity100 as g100
from physedit import conditioned_measurement as cm


def dump(path, obj):
    Path(path).write_text(json.dumps(obj))
    return str(path)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    image = np.full((64, 96, 3), 150, np.uint8)
    cv2.rectangle(image, (30, 15), (45, 30), (20, 70, 190), -1)
    cond = tmp_path / 'condition.png'
    cv2.imwrite(str(cond), image)
    video = tmp_path / 'reference.avi'
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'FFV1'), 30., (96, 64))
    assert writer.isOpened()
    for _ in range(10):
        writer.write(image)
    writer.release()
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('Continue the visible motion with fixed camera.')
    known = tmp_path / 'known.json'
    dump(known, {'camera': {}, 'object': {}, 'motion': {}, 'window': {'start_frame': 0, 'max_frames': 10}})
    desc = tmp_path / 'estimator.json'
    times = [i / 30 for i in range(10)]
    dump(desc, dict(kind='frozen', module=None, known_conditions='known.json',
                    known_conditions_sha256=g100.sha256(known), registered_physical_times_s=times))
    source = list(csv.DictReader(g100.MANIFEST.open()))
    fields = list(source[0])
    members = []
    tasks = []
    for old in source:
        row = dict(old, conditioning_image_sha256=g100.sha256(cond), reference_video_sha256=g100.sha256(video),
                   evaluation_frame_count='10', source_condition_frame='0', source_last_frame='9')
        members.append(row)
        tasks.append(dict(id=old['id'], conditioning_image='condition.png', reference_video='reference.avi',
                          estimator='estimator.json', estimator_sha256=g100.sha256(desc),
                          initial_objects={'object': [30, 15, 46, 31]}, target_name='object',
                          physical_times_s=times, conditioning_frame=0, evaluation_start_frame=0,
                          generation_prompt='prompt.txt', generation_prompt_sha256=g100.sha256(prompt),
                          prompt_source='fixture', image_size=[96, 64]))
    manifest = tmp_path / 'manifest.csv'
    with manifest.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(members)
    task_file = tmp_path / 'tasks.jsonl'
    g100.write_rows(task_file, tasks)
    monkeypatch.setattr(g100, 'MANIFEST_SHA256', g100.sha256(manifest))
    spec = dict(protocol='gravity100', gravity100=dict(tasks=str(task_file), tasks_sha256=g100.sha256(task_file),
                manifest=str(manifest), manifest_sha256=g100.sha256(manifest)), model='cpu_fixture',
                model_dir='unused', sam3='unused', checkpoint='unused', frames=10, fps=30,
                generation_command=['cpu-fixture', '{manifest}'], evaluation={'metrics': ['gravtrace']})
    return spec, tasks, tmp_path


def test_plan_uses_all_current_members_and_zero_condition_without_launch(prepared, monkeypatch):
    spec, tasks, root = prepared
    monkeypatch.setattr(g100.subprocess, 'run', lambda *a, **k: pytest.fail('plan launched a process'))
    from physedit.phyediting import execution_plan
    plan = execution_plan(spec)
    assert plan['registered'] == plan['input_ready'] == plan['native_time_grid_ready'] == 100
    assert plan['group_counts'] == {'ID': 80, 'OOD-1': 10, 'OOD-2': 10}
    assert plan['conditioning_frame'] == plan['evaluation_start_frame'] == 0
    assert not plan['gpu_started']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'condition23', 'clock', 'asset', 'target', 'old_boxes', 'prompt'])
def test_old_inputs_drift_and_reference_observations_rejected(prepared, fault):
    spec, tasks, root = prepared
    if fault == 'missing':
        tasks.pop()
    elif fault == 'duplicate':
        tasks[-1] = tasks[0]
    elif fault == 'condition23':
        tasks[0]['conditioning_frame'] = 23
    elif fault == 'clock':
        tasks[0]['physical_times_s'][1] = .02
    elif fault == 'asset':
        (root / 'condition.png').write_bytes(b'changed')
    elif fault == 'prompt':
        (root / 'prompt.txt').write_text('changed after registration')
    else:
        known = json.loads((root / 'known.json').read_text())
        known['target_gravity' if fault == 'target' else 'observed_boxes'] = 9.81
        dump(root / 'known.json', known)
        d = json.loads((root / 'estimator.json').read_text())
        d['known_conditions_sha256'] = g100.sha256(root / 'known.json')
        dump(root / 'estimator.json', d)
        for t in tasks:
            t['estimator_sha256'] = g100.sha256(root / 'estimator.json')
    (root / 'tasks.jsonl').write_text(''.join(json.dumps(t) + '\n' for t in tasks))
    spec['gravity100']['tasks_sha256'] = g100.sha256(root / 'tasks.jsonl')
    with pytest.raises(ValueError):
        g100.execution_plan(spec)


def test_physics_clock_is_not_media_fps_and_short_native_scope_is_explicit(prepared):
    spec, _, _ = prepared
    members, tasks = g100.read_inputs(spec)
    member = dict(members[0], evaluation_frame_count='4')
    task = dict(tasks[members[0]['id']], physical_times_s=[0., .02, .04, .06])
    clock = g100.observation_clock(member, task, 30., 30)
    assert clock['generated_frames'] == [0, 1, 2, 3]
    assert clock['physical_times_s'] == pytest.approx([0, .02, .04, .06])
    assert clock['physics_seconds_per_media_second'] == pytest.approx(.6)
    short = g100.observation_clock(dict(member, evaluation_frame_count='2'),
                                  dict(task, physical_times_s=[0., .02]), 16., 81)
    assert short['generated_frames'] == [0]
    assert not short['applicable']
    assert short['reason'] == 'native_frames_within_fixed_horizon_below_model_minimum'


def test_model_duration_cannot_drop_last_registered_time(prepared):
    spec, _, _ = prepared
    members, tasks = g100.read_inputs(spec)
    c = g100.observation_clock(members[0], tasks[members[0]['id']], 30., 5)
    assert c['reason'] == 'generation_duration_shorter_than_fixed_scope'


def test_build_uses_exact_condition_image_and_never_legacy_builder(prepared, monkeypatch):
    spec, _, root = prepared
    from scripts import phyediting_gen
    monkeypatch.setattr(phyediting_gen, 'build', lambda *a: pytest.fail('old frame23 builder called'))
    _, rows, tasks, items = g100.build_inputs(spec, root / 'run')
    assert len(rows) == len(items) == 100
    for r in rows:
        assert r['condition_frame_index'] == r['condition_time_ms'] == 0
        assert g100.sha256(r['condition_image']) == g100.sha256(tasks[r['item_id']]['conditioning_image'])
        assert r['sample_id'] not in Path(r['prompt_file']).read_text()
        assert r['protocol'] == 'gravity100'


@pytest.mark.parametrize('key', ['g', 'g0', 'gravity', 'gravity_truth', 'known_gravity', 'target_gravity',
                                'gravity_target', 'gravity_m_s2', 'reference_estimate_m_s2',
                                'source_states', 'future_poses', 'observed_masks', 'distance_m'])
def test_nested_target_aliases_and_old_observations_never_reach_estimator(key):
    with pytest.raises(ValueError):
        cm.reject_target({'condition': {key: 9.81}})
    cm.reject_target({'gravity_dir': [0, 0, -1], 'known_gravity': None})


def test_summary_keeps_all_failures_and_never_uses_reference_estimates():
    rows = [dict(sample_id=str(k), item_id='G' + str(k), split=group, gravity_truth=10.)
            for k, group in enumerate(['ID', 'ID', 'OOD-1', 'OOD-2'])]
    predictions = [dict(id='0', status='ok', gravity=9.), dict(id='1', status='at_bound', gravity=.1),
                   dict(id='2', status='measurement_failure', gravity=None, reason='missing mask'),
                   dict(id='3', status='ok', gravity=11.)]
    result = g100.summarize(rows, predictions)
    assert result['registered'] == 4 and result['scored'] == result['failed'] == 2
    assert result['failure_rate_percent'] == result['coverage_percent'] == 50
    assert result['numeric_output_coverage_percent'] == 75
    assert result['mean_error_percent'] == pytest.approx(10)
    assert result['groups']['OOD-1']['registered'] == 1
    assert result['groups']['OOD-1']['scored'] == 0


def test_fresh_gpu_check_defers_occupied_devices_without_launch(prepared, monkeypatch):
    spec, _, _ = prepared
    spec['generation_runtime'] = dict(gpu_devices='0')
    answers = iter(['GPU-a, 0, 0\n', 'GPU-a, 1234\n'])
    monkeypatch.setattr(g100.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=next(answers)))
    with pytest.raises(RuntimeError, match='gpu_deferred_not_fully_idle'):
        g100.require_idle_gpu(spec)


def test_cpu_full_controller_retains_failed_generation_and_reuses_only_generated_predictions(prepared, monkeypatch):
    spec, _, root = prepared
    from scripts import sam31_frontend as frontend
    from physedit import phyediting, evaluations
    monkeypatch.setattr(frontend, 'validate_runtime', lambda *a: {'fixture': True})
    def launch(command, **kwargs):
        assert command[0] == 'cpu-fixture'
        for row in g100.read_rows(command[1])[:-1]:
            dest = Path(row['generated_video_resized_to_source'])
            dest.parent.mkdir(parents=True)
            shutil.copyfile(row['source_video'], dest)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(g100.subprocess, 'run', launch)
    def fake_frontend(output, *args):
        tracks = []
        folder = output / 'runs/sam31_visible_projection_full30_masks'
        folder.mkdir()
        for job in g100.read_rows(output / 'all_jobs.jsonl'):
            if job['input_failure']:
                continue
            mask = np.zeros((64, 96), bool)
            mask[15:31, 30:46] = True
            stem = hashlib.sha256(job['id'].encode()).hexdigest()[:12]
            for frame in job['frames']:
                np.savez_compressed(folder / (stem + '_' + str(frame) + '.npz'), mask=mask)
            tracks.append(dict(id=job['id'], video_sha256=job['video_sha256'],
                               tracks={job['target_name']: dict(frames=job['frames'],
                               xyxy=[[30, 15, 46, 31]] * len(job['frames']))}))
        g100.write_rows(output / 'tracks_v4.jsonl', tracks)
    monkeypatch.setattr(frontend, 'run', fake_frontend)
    calls = []
    def current_measurement(task, video, frames, times, masks, output):
        calls.append(video)
        assert video != task['reference_video']
        assert frames[0] == times[0] == 0
        cm.descriptor(task)
        return dict(status='ok', gravity=9.81)
    monkeypatch.setattr(cm, 'measure', current_measurement)
    run = root / 'run'
    result = phyediting.pipeline(spec, run)
    assert len(calls) == result['scored'] == 99
    assert result['registered'] == 100 and result['failed'] == 1
    assert len(g100.read_rows(run / 'conditional_gravity/predictions.jsonl')) == 100
    monkeypatch.setattr(cm, 'measure', lambda *a, **k: pytest.fail('existing-run must not refit'))
    monkeypatch.setattr(g100.subprocess, 'run', lambda *a, **k: pytest.fail('existing-run must not generate'))
    again = evaluations.existing_run(spec, run, root / 'recheck', execute=True)
    assert again['scored'] == 99 and again['failed'] == 1


def test_prepare_cli_writes_new_protocol_only(prepared):
    spec, _, root = prepared
    config = {k: v for k, v in spec.items() if k not in ('protocol', 'gravity100')}
    dump(root / 'model.json', config)
    from physedit.__main__ import main
    assert main(['prepare-gravity100', str(root / 'tasks.jsonl'), '--model-config', str(root / 'model.json'),
                 '--manifest', str(root / 'manifest.csv'), '--out', str(root / 'new.json')]) == 0
    new = json.loads((root / 'new.json').read_text())
    assert new['protocol'] == 'gravity100'
    assert 'compact' not in new and 'items' not in new


def test_reference_adaptive_candidate_cache_is_not_a_runtime_input(prepared):
    spec, _, root = prepared
    d = json.loads((root / 'estimator.json').read_text())
    d['forward_model_bank'] = dict(path='old_reference_responses.json')
    dump(root / 'estimator.json', d)
    task = dict(estimator=str(root / 'estimator.json'), estimator_sha256=g100.sha256(root / 'estimator.json'))
    with pytest.raises(ValueError, match='reference_adaptive_response_bank'):
        cm.descriptor(task)


def test_native_target_is_checked_before_process_launch(tmp_path, monkeypatch):
    from physedit.native_physics import ForwardModel
    monkeypatch.setattr(g100.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid native target launched'))
    with pytest.raises(ValueError, match='native_target_must_be_unknown_gravity'):
        ForwardModel({'command': ['never']}, {'target': 'gravity', 'known_gravity': 9.81}, [0, .04], tmp_path)


def test_union_observations_preserve_both_instances(tmp_path, monkeypatch):
    known = dict(schema='fixture', camera={}, image_size=[100, 50])
    dump(tmp_path / 'known.json', known)
    d = dict(kind='model', module='fixture', known_conditions='known.json',
             known_conditions_sha256=g100.sha256(tmp_path / 'known.json'),
             observation_fields=['observed_boxes'])
    dump(tmp_path / 'estimator.json', d)
    seen = []
    def estimate(p):
        seen.extend(p['observed_boxes'])
        return dict(status='ok', gravity=1.)
    monkeypatch.setattr(cm, 'model_module', lambda name: SimpleNamespace(estimate=estimate))
    masks = {}
    for role, x in [('a', 5), ('b', 75)]:
        mask = np.zeros((50, 100), bool)
        mask[10:20, x:x+10] = True
        path = tmp_path / (role + '.npz')
        np.savez_compressed(path, mask=mask)
        masks[role] = [str(path)] * 2
    video = tmp_path / 'video.bin'
    video.write_bytes(b'current-video-fixture')
    task = dict(estimator=str(tmp_path / 'estimator.json'), estimator_sha256=g100.sha256(tmp_path / 'estimator.json'),
                target_name='union', measurement_roles=['a', 'b'], image_size=[100, 50])
    result = cm.measure(task, str(video), [0, 1], [0., 1/30], masks, tmp_path / 'result')
    assert result['status'] == 'ok'
    assert seen == [[5., 10., 85., 20.], [5., 10., 85., 20.]]


def test_native_bridge_preserves_stream_and_has_private_socket(tmp_path):
    import json, os, socket, subprocess, sys, time
    # Use a short path: Unix sockets on macOS have a 104-byte pathname limit.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='pe-', dir='/tmp') as directory:
        path = Path(directory) / 'cpu.sock'
        command = tmp_path / 'command.json'
        command.write_text(json.dumps([sys.executable, '-u', '-c',
            'import sys;print("ready",flush=True);[print(s.strip().upper(),flush=True) for s in sys.stdin]']))
        server = subprocess.Popen([sys.executable, '-m', 'physedit.native_bridge', 'serve',
                                   '--socket', str(path), '--command-json', str(command)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not path.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert path.stat().st_mode & 0o777 == 0o600
            client = subprocess.run([sys.executable, '-m', 'physedit.native_bridge', 'connect',
                                     '--socket', str(path)], input='one\ntwo\n', text=True,
                                    capture_output=True, timeout=5, check=True)
            assert client.stdout == 'ready\nONE\nTWO\n'
            assert client.stderr == ''
        finally:
            server.terminate()
            server.wait(timeout=5)


def test_fixed_native_prefix_keeps_pixels_and_fps(tmp_path):
    import cv2, numpy as np
    from physedit.conditioned_measurement import observation_video
    source = tmp_path / 'generated.avi'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'FFV1'), 25., (16, 12))
    for k in range(8): writer.write(np.full((12,16,3), k*20, np.uint8))
    writer.release()
    actual = observation_video(source, [0,1,2,3], tmp_path)
    cap = cv2.VideoCapture(actual)
    assert cap.get(cv2.CAP_PROP_FPS) == 25.
    assert cap.get(cv2.CAP_PROP_FRAME_COUNT) == 4
    for k in range(4):
        ok, image = cap.read()
        assert ok and np.all(image == k*20)
    assert not cap.read()[0]
    cap.release()


def test_known_control_resampling_preserves_solver_tick():
    import numpy as np
    from physedit.conditioned_control_clock import displacement_at_times
    from physedit.conditioned_models.known_forced_group_1d import displacement
    from physedit.conditioned_measurement import native_control_clock, minimum_observations
    p = {'mass':1., 'known_friction':.05, 'known_linear_drag_per_second':.02,
         'known_velocity':[.4,0,0], 'step_s': .005, 'steps_per_observation': 4,
         'condition_frame_relative':0,
         'world_force_updates_from_config': [[0.,0.,0.],[1.,0.,0.],[2.,0.,0.],[-1.,0.,0.],[0.,0.,0.],[.3,0.,0.]]}
    ct = np.arange(6)*.02
    expected = displacement(p,4.)
    assert np.max(abs(displacement_at_times(p,4.,ct,ct)-expected)) < 1e-12
    actual = displacement_at_times(p,4.,[0.,1/24.,2/24.],ct)
    assert actual.shape == (3,) and np.isfinite(actual).all()
    d = {'module':'known_group_outline','registered_physical_times_s':ct.tolist()}
    assert native_control_clock(d,{'known_group_condition':p},[0.,1/24.,2/24.]) is None
    assert p['steps_per_observation'] == 4
    assert minimum_observations({'kind':'model','module':'closed_damped_visible_initial'}) == 4
    assert minimum_observations({'kind':'model','module':'known_push_gravity'}) == 6


@pytest.mark.parametrize('fault', [None, 'device', 'memory', 'busy'])
def test_explicit_shared_gpu_retains_other_processes_and_checks_budget(monkeypatch, fault):
    calls = []
    def resource(query, **kwargs):
        calls.append(query)
        field = next(x for x in query if x.startswith('--query-'))
        if field == '--query-gpu=memory.free':
            return SimpleNamespace(stdout='8000' if fault == 'memory' else '21500')
        if 'compute-apps' in field:
            return SimpleNamespace(stdout='GPU-fixture, 1234')
        return SimpleNamespace(stdout='GPU-fixture, 3000, '+('80' if fault == 'busy' else '0'))
    monkeypatch.setattr(g100.subprocess, 'run', resource)
    spec = {'generation_runtime': {'gpu_devices':'1','gpu_sharing':{
        'allowed_gpu_uuids':['GPU-other' if fault == 'device' else 'GPU-fixture'],
        'minimum_free_mib':16384,'maximum_utilization_percent':30}}}
    if fault == 'device':
        with pytest.raises(ValueError, match='not_authorized'): g100.require_idle_gpu(spec)
    elif fault:
        with pytest.raises(RuntimeError, match='deferred_shared'): g100.require_idle_gpu(spec)
    else:
        g100.require_idle_gpu(spec)
    assert all(q[0] == 'nvidia-smi' for q in calls)


def test_sharing_rejects_implicit_or_unbounded_policy():
    with pytest.raises(ValueError, match='requires_device_allowlist'):
        g100.gpu_sharing_policy({'generation_runtime':{'gpu_sharing':True}})
