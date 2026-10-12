"""Independent metric scopes, negative identity evidence, and category-local failures."""
import json
from pathlib import Path

import numpy as np
import pytest

from test_evaluations import clip, judgement, api
from physedit import evaluations as ev
from physedit.judge_validation import validate_response


def sparse(entry, missing):
    path = Path(entry['path'])
    with np.load(path) as z:
        data = {k: z[k] for k in z.files}
    scope = data['frames'].copy()
    keep = ~np.isin(scope, missing)
    data.update(scope_frames=scope, unavailable_reasons=np.asarray(['missing_actual_mask' if f in missing else '' for f in scope]),
                frames=scope[keep], masks=data['masks'][keep])
    np.savez_compressed(path, **data)
    entry['sha256'] = ev.sha256(path)


def test_generated_only_metrics_do_not_require_source_masks(clip):
    row, ctx, item, pair = clip
    result = ev.vp_case(row, ctx, item, {'generated': pair['generated']})
    for name in ('background_flicker_full', 'background_flicker_1s', 'silhouette_full', 'silhouette_1s'):
        assert result['metrics'][name]['status'] == 'ok'
        assert result['metrics'][name]['value'] == pytest.approx(0)
    assert result['metrics']['trajectory_error_full']['status'] == 'failed'
    assert result['metrics']['reference_foreground_ssim']['status'] == 'failed'


@pytest.mark.parametrize('kind', ['source', 'generated'])
def test_late_missing_masks_preserve_complete_first_second(clip, kind):
    row, ctx, item, pair = clip
    sparse(pair[kind], [ctx[kind + '_frames'] - 1])
    result = ev.vp_case(row, ctx, item, pair)
    for name in ev.VP_NAMES:
        if name.endswith('_1s') or 'foreground' in name:
            assert result['metrics'][name]['status'] == 'ok', (name, result['metrics'][name])
    assert result['metrics']['trajectory_error_full']['status'] == 'failed'
    assert result['metrics']['motion_region_iou_full']['status'] == 'failed'
    assert result['mask_provenance'][kind]['scope_frames'][-1] == ctx[kind + '_frames'] - 1
    assert result['mask_provenance'][kind]['available_frames'] == 47


def test_missing_reference_window_frame_never_shrinks_window(clip):
    row, ctx, item, pair = clip
    sparse(pair['source'], [7])
    result = ev.vp_case(row, ctx, item, pair)
    assert result['metrics']['condition_foreground_ssim']['status'] == 'ok'
    assert result['metrics']['reference_foreground_ssim']['status'] == 'failed'
    assert result['metrics']['trajectory_error_1s']['status'] == 'failed'
    assert result['metrics']['silhouette_1s']['status'] == 'ok'
    assert '7' in result['metrics']['reference_foreground_ssim']['reason']
    assert result['pixel_alignment']['requested_pairs'] == 30


def test_sparse_missing_reason_cannot_hide_mask_or_scope_drift(clip):
    row, ctx, item, pair = clip
    sparse(pair['source'], [52])
    p = Path(pair['source']['path'])
    with np.load(p) as z:
        data = {k: z[k] for k in z.files}
    data['unavailable_reasons'][-1] = ''
    np.savez_compressed(p, **data)
    pair['source']['sha256'] = ev.sha256(p)
    result = ev.vp_case(row, ctx, item, pair)
    assert 'validity_inconsistent' in result['metrics']['condition_foreground_ssim']['reason']


@pytest.mark.parametrize('drift', [False, True])
def test_identity_review_is_hash_bound_and_only_rejects(clip, tmp_path, drift):
    import hashlib
    row, ctx, item, pair = clip
    with np.load(pair['generated']['path']) as z:
        digest = hashlib.sha256(z['masks'][40].tobytes()).hexdigest()
    review = tmp_path / 'review.json'
    review.write_text(json.dumps(dict(video_sha256=ctx['generated_sha256'], target_name='book',
        rejected_frames=[dict(frame_index=40, reason='visible target is elsewhere; mask covers background',
                              mask_sha256='stale' if drift else digest)])))
    pair['generated']['review'] = dict(path=str(review), sha256=ev.sha256(review))
    result = ev.vp_case(row, ctx, item, pair)
    assert result['metrics']['silhouette_full']['status'] == 'failed'
    if drift:
        assert 'review_observation_mismatch' in result['metrics']['silhouette_1s']['reason']
    else:
        assert result['metrics']['silhouette_1s']['status'] == 'ok'
        assert result['mask_provenance']['generated']['rejected_frames'][0]['frame_index'] == 40
        assert result['mask_provenance']['generated']['identity_accuracy_certified'] is False


@pytest.mark.parametrize('fault', ['missing', 'empty', 'rotation_basis', 'future_condition', 'unregistered_frame', 'false_type'])
def test_one_invalid_judge_category_does_not_erase_other_categories(fault):
    value = judgement()
    key = 'condition_inconsistency' if fault == 'future_condition' else 'abnormal_deformation'
    v = value[key]
    if fault == 'missing': del value[key]
    if fault == 'empty': v['evidence'] = ''
    if fault == 'rotation_basis': v.update(present=True, severity=2, basis='rigid_rotation')
    if fault == 'future_condition': v['evidence_frames'] = [47]
    if fault == 'unregistered_frame': v['evidence_frames'] = [0, 46]
    if fault == 'false_type': v['assessable'] = 'true'
    raw = json.dumps(value)
    result = validate_response(raw, {'frames': [{'frame_index': 0}, {'frame_index': 47}]})
    assert set(result['category_errors']) == {key}
    assert not result['judgement'][key]['assessable']
    assert sum(result['judgement'][k]['assessable'] for k in ev.CATEGORIES) == 4
    assert not result['judgement']['insufficient_evidence']
    assert result['semantic_accuracy_validated'] is False
    record = dict(sample_id='kept', status='partial', **result)
    summary = ev.summarize([{'sample_id': 'kept'}], [record], 'qwen')
    assert summary['registered'] == 1 and summary['failed'] == 1
    assert summary['category_coverage'][key]['assessed'] == 0
    assert summary['clear_violation_percent'][key] is None


def test_old_unsupported_reasons_are_retained_as_unknown_not_rescued():
    value = judgement()
    for k in ev.CATEGORIES:
        del value[k]['basis']
        del value[k]['evidence_frames']
    value['abnormal_deformation'].update(present=True, severity=2, evidence='The can rotates.')
    result = validate_response(json.dumps(value), {'frames': [{'frame_index': 0}, {'frame_index': 47}]})
    assert result['judgement']['insufficient_evidence']
    assert len(result['category_errors']) == 5


def test_api_invalid_category_retains_raw_and_partial_coverage(clip, api, tmp_path):
    config, requests, responses = api
    value = judgement()
    value['identity_change'].update(assessable=False, present=False, severity=0, evidence='')
    responses.append(dict(judgement=value))
    row, _, item, _ = clip
    summary = ev.run_additional({'evaluation': {'metrics': ['qwen'], 'qwen': config}},
                               [row], {'i': item}, {}, tmp_path / 'result')
    record = ev.read_rows(tmp_path / 'result/qwen_results.jsonl')[0]
    assert json.loads(record['raw']) == value and len(requests) == 1
    assert record['status'] == 'partial'
    assert summary['qwen']['category_coverage']['identity_change']['assessed'] == 0
    assert summary['qwen']['category_coverage']['camera_motion']['assessed'] == 1
