"""Evidence input binding and interrupted-process recovery, with no real models."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_evaluations import clip, judgement
from physedit import evaluations as ev, qwen_judge as judge
from physedit.judge_validation import validate_response
from physedit.judge_video import local_inputs


@pytest.mark.parametrize('fault', ['condition_alias', 'frame_index', 'time', 'sampling_fps', 'order', 'prompt', 'image_hash'])
@pytest.mark.parametrize('backend', ['api', 'local'])
def test_actual_judge_inputs_reject_registration_drift(tmp_path, clip, fault, backend):
    evidence = ev.qwen_evidence(clip[0], clip[1], tmp_path / 'e')
    if fault == 'condition_alias': evidence['condition_image'] = evidence['frames'][0]['path']
    if fault == 'frame_index': evidence['frames'][1]['frame_index'] += 1
    if fault == 'time': evidence['frames'][1]['time_seconds'] += .1
    if fault == 'sampling_fps': evidence['sampling_fps'] += 1
    if fault == 'order': evidence['frames'][1:3] = reversed(evidence['frames'][1:3])
    if fault == 'prompt': evidence['prompt_sha256'] = 'stale'
    if fault == 'image_hash': evidence['condition']['png_sha256'] = 'stale'
    class NoProcessor:
        def apply_chat_template(self, *a, **kw): pytest.fail('drift must fail before processor')
    with pytest.raises(ValueError, match='judge_'):
        judge.messages(evidence) if backend == 'api' else local_inputs(NoProcessor(), evidence, 'unused')


@pytest.mark.parametrize('duplicate', ['confidence', 'evidence_frames'])
def test_ambiguous_duplicate_json_answer_never_scores(duplicate):
    raw = json.dumps(judgement())
    raw = raw.replace('"confidence": 0.9', '"confidence": 0.1, "confidence": 0.9') if duplicate == 'confidence' else raw.replace('"evidence_frames": [0, 47]', '"evidence_frames": [0, 1], "evidence_frames": [0, 47]', 1)
    with pytest.raises(ValueError, match='duplicate_json_key'):
        validate_response(raw, {'frames': [{'frame_index': 0}, {'frame_index': 47}]})


def test_child_killed_during_second_response_preserves_first(tmp_path, clip, monkeypatch):
    row, _, item, _ = clip
    second = dict(row, sample_id='second')
    # Isolate only input completion lookup; actual PNG/video evidence is still used.
    ctx = clip[1]
    monkeypatch.setattr(ev, 'context', lambda value: copy.deepcopy(ctx))
    calls = []
    def interrupted(command, **kwargs):
        calls.append(command)
        output = Path(command[command.index('--output') + 1])
        output.write_text(json.dumps(dict(sample_id='valid', status='ok', judgement=judgement(), raw=json.dumps(judgement()), served_model='fixture')) + '\n{"sample_id":"second","raw":')
        return SimpleNamespace(returncode=-9)
    monkeypatch.setattr(ev.subprocess, 'run', interrupted)
    config = dict(metrics=['qwen'], qwen=dict(backend='local', model='fixture', model_dir='/fixture'))
    result = ev.run_additional({'evaluation': config}, [row, second], {'i': item}, {}, tmp_path/'out')
    records = ev.read_rows(tmp_path/'out/qwen_results.jsonl')
    assert len(calls) == 1 and result['qwen']['registered'] == 2
    assert records[0]['status'] == 'ok' and records[0]['local_process_returncode'] == -9
    assert records[1]['status'] == 'failed' and 'missing_complete' in records[1]['reason']
    assert result['qwen']['scored'] == 1
    assert json.loads((tmp_path/'out/local_qwen_exit.json').read_text())['incomplete_tail_retained']


@pytest.mark.parametrize('fault', ['clean_exit_bad_json', 'duplicate_id', 'unknown_id', 'middle_invalid'])
def test_corrupt_local_response_identity_does_not_pass(tmp_path, fault):
    p = tmp_path/'responses.jsonl'
    good = json.dumps(dict(sample_id='one', status='ok'))
    text, rc = good + '\n{', 0
    if fault == 'duplicate_id': text, rc = good + '\n' + good, -9
    if fault == 'unknown_id': text, rc = good + '\n' + json.dumps(dict(sample_id='other')), 0
    if fault == 'middle_invalid': text, rc = '{\n' + good, -9
    p.write_text(text)
    with pytest.raises(ValueError): ev.read_local_responses(p, {'one'}, rc)


def test_bad_late_mask_shape_keeps_earlier_frames_and_empty_side(tmp_path):
    import hashlib
    import numpy as np
    from physedit.mask_evidence import export_masks, load_sequence
    observations = tmp_path/'observed'
    folder = observations/'runs/sam31_visible_projection_full30_masks';folder.mkdir(parents=True)
    ctx = dict(condition_frame=0, source_frames=3, generated_frames=3, source_fps=16, generated_fps=16,
               source_sha256='source', generated_sha256='generated')
    row = dict(sample_id='case', item_id='item', source_width=10, source_height=8)
    measures = []
    for kind in ('source', 'generated'):
        jid = 'case__vp_' + kind;hashes={}
        if kind == 'generated':
            for f in range(3):
                mask = np.ones((8,10) if f < 2 else (9,10), dtype=np.uint8)
                np.savez_compressed(folder/(hashlib.sha256(jid.encode()).hexdigest()[:12]+'_'+str(f)+'.npz'), mask=mask)
                hashes[str(f)] = hashlib.sha256(mask.tobytes()).hexdigest()
        measures.append(dict(id=jid, frames=[0,1,2], statuses=['missing_actual_mask']*3 if kind=='source' else ['ok']*3,
                             video_sha256=kind, mask_sha256=hashes))
    (observations/'measurements_v4.jsonl').write_text(''.join(json.dumps(m)+'\n' for m in measures))
    root=tmp_path/'export';root.mkdir()
    entries, failures = export_masks([row], {'case':ctx}, {'item':{'object_name':'can'}}, root, observations)
    assert 'shape_mismatch' in failures['case']
    source, _ = load_sequence(entries['case']['source'],ctx,'source','can',(10,8))
    generated, _ = load_sequence(entries['case']['generated'],ctx,'generated','can',(10,8))
    assert source == [None]*3
    assert all(x is not None for x in generated[:2]) and generated[2] is None


def test_corrupt_child_output_still_retains_actual_exit(tmp_path, clip, monkeypatch):
    row, _, item, _ = clip
    def corrupt(command, **kwargs):
        Path(command[command.index('--output') + 1]).write_text('{invalid}\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(ev.subprocess, 'run', corrupt)
    config = dict(metrics=['qwen'], qwen=dict(backend='local', model='fixture', model_dir='/fixture'))
    result = ev.run_additional({'evaluation':config}, [row], {'i':item}, {}, tmp_path/'out')
    assert result['qwen']['failed'] == 1
    assert json.loads((tmp_path/'out/local_qwen_exit.json').read_text())['returncode'] == 0
    assert (tmp_path/'out/local_qwen_responses.jsonl').read_text() == '{invalid}\n'
