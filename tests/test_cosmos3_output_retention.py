"""Failed Cosmos3 exports remain available and cannot be silently rerun."""
import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest


def runner_functions():
    tree = ast.parse(Path('physedit/runners/cosmos3.py').read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    namespace = dict(argparse=argparse, datetime=datetime, json=json, os=os,
                     pathlib=__import__('pathlib'), subprocess=subprocess, time=time)
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'cosmos3_runner', 'exec'), namespace)
    return namespace


@pytest.mark.parametrize('existing', range(4))
def test_existing_raw_resized_or_partial_is_retained(tmp_path, existing):
    ns = runner_functions()
    paths = [tmp_path/name for name in ('raw.mp4', 'resized.mp4', 'raw.incomplete.mp4', 'resized.incomplete.mp4')]
    paths[existing].write_bytes(b'original incomplete evidence')
    with pytest.raises(FileExistsError, match='retained_no_overwrite'):
        ns['claim_generation'](*paths)
    assert paths[existing].read_bytes() == b'original incomplete evidence'
    assert not (tmp_path/'raw.mp4.claim').exists()


def test_exclusive_claim_rejects_second_writer(tmp_path):
    ns = runner_functions()
    paths = [tmp_path/name for name in ('raw.mp4', 'resized.mp4', 'raw.incomplete.mp4', 'resized.incomplete.mp4')]
    ns['claim_generation'](*paths)
    claim = (tmp_path/'raw.mp4.claim').read_bytes()
    with pytest.raises(FileExistsError):
        ns['claim_generation'](*paths)
    assert (tmp_path/'raw.mp4.claim').read_bytes() == claim


def test_failed_export_keeps_partial_and_second_invocation_does_not_generate(tmp_path, monkeypatch):
    ns = runner_functions()
    calls = []

    class Pipe:
        scheduler = SimpleNamespace(config={})

        def __call__(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(video='fixture')

    def export(video, path, **kwargs):
        Path(path).write_bytes(b'original export stopped here')
        raise RuntimeError('intentional export failure')

    ns.update(Cosmos3OmniPipeline=SimpleNamespace(from_pretrained=lambda *a, **kw: Pipe()),
              UniPCMultistepScheduler=SimpleNamespace(from_config=lambda *a, **kw: SimpleNamespace(config={})),
              torch=SimpleNamespace(bfloat16='bf16', Generator=lambda **kw: SimpleNamespace(manual_seed=lambda seed: ('seed', seed))),
              load_image=lambda path: ('condition_image', path), export_to_video=export)
    prompt = tmp_path/'prompt.txt'
    negative = tmp_path/'negative.txt'
    prompt.write_text('An object moves on the table.')
    negative.write_text('camera motion')
    row = dict(sample_id='case', generated_video=str(tmp_path/'raw.mp4'),
               generated_video_resized_to_source=str(tmp_path/'resized.mp4'),
               prompt_file=str(prompt), negative_prompt_file=str(negative),
               condition_image='condition.png', gen_width=832, gen_height=480,
               num_frames=189, output_fps=24, seed=20261008)
    manifest = tmp_path/'manifest.jsonl'
    manifest.write_text(json.dumps(row)+'\n')
    monkeypatch.setattr(sys, 'argv', ['cosmos3', '--model', 'weights', '--manifest', str(manifest),
        '--node', 'fixture', '--status-jsonl', str(tmp_path/'status.jsonl'),
        '--state-json', str(tmp_path/'state.json'), '--ffmpeg', 'ffmpeg'])
    with pytest.raises(SystemExit, match='intentional export failure'):
        ns['main']()
    partial = tmp_path/'raw.incomplete.mp4'
    assert partial.read_bytes() == b'original export stopped here'
    assert len(calls) == 1
    assert calls[0]['num_frames'] == 189 and calls[0]['num_inference_steps'] == 35
    assert calls[0]['fps'] == 24 and calls[0]['guidance_scale'] == 6.0
    assert calls[0]['image'] == ('condition_image', 'condition.png')
    with pytest.raises(SystemExit, match='existing_output_or_partial_retained'):
        ns['main']()
    assert len(calls) == 1
    assert partial.read_bytes() == b'original export stopped here'
    assert all(json.loads(line)['state'] == 'failed' for line in (tmp_path/'status.jsonl').read_text().splitlines())
