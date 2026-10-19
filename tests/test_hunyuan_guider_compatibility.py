"""Preserve the selected sampler across both Hunyuan guidance interfaces."""
from contextlib import nullcontext
from types import SimpleNamespace
import json
import sys

from PIL import Image
import pytest

from physedit.runners import diffusers_i2v as runner


class Guider:
    def __init__(self, scale=1.0):
        self.config = dict(guidance_scale=scale, guidance_rescale=0.0,
                           start=0.0, stop=1.0, enabled=True,
                           use_original_formulation=False)

    def new(self, **changes):
        other = Guider()
        other.config = {**self.config, **changes}
        return other


def test_checkpoint_cfg_one_keeps_the_actual_guider_instance():
    original = Guider(1.0)
    pipe = SimpleNamespace(guider=original)
    assert runner._bind_hunyuan_guider(pipe, 1.0) == original.config
    assert pipe.guider is original


def test_requested_scale_preserves_other_guidance_parameters():
    original = Guider(6.0)
    pipe = SimpleNamespace(guider=original)
    config = runner._bind_hunyuan_guider(pipe, 1.0)
    assert config == {**original.config, "guidance_scale": 1.0}
    assert original.config["guidance_scale"] == 6.0


def test_guider_must_apply_the_requested_scale():
    class Ignored(Guider):
        def new(self, **changes):
            return self
    with pytest.raises(ValueError, match="guidance_mismatch"):
        runner._bind_hunyuan_guider(SimpleNamespace(guider=Ignored(6)), 1)


def test_guider_cannot_change_rescaling_while_setting_cfg():
    class Changed(Guider):
        def new(self, **changes):
            other = super().new(**changes)
            other.config["guidance_rescale"] = 0.5
            return other
    with pytest.raises(ValueError, match="policy_changed"):
        runner._bind_hunyuan_guider(SimpleNamespace(guider=Changed(6)), 1)


def test_missing_guider_does_not_drop_cfg_silently():
    with pytest.raises(ValueError, match="guidance_unavailable"):
        runner._bind_hunyuan_guider(SimpleNamespace(), 1)


def prepare_call(tmp_path, monkeypatch):
    calls = []
    class Generator:
        def __init__(self, device):
            assert device == "cuda"
        def manual_seed(self, value):
            self.seed = value
            return self
    image = Image.new("RGB", (854, 480), "red")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        Generator=Generator, inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "diffusers.utils", SimpleNamespace(
        load_image=lambda path: image,
        export_to_video=lambda frames, path, fps: calls.append((frames, path, fps))))
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Two cans move across a table.")
    negative = tmp_path / "negative.txt"
    negative.write_text("camera motion")
    row = dict(prompt_file=str(prompt), negative_prompt_file=str(negative),
               condition_image="input.png", num_frames=121, gen_width=848,
               gen_height=480, output_fps=24, seed=20261008, sample_id="case")
    args = SimpleNamespace(pipeline="hunyuan15_i2v", model_dir="checkpoint",
                           height=None, width=None, num_inference_steps=12,
                           guidance_scale=1.0, num_frames=None, flow_shift=None,
                           wan_invert_output=False, attention_slicing="on")
    return args, row, image, calls


def test_new_api_gets_cfg_from_guider_without_changing_sampling(tmp_path, monkeypatch):
    args, row, image, exports = prepare_call(tmp_path, monkeypatch)
    class Pipeline:
        guider = Guider(1)
        target_size = 480
        video_processor = SimpleNamespace(calculate_default_height_width=lambda **kw: (480, 848))
        def __call__(self, image, prompt, negative_prompt, num_frames,
                     num_inference_steps, generator):
            assert self.guider.config["guidance_scale"] == 1
            assert image.size == (854, 480)
            assert (num_frames, num_inference_steps, generator.seed) == (121, 12, 20261008)
            return SimpleNamespace(frames=[[image]])
    log = tmp_path / "call.json"
    runner._generate_one(Pipeline(), args, row, tmp_path / "raw.mp4", log)
    metadata = json.loads(log.read_text())
    assert metadata["guidance_binding"] == "guider"
    assert metadata["guidance_scale"] == metadata["guider_config"]["guidance_scale"] == 1
    assert "guidance_scale" not in metadata["accepted_call_args"]
    assert exports[0][2] == 24


def test_legacy_api_keeps_explicit_guidance_argument(tmp_path, monkeypatch):
    args, row, image, _ = prepare_call(tmp_path, monkeypatch)
    class Pipeline:
        def __call__(self, image, prompt, negative_prompt, height, width,
                     num_frames, num_inference_steps, guidance_scale, generator):
            assert (height, width, num_frames, num_inference_steps) == (480, 848, 121, 12)
            assert guidance_scale == 1
            return SimpleNamespace(frames=[[image]])
    log = tmp_path / "call.json"
    runner._generate_one(Pipeline(), args, row, tmp_path / "raw.mp4", log)
    assert json.loads(log.read_text())["guidance_binding"] == "call_argument"


def test_new_api_refuses_a_different_native_canvas(tmp_path, monkeypatch):
    args, row, _, _ = prepare_call(tmp_path, monkeypatch)
    class Pipeline:
        guider = Guider(1)
        target_size = 720
        video_processor = SimpleNamespace(calculate_default_height_width=lambda **kw: (720, 1280))
        def __call__(self, image, num_frames, num_inference_steps):
            pytest.fail("mismatched canvas reached inference")
    with pytest.raises(ValueError, match="native_canvas_mismatch"):
        runner._generate_one(Pipeline(), args, row, tmp_path / "raw.mp4", tmp_path / "call.json")
