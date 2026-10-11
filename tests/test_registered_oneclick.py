"""No GPU or model inference: check the twelve launch contracts and input isolation."""
import json
import sys
import subprocess
import venv
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from physedit import phyediting
from physedit.runners.oneclick_registry import MODELS, validate_registration
from physedit.runners import registered_oneclick as adapter
from physedit.runners.media_contract import validate_video
from physedit.runners.media_contract import sha256, verified_completion


@pytest.mark.parametrize('model', sorted(MODELS))
def test_all_registered_models_have_plan_without_importing_model(tmp_path, model):
    profile = MODELS[model]
    items = tmp_path/'items.jsonl'
    items.write_text(json.dumps({'id': 'case'})+'\n')
    spec = dict(items=str(items), data_root='remote_source', compact='remote_states', model=model,
                model_dir='remote_weights', frames=profile.frames, fps=profile.fps,
                sam3='remote_sam', checkpoint='remote_checkpoint',
                generation_runtime={name: 'registered_'+name for name in profile.needs})
    plan = phyediting.execution_plan(spec)
    assert plan['registered'] == 1 and plan['model_runner'] == profile.runner
    assert plan['conditioning_mode'] == profile.mode
    assert plan['execution_requested'] is False and plan['gpu_started'] is False


def test_registered_clock_and_resources_rejected_before_generation(tmp_path):
    spec = dict(model='physrvg_ti2v5b', model_dir='weights', frames=49, fps=15)
    with pytest.raises(ValueError, match='code_dir, lora_dir'):
        validate_registration(spec)
    spec['generation_runtime'] = dict(code_dir='code', lora_dir='lora')
    spec['fps'] = 16
    with pytest.raises(ValueError, match='49 frames at 15 fps'):
        validate_registration(spec)


def test_wan_ti2v_checkpoint_does_not_silently_accept_t2v_mode():
    spec = dict(model='wan_ti2v5b', frames=121, fps=24, conditioning_mode='t2v')
    with pytest.raises(ValueError, match='conditioning mode is i2v; requested t2v'):
        validate_registration(spec)
    spec['conditioning_mode'] = 'i2v'
    assert validate_registration(spec).mode == 'i2v'


def test_explicit_external_runner_remains_available(tmp_path):
    items = tmp_path/'items.jsonl'
    items.write_text(json.dumps({'id': 'case'})+'\n')
    spec = dict(items=str(items), data_root='source', compact='states', model='external_registered_model',
                model_dir='weights', frames=48, fps=12, sam3='sam', checkpoint='checkpoint',
                generation_command=['python3', 'runner.py', '--manifest', '{manifest}'])
    assert phyediting.execution_plan(spec)['model_runner'] == 'custom_argv'
    del spec['frames']
    with pytest.raises(ValueError, match='requires explicit frames and fps'):
        phyediting.execution_plan(spec)


@pytest.mark.parametrize('model', ['cosmos', 'dynamicrafter_i2v', 'videogpa_ti2v5b',
                                   'physrvg_ti2v5b', 'cosmos3_nano', 'wan22_i2v_a14b',
                                   'physalign_wan22_i2v_a14b', 'minimax_h3'])
def test_legacy_models_have_argv_adapter_without_shell(tmp_path, model):
    profile = MODELS[model]
    runtime = {name: str(tmp_path/name) for name in profile.needs}
    spec = dict(model=model, model_dir='weights', generation_runtime=runtime)
    prompt = tmp_path/'prompt.txt'
    prompt.write_text('registered prompt')
    row = dict(sample_id='case', prompt_file=str(prompt), condition_image='registered.png', seed=42,
               gen_width=832, gen_height=480)
    commands, raw = adapter._command(spec, profile, tmp_path/'eligible.jsonl', tmp_path,
                                      'python3', 'ffmpeg', [row])
    assert commands and all(isinstance(c, list) and c[0] == 'python3' for c in commands)
    assert all(not any('&&' in token or ';' in token for token in c) for c in commands)
    assert raw is None or model == 'videogpa_ti2v5b'
    if model == 'physrvg_ti2v5b':
        assert 'static_frame' in commands[0]
    if model == 'physalign_wan22_i2v_a14b':
        assert '--physalign-adapter-dir' in commands[0]


def test_cosmos_condition_video_contains_only_declared_frame(tmp_path):
    image = np.full((64, 80, 3), 173, dtype=np.uint8)
    image[20:30, 30:40] = 20
    path = tmp_path/'condition.png'
    assert cv2.imwrite(str(path), image)
    video = tmp_path/'condition_only.mp4'
    adapter._condition_video(dict(condition_image=str(path), source_sample_fps=30), video)
    assert validate_video(video, fps=30, frames=1, width=80, height=64)['full_decode']
    cap = cv2.VideoCapture(str(video))
    assert cap.read()[0]
    assert not cap.read()[0]
    cap.release()


