"""Execution policy controls preserve the registered sampler and default behavior."""
import sys
from types import SimpleNamespace

import pytest

from physedit import phyediting
from physedit.runners import diffusers_i2v, oneclick_registry


@pytest.mark.parametrize('model,default', [('ltx_i2v', 'model'), ('hunyuan15_i2v', 'sequential')])
def test_explicit_memory_policy_reaches_runner_without_changing_sampler(tmp_path, monkeypatch, model, default):
    monkeypatch.setattr('physedit.runners.registered_oneclick._preflight', lambda *a: ('python', 'ffmpeg', {}))
    spec = {'model': model, 'model_dir': str(tmp_path)}
    before, _ = phyediting.diffusers_launch(spec, tmp_path/'manifest.jsonl')
    assert before[before.index('--offload-mode')+1] == default
    after, _ = phyediting.diffusers_launch({**spec, 'generation_runtime':
        {'offload_mode': 'none', 'attention_slicing': False}}, tmp_path/'manifest.jsonl')
    expected = before.copy()
    expected[expected.index('--offload-mode')+1] = 'none'
    assert after == expected + ['--attention-slicing', 'off']


@pytest.mark.parametrize('field,value', [('offload_mode', 'invalid'), ('attention_slicing', 'false'),
                                       ('attention_slicing', 0)])
def test_invalid_memory_controls_rejected_during_registration(field, value):
    spec = dict(model='ltx_i2v', frames=161, fps=25, generation_runtime={field: value})
    with pytest.raises(ValueError, match=field):
        oneclick_registry.validate_registration(spec)


@pytest.mark.parametrize('field,value', [('offload_mode', 'none'), ('attention_slicing', False)])
def test_other_runners_do_not_silently_ignore_diffusers_controls(field, value):
    spec = dict(model='minimax_h3', frames=124, fps=24, generation_runtime={field: value})
    with pytest.raises(ValueError, match=field):
        oneclick_registry.validate_registration(spec)


@pytest.mark.parametrize('model,frames,fps', [('ltx_i2v', 161, 25), ('hunyuan15_i2v', 121, 24)])
def test_group_offload_is_not_silently_replaced_by_model_offload(model, frames, fps):
    spec = dict(model=model, frames=frames, fps=fps, generation_runtime={'offload_mode': 'group'})
    with pytest.raises(ValueError, match='only available for Wan'):
        oneclick_registry.validate_registration(spec)
    with pytest.raises(ValueError, match='only available for Wan'):
        diffusers_i2v._load_pipeline(model, 'weights', 'bfloat16', 'group', None)


@pytest.mark.parametrize('enabled', [True, False])
def test_attention_policy_keeps_original_pipeline_processor_when_disabled(monkeypatch, enabled):
    calls = []
    class Pipe:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls.append(('load', path, kwargs))
            return cls()
        def __call__(self, image):
            pass
        def to(self, device):
            calls.append(('device', device))
        def enable_attention_slicing(self):
            calls.append(('slicing',))
    monkeypatch.setitem(sys.modules, 'diffusers', SimpleNamespace(LTXImageToVideoPipeline=Pipe))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(bfloat16='bf16', float16='fp16'))
    diffusers_i2v._load_pipeline('ltx_i2v', 'weights', 'bfloat16', 'none', None, enabled)
    assert calls[:2] == [('load', 'weights', {'torch_dtype': 'bf16', 'local_files_only': True}),
                         ('device', 'cuda')]
    assert (('slicing',) in calls) == enabled


def test_h3_performance_metadata_uses_actual_canvas():
    import ast
    from pathlib import Path

    source = Path("physedit/runners/minimax_h3.py").read_text()
    tree = ast.parse(source)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "output_row"]
    namespace = {"H3_WIDTH": 896, "H3_HEIGHT": 512, "pathlib": __import__("pathlib")}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "h3_output_row", "exec"), namespace)
    row = {"source_sample_id": "case", "prompt_granularity": "fine", "index": 0,
           "condition_image": "image.png", "prompt_file": "prompt.txt", "seed": 42,
           "source_width": 1280, "source_height": 720}
    output = namespace["output_row"](row, Path("raw.mp4"), Path("resized.mp4"))
    assert output["h3_resolution"] == {"width": 896, "height": 512}
    custom = namespace["output_row"]({**row, "gen_width": 768, "gen_height": 432}, Path("raw.mp4"), Path("resized.mp4"))
    assert custom["h3_resolution"] == {"width": 768, "height": 432}
    assert output["num_frames"] == 124 and output["output_fps"] == 24
    assert '"resolution": "960x544"' not in source


@pytest.mark.parametrize("model,policy", [("ltx_i2v", "resident-denoiser"), ("minimax_h3", "unknown")])
def test_h3_residency_policy_rejects_other_models_and_unknown_values(model, policy):
    profile = oneclick_registry.contract(model)
    with pytest.raises(ValueError, match="minimax_memory_policy"):
        oneclick_registry.validate_registration(dict(model=model, frames=profile.frames, fps=profile.fps,
            generation_runtime={"minimax_memory_policy": policy}))


def test_h3_residency_reaches_oneclick_argv_and_preserves_default(tmp_path):
    from physedit.runners import registered_oneclick
    spec = dict(model="minimax_h3", model_dir=str(tmp_path), frames=124, fps=24)
    profile = oneclick_registry.validate_registration(spec)
    before, _ = registered_oneclick._command(spec, profile, tmp_path/"manifest", tmp_path, "python", "ffmpeg", [])
    requested = {**spec, "generation_runtime": {"minimax_memory_policy": "resident-denoiser"}}
    oneclick_registry.validate_registration(requested)
    after, _ = registered_oneclick._command(requested, profile, tmp_path/"manifest", tmp_path, "python", "ffmpeg", [])
    assert after == [before[0] + ["--memory-policy", "resident-denoiser"]]


