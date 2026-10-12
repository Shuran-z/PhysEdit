"""Reference eligibility must precede generation and never depend on its result."""
import copy
import json
from types import SimpleNamespace

import pytest

from physedit.inversion_inputs import assess
from scripts import phyediting_gen as gen
from test_generation_pipeline import item, dump, reference_evidence, video


@pytest.mark.parametrize('change,reason', [
    ('missing', 'missing_reference_applicability_evidence'),
    ('digest', 'reference_applicability_sha256_mismatch'),
    ('window', 'registered_reference_item_changed'),
    ('geometry', 'registered_reference_item_changed'),
    ('camera', 'registered_reference_item_changed'),
    ('not_registered', 'missing_verified_reference_item'),
    ('unsupported_model', 'reference_motion_not_supported_by_frozen_generation_score'),
    ('reference_failure', 'reference_inversion_not_valid'),
    ('reference_target', 'reference_prediction_gravity_identity_mismatch'),
    ('short_generation', 'generation_clock_does_not_cover_reference_window'),
])
def test_rejects_before_decoding_or_neural_inference(tmp_path, monkeypatch, change, reason):
    i = item()
    evidence = reference_evidence(tmp_path, [i])
    registered = copy.deepcopy(i)
    frames = 81
    if change == 'missing': evidence = None
    if change == 'digest': evidence['benchmark_sha256'] = 'wrong'
    if change == 'window': registered['window']['start_frame'] += 1
    if change == 'geometry': registered['object']['position'] = [0,0,0]
    if change == 'camera': registered['camera']['fx'] = .5
    if change == 'not_registered': registered['id'] = 'unregistered_smoke'
    if change == 'short_generation': frames = 2
    if change in ('unsupported_model', 'reference_failure', 'reference_target'):
        path = tmp_path/'reference_predictions.jsonl'
        row = json.loads(path.read_text())
        if change == 'unsupported_model': row['prediction']['scenario'] = 'incline'
        if change == 'reference_failure': row['prediction']['status'] = 'at_bound'
        if change == 'reference_target': row['target'] = 1.62
        dump(path, [row])
        from physedit.runners.media_contract import sha256
        evidence['reference_predictions_sha256'] = sha256(path)
    result = assess([registered], evidence, frames=frames, fps=16)
    assert result['items'][0]['reason'] == reason
    assert not result['uses_generated_results']


def test_unqualified_smoke_keeps_id_and_never_writes_condition(tmp_path, monkeypatch):
    i = item()
    video(tmp_path/'source.avi')
    ip = dump(tmp_path/'items', [i])
    monkeypatch.setattr(gen.cv2, 'VideoCapture', lambda *a: pytest.fail('must reject before decoding'))
    gen.build(SimpleNamespace(items=ip, out=tmp_path/'out', data_root=str(tmp_path), source_root=str(tmp_path),
        host_root=str(tmp_path/'out'), min_window_frames=8, max_end_frame=170, seed=1))
    rows = gen._json_rows(tmp_path/'out/template.jsonl')
    assert len(rows) == 1 and rows[0]['item_id'] == i['id']
    assert rows[0]['input_failure'] == 'missing_reference_applicability_evidence'
    assert not list((tmp_path/'out/conditioning').iterdir())


def test_visibility_and_reference_frame_binding(tmp_path):
    i = item(window=dict(start_frame=25, max_frames=10, edges_visible={'27':[False]*4}))
    evidence = reference_evidence(tmp_path,[i])
    assert assess([i],evidence,frames=81,fps=16)['items'][0]['reason'] == 'reference_window_has_unobservable_scheduled_frames'
    i['window']['edges_visible'] = {}
    evidence = reference_evidence(tmp_path,[i])
    assert assess([i],evidence,frames=81,fps=16)['items'][0]['status'] == 'applicable'
    i['split'] = 'smoke_only'
    assert assess([i],evidence,frames=81,fps=16)['items'][0]['status'] == 'applicable'
