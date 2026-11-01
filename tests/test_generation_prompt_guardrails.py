"""Prompt policy regressions using synthetic inputs, never released task edits."""
import copy
import json
import sys
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest

from physedit import prompt_contract as contract
from physedit.runners import diffusers_i2v as runner


def test_old_captions_cannot_bypass_structured_physical_inputs():
    with pytest.raises(ValueError, match='structured_english_prompt_upgrade_required'):
        contract.from_item(dict(gravity=9.81, generation_prompt='A book moves.'))
    with pytest.raises(ValueError, match='english_prompt_task_upgrade_required'):
        contract.from_gravity_task(dict(generation_prompt='old-caption.txt'), {}, {})


def test_three_declared_variants_keep_their_text_and_parameter_hash_bindings():
    facts = [['gravity', '', 1.62, 'm/s^2'],
             ['book.initial_velocity', '', [1.1, 0.2, 0.3], 'm/s']]
    texts = [contract.render_facts(facts, variant=v) for v in (1, 2, 3)]
    item = dict(generation_parameter_facts=facts,
                generation_parameter_facts_sha256=contract.parameter_facts_sha(facts),
                generation_prompt_variants_en=texts,
                generation_prompt_variant_sha256=[contract.sha(t) for t in texts])
    assert len(set(texts)) == 3
    for variant, text in enumerate(texts, 1):
        assert contract.from_item({**item, 'prompt_variant': variant}) == text
        assert 'Gravity 1.62 m/s^2.' in text
        assert 'Book initial velocity [1.1,0.2,0.3] m/s.' in text
    changed = copy.deepcopy(item)
    changed['generation_parameter_facts'][0][2] = 9.81
    with pytest.raises(ValueError, match='parameter_binding_mismatch'):
        contract.from_item(changed)
    changed = copy.deepcopy(item)
    changed['generation_prompt_variants_en'][0] += ' Changed text.'
    with pytest.raises(ValueError, match='text_binding_mismatch'):
        contract.from_item(changed)


@pytest.mark.parametrize('tokens', [128, 129])
def test_ltx_token_budget_is_checked_without_silent_truncation(tmp_path, monkeypatch, tokens):
    calls = []
    class Generator:
        def __init__(self, device):
            pass
        def manual_seed(self, seed):
            return self
    class Pipeline:
        @staticmethod
        def tokenizer(text, *, add_special_tokens, truncation):
            assert text == 'Registered physical inputs.'
            assert add_special_tokens is True and truncation is False
            return {'input_ids': list(range(tokens))}
        def __call__(self, prompt, image, num_frames, num_inference_steps,
                     guidance_scale, frame_rate, max_sequence_length, generator):
            calls.append(prompt)
            assert max_sequence_length == 128
            return SimpleNamespace(frames=[np.zeros((2, 2, 3), dtype=np.uint8)])
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        Generator=Generator, inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'diffusers.utils', SimpleNamespace(
        load_image=lambda _: object(), export_to_video=lambda *a, **kw: None))
    prompt = tmp_path/'prompt.txt'
    prompt.write_text('Registered physical inputs.', encoding='utf8')
    negative = tmp_path/'negative.txt'
    negative.write_text('camera motion', encoding='utf8')
    row = dict(sample_id='synthetic', condition_image='fixture.png',
               prompt_file=str(prompt), negative_prompt_file=str(negative),
               source_width=80, source_height=64, num_frames=5, output_fps=25, seed=0)
    args = SimpleNamespace(pipeline='ltx_i2v', model_dir='fixture', height=None, width=None,
        num_frames=None, num_inference_steps=None, guidance_scale=None, wan_invert_output=False)
    generate = lambda: runner._generate_one(Pipeline(), args, row,
        tmp_path/'out.mp4', tmp_path/'call.json')
    if tokens > 128:
        with pytest.raises(ValueError, match='prompt_exceeds_registered_budget'):
            generate()
        assert calls == []
    else:
        generate()
        assert calls == ['Registered physical inputs.']
        assert json.loads((tmp_path/'call.json').read_text())['prompt_tokens'] == tokens