def test_missing_registered_assets_keep_per_row_failure_before_model(tmp_path, monkeypatch):
    profile = MODELS['dynamicrafter_i2v']
    spec = dict(model='dynamicrafter_i2v', model_dir=str(tmp_path/'absent_weights'),
                frames=profile.frames, fps=profile.fps,
                generation_runtime=dict(code_dir=str(tmp_path/'absent_code')))
    manifest = tmp_path/'eligible.jsonl'
    manifest.write_text(json.dumps(dict(sample_id='a'))+'\n'+json.dumps(dict(sample_id='b'))+'\n')
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *a, **kw: pytest.fail('must not launch model'))
    assert adapter.run(spec, manifest, tmp_path) == 1
    statuses = [json.loads(line) for line in (tmp_path/'registered_model_status.jsonl').read_text().splitlines()]
    assert [r['sample_id'] for r in statuses] == ['a', 'b']
    assert all(r['status'] == 'failed_before_model' and 'registered_model_dir_missing' in r['reason'] for r in statuses)


def _video(path, frames, fps):
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (80, 64))
    assert writer.isOpened()
    for index in range(frames):
        writer.write(np.full((64, 80, 3), (index % 90) + 90, np.uint8))
    writer.release()


def test_legacy_adapter_seals_only_full_media_and_preserves_attempt(tmp_path, monkeypatch):
    source = tmp_path/'source.mp4'
    _video(source, 30, 30)
    row = dict(sample_id='case', out_dir=str(tmp_path/'case'),
               generated_video=str(tmp_path/'case/raw.mp4'),
               generated_video_resized_to_source=str(tmp_path/'case/resized.mp4'),
               source_video=str(source), source_video_sha256=sha256(source),
               source_width=80, source_height=64, num_frames=16, output_fps=10)
    for name in ('condition_image', 'prompt_file', 'negative_prompt_file'):
        path = tmp_path/name
        path.write_text(name)
        row[name] = str(path)
    manifest = tmp_path/'eligible.jsonl'
    manifest.write_text(json.dumps(row)+'\n')
    spec = dict(model='dynamicrafter_i2v', frames=16, fps=10, model_dir='registered_checkpoint',
                generation_runtime=dict(code_dir='registered_repo'))
    monkeypatch.setattr(adapter, '_preflight', lambda *a: (sys.executable, 'ffmpeg', {}))
    monkeypatch.setattr(adapter, '_command', lambda *a: ([['registered_runner']], None))
    def invoke(*args, **kwargs):
        _video(Path(row['generated_video']), 16, 10)
        _video(Path(row['generated_video_resized_to_source']), 16, 10)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(adapter.subprocess, 'run', invoke)
    assert adapter.run(spec, manifest, tmp_path) == 0
    assert verified_completion(row)['media']['full_decode']
    assert (tmp_path/'case/generation.claim').is_file()
    status = json.loads((tmp_path/'registered_model_status.jsonl').read_text().splitlines()[-1])
    assert status['status'] == 'complete'
    Path(row['generated_video_resized_to_source']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        verified_completion(row)


def test_cosmos_runner_never_passes_future_reference_video(tmp_path, monkeypatch):
    from physedit.runners import cosmos_predict2
    row = dict(sample_id='case', source_video='/reference/full_future.mp4',
               conditioning_video='/registered/condition_only.mp4', source_sample_fps=30,
               source_width=80, source_height=64, out_dir=str(tmp_path/'case'),
               generated_video=str(tmp_path/'case/raw.mp4'),
               generated_video_resized_to_source=str(tmp_path/'case/resized.mp4'),
               prompt_file='prompt', negative_prompt_file='negative', output_fps=16,
               num_frames=81, seed=17, cosmos_predict2_condition_frames=1)
    manifest = tmp_path/'manifest.jsonl'
    manifest.write_text(json.dumps(row)+'\n')
    seen = []
    def invoke(command, **kwargs):
        seen.extend(command)
        Path(row['generated_video']).write_bytes(b'fake model output')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(cosmos_predict2.subprocess, 'run', invoke)
    monkeypatch.setattr(cosmos_predict2, '_resize_to_source', lambda *a, **kw:
                        Path(row['generated_video_resized_to_source']).write_bytes(b'fake resized output'))
    monkeypatch.setattr(sys, 'argv', ['cosmos_predict2.py', '--generation-manifest', str(manifest),
                                       '--cosmos-tools', str(tmp_path), '--python', 'python3',
                                       '--model-dir', str(tmp_path)])
    assert cosmos_predict2.main() == 0
    assert seen[seen.index('--video_path')+1] == row['conditioning_video']
    assert row['source_video'] not in seen
    assert seen[seen.index('--num_conditional_frames')+1] == '1'
    assert seen[seen.index('--seed')+1] == '17'


@pytest.mark.parametrize('key', ['mode', 'conditioning_mode'])
@pytest.mark.parametrize('model', [*sorted(MODELS), 'external_registered_model'])
def test_oneclick_refuses_t2v_even_for_external_commands(tmp_path, model, key):
    items = tmp_path/'items.jsonl'
    items.write_text('{"id":"case"}\n')
    spec = dict(items=str(items), data_root='source', compact='states', model=model,
                model_dir='weights', frames=81, fps=16, sam3='sam', checkpoint='checkpoint',
                generation_command=['external_runner'], **{key: 't2v'})
    with pytest.raises(ValueError, match='conditioning mode|pure T2V'):
        phyediting.execution_plan(spec)


@pytest.mark.parametrize('model', ['ltx_i2v', 'cogvideox_i2v', 'wan_ti2v5b', 'hunyuan15_i2v'])
def test_diffusers_uses_registered_runtime_without_loading_models(tmp_path, model):
    weights = tmp_path/'weights'
    weights.mkdir()
    python = tmp_path/'model_python'
    python.write_text('registered executable fixture')
    ffmpeg = tmp_path/'media_bin'/'ffmpeg'
    ffmpeg.parent.mkdir()
    ffmpeg.write_text('registered media fixture')
    spec = dict(model=model, model_dir=str(weights), generation_runtime=dict(
        python=str(python), ffmpeg=str(ffmpeg), gpu_devices='3', pythonpath=[str(tmp_path/'site')]))
    command, env = phyediting.diffusers_launch(spec, tmp_path/'manifest.jsonl')
    assert command[0] == str(python)
    assert env['CUDA_VISIBLE_DEVICES'] == '3'
    assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1'
    assert env['PATH'].split(':')[0] == str(ffmpeg.parent)
    assert env['IMAGEIO_FFMPEG_EXE'] == str(ffmpeg)
    assert str(tmp_path/'site') in env['PYTHONPATH'].split(':')
    assert command[command.index('--model-dir')+1] == str(weights)


def test_registered_python_preserves_real_virtual_environment(tmp_path):
    environment = tmp_path/'model_env'
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = environment/'bin/python'
    weights = tmp_path/'weights'
    weights.mkdir()
    spec = dict(model='hunyuan15_i2v', model_dir=str(weights), generation_runtime=dict(
        python=str(python), ffmpeg=sys.executable))
    command, _ = phyediting.diffusers_launch(spec, tmp_path/'manifest')
    prefix = subprocess.check_output([command[0], '-I', '-c', 'import sys; print(sys.prefix)'], text=True).strip()
    assert Path(prefix) == environment
    assert command[0] == str(python)



def test_legacy_launch_error_is_retained_instead_of_missing_output(tmp_path,monkeypatch):
    spec=dict(model='dynamicrafter_i2v',model_dir='fixture',frames=16,fps=10,generation_runtime=dict(code_dir='fixture'))
    row=dict(sample_id='x',out_dir=str(tmp_path/'x'),generated_video=str(tmp_path/'x/raw.mp4'),
             generated_video_resized_to_source=str(tmp_path/'x/resized.mp4'),source_width=80,source_height=64,num_frames=16,output_fps=10)
    for name in ['condition_image','prompt_file','negative_prompt_file']:
        p=tmp_path/name;p.write_text('fixture');row[name]=str(p)
    manifest=tmp_path/'rows';manifest.write_text(json.dumps(row)+'\n')
    monkeypatch.setattr(adapter,'_preflight',lambda *a:('python','ffmpeg',{}))
    monkeypatch.setattr(adapter,'_command',lambda *a:([['fixture']],None))
    def fail(*a,**kw):
        kw['stdout'].write("KeyError: 'before_encode'\n")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(adapter.subprocess,'run',fail)
    assert adapter.run(spec,manifest,tmp_path)==1
    status=json.loads((tmp_path/'registered_model_status.jsonl').read_text().splitlines()[-1])
    assert "KeyError: 'before_encode'" in status['reason']
    assert 'missing_source_video' not in status['reason']