def test_h3_residency_rejects_multiple_gpus_before_any_placement(monkeypatch):
    from physedit.runners.minimax_memory import configure_resident_denoiser
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(device_count=lambda: 2)))
    monkeypatch.setitem(sys.modules, "accelerate", SimpleNamespace(cpu_offload=None, cpu_offload_with_hook=None))
    with pytest.raises(ValueError, match="exactly one"):
        configure_resident_denoiser(None, None)


def test_h3_residency_rejects_inadequate_capacity_before_disabling_manager(monkeypatch):
    from physedit.runners.minimax_memory import configure_resident_denoiser
    class Module:
        def parameters(self):
            return [SimpleNamespace(numel=lambda: 8 * 1024**3, element_size=lambda: 2)]
    encoder = type("Qwen3VLForConditionalGeneration", (), {})()
    manager = SimpleNamespace(disable_auto_cpu_offload=lambda: pytest.fail("manager changed before capacity check"))
    conditioner = SimpleNamespace(text_encoder=encoder, _components_manager=manager)
    generator = SimpleNamespace(_components_manager=manager, components={key: Module() for key in ("transformer", "vae", "audio_vae")})
    torch = SimpleNamespace(nn=SimpleNamespace(Module=Module), cuda=SimpleNamespace(device_count=lambda: 1,
        get_device_properties=lambda _: SimpleNamespace(total_memory=24*1024**3)))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "accelerate", SimpleNamespace(cpu_offload=None, cpu_offload_with_hook=None))
    with pytest.raises(ValueError, match="16 GiB"):
        configure_resident_denoiser(conditioner, generator)


def test_explicit_wan_group_request_does_not_silently_change_policy(monkeypatch):
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(device=lambda name: name))
    monkeypatch.setitem(sys.modules, 'diffusers.hooks', SimpleNamespace(apply_group_offloading=None))
    calls = []
    pipe = SimpleNamespace(transformer=object(), vae=None,
        enable_sequential_cpu_offload=lambda: calls.append('sequential'),
        enable_model_cpu_offload=lambda: calls.append('model'))
    with pytest.raises(ValueError, match='requested group offload'):
        diffusers_i2v._enable_wan_offload(pipe, 'group', strict=True)
    assert calls == []


def test_videogpa_missing_requested_adapter_cannot_become_faster_base_model(tmp_path):
    import ast
    from pathlib import Path
    tree = ast.parse(Path('physedit/runners/videogpa_wan22.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate']
    torch = SimpleNamespace(cuda=SimpleNamespace(set_device=lambda *_: pytest.fail('GPU initialized before adapter validation')))
    namespace = {'torch': torch, 'Path': Path}
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'videogpa_generate', 'exec'), namespace)
    with pytest.raises(FileNotFoundError, match='adapter missing adapter_config.json'):
        namespace['generate'](SimpleNamespace(lora_path=str(tmp_path/'missing'), gpu_id=0))


def test_dynamicrafter_records_inference_group_time_separately_from_postprocessing(tmp_path, monkeypatch):
    import json
    import shutil
    from pathlib import Path
    from physedit.runners import dynamicrafter
    repo = tmp_path/'repo'
    for name in ['scripts/evaluation/inference.py', 'configs/inference_1024_v1.0.yaml']:
        file = repo/name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('fixture')
    checkpoint = tmp_path/'model.ckpt'
    checkpoint.write_bytes(b'fixture')
    image, prompt = tmp_path/'image.png', tmp_path/'prompt.txt'
    image.write_bytes(b'fixture')
    prompt.write_text('move')
    raw, resized = tmp_path/'raw.mp4', tmp_path/'resized.mp4'
    manifest = tmp_path/'rows.jsonl'
    manifest.write_text(json.dumps(dict(sample_id='case', condition_image=str(image), prompt_file=str(prompt),
        seed=42, source_video='source.mp4', source_width=16, source_height=16,
        generated_video=str(raw), generated_video_resized_to_source=str(resized)))+'\n')
    clock = [100.]
    monkeypatch.setattr(dynamicrafter.time, 'time', lambda: clock[0])
    def inference(command, **kwargs):
        target = Path(command[command.index('--savedir')+1])/'samples_separate'
        target.mkdir(parents=True)
        inputs = Path(command[command.index('--prompt_dir')+1])
        for p in inputs.glob('*.png'):
            (target/(p.stem+'_sample0.mp4')).write_bytes(b'fixture')
        clock[0] += 20
        return SimpleNamespace(returncode=0)
    def reclock(source, output, fps):
        shutil.copyfile(source, output)
        clock[0] += 3
    monkeypatch.setattr(dynamicrafter.subprocess, 'run', inference)
    monkeypatch.setattr(dynamicrafter, '_reclock_native_frames', reclock)
    monkeypatch.setattr(dynamicrafter, '_resize_to_source', lambda source, reference, target, *a, **kw: shutil.copyfile(source, target))
    monkeypatch.setattr(sys, 'argv', ['dynamicrafter', '--generation-manifest', str(manifest),
        '--repo-dir', str(repo), '--checkpoint', str(checkpoint), '--startup-reserve-mib', '0'])
    assert dynamicrafter.main() == 0
    status = json.loads((tmp_path/'dynamicrafter_i2v_generation_status.jsonl').read_text())
    assert status['inference_group_elapsed_seconds'] == 20
    assert status['inference_group_samples'] == 1
    assert status['elapsed_seconds'] == 3
    assert status['elapsed_scope'] == 'postprocess_only'
