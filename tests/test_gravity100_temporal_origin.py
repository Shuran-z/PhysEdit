"""CPU-only native-origin, lossless-pixel and shared evaluator regressions."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from physedit import gravity100 as g100, conditioned_measurement as cm, evaluations as ev
from physedit.runners.media_contract import seal_completion, row_digest, validate_video
from physedit.runners.oneclick_registry import MODELS
from test_gravity100_pipeline import prepared


def write_video(path, images, fps):
    h, w = images[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'), fps, (w, h))
    assert writer.isOpened()
    for image in images:
        writer.write(image)
    writer.release()


def decode(path):
    cap = cv2.VideoCapture(str(path))
    images, times = [], []
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            images.append(image)
            times.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.)
    finally:
        cap.release()
    return images, times


@pytest.fixture
def physrvg_row(tmp_path):
    yy, xx = np.indices((24, 32))
    images = [np.stack([(xx * 3 + k * 5) % 256, (yy * 4 + k * 3) % 256,
                        (xx + yy + k * 2) % 256], axis=-1).astype(np.uint8) for k in range(49)]
    raw, resized, reference = [tmp_path / n for n in ('raw.avi', 'resized.avi', 'reference.avi')]
    write_video(raw, images, 15.)
    write_video(resized, images, 15.)
    write_video(reference, [images[4]] * 10, 30.)
    condition = tmp_path / 'condition.png'
    assert cv2.imwrite(str(condition), images[4])
    prompt, negative = tmp_path / 'prompt.txt', tmp_path / 'negative.txt'
    prompt.write_text('Continue this condition with the declared parameters.')
    negative.write_text('camera motion')
    row = dict(sample_id='native-origin-case', item_id='G100_001', model_name='physrvg_ti2v5b',
               protocol='gravity100', mode='i2v', split='ID', gravity_truth=9.81,
               condition_image=str(condition), condition_frame_index=0, condition_frames=1,
               prompt_file=str(prompt), negative_prompt_file=str(negative),
               prompt_granularity='registered_condition_continuation',
               generated_video=str(raw), generated_video_resized_to_source=str(resized),
               evaluation_video=str(tmp_path / 'evaluation.avi'), num_frames=49, output_fps=15.,
               source_video=str(reference), source_video_sha256=g100.sha256(reference),
               source_native_fps=30., source_width=32, source_height=24,
               raw_origin_frame=4, conditioning_input_frames=5, evaluation_output_frames=45,
               evaluation_origin_source='FastVideo static_frame: condition image repeated five times; first two condition latents clamped',
               observation_clock=dict(generated_frames=list(range(5)), physical_times_s=[k * .04 for k in range(5)],
                                      reason=None), input_failure=None)
    seal_completion(row)
    return row, images, tmp_path


def test_physrvg_lossless_raw4_to_clip0_preserves_both_native_outputs(physrvg_row):
    row, original, root = physrvg_row
    before = {k: g100.sha256(row[k]) for k in ('generated_video', 'generated_video_resized_to_source')}
    registered_row_sha = row_digest(row)
    receipt = g100.prepare_evaluation_video(row)
    actual, times = decode(row['evaluation_video'])
    assert len(actual) == 45
    assert all(np.array_equal(a, b) for a, b in zip(actual, original[4:]))
    assert not np.array_equal(actual[0], original[0])  # Detect the old raw0 mistake.
    assert times == pytest.approx([i / 15 for i in range(45)], abs=1e-6)
    assert receipt['raw_origin_frame'] == 4 and receipt['conditioning_input_frames'] == 5
    assert receipt['evaluation_frame0_decoded_bgr_sha256'] == hashlib.sha256(original[4].tobytes()).hexdigest()
    assert receipt['source_suffix_decoded_bgr_sha256'] == receipt['evaluation_decoded_bgr_sha256']
    assert receipt['interpolation'] is receipt['fps_changed'] is receipt['generated_again'] is False
    assert row_digest(row) == registered_row_sha
    for k, digest in before.items():
        assert g100.sha256(row[k]) == digest
        assert validate_video(row[k], fps=15., frames=49)['frames'] == 49
    mtime = Path(row['evaluation_video']).stat().st_mtime_ns
    assert g100.prepare_evaluation_video(row) == receipt
    assert Path(row['evaluation_video']).stat().st_mtime_ns == mtime


def test_native_prefix_clock_starts_at_zero_preserves_scale_and_checks_available_tail(monkeypatch):
    monkeypatch.setattr(cm, 'descriptor', lambda task: ({'kind': 'frozen'}, {}, None))
    member = dict(evaluation_frame_count='10', media_fps='30')
    task = dict(physical_times_s=[k * .02 for k in range(10)])
    clock = g100.observation_clock(member, task, 15., 49, prefix=5)
    assert clock['generated_frames'] == list(range(5))
    assert clock['physical_times_s'] == pytest.approx([k * .04 for k in range(5)])
    assert clock['physics_seconds_per_media_second'] == pytest.approx(.6)
    assert clock['evaluation_output_frames'] == 45
    assert clock['available_future_media_seconds'] == pytest.approx(44/15)
    long_member = dict(evaluation_frame_count='91', media_fps='30')
    long_task = dict(physical_times_s=[k * .02 for k in range(91)])
    assert g100.observation_clock(long_member, long_task, 15., 49)['applicable']
    short = g100.observation_clock(long_member, long_task, 15., 49, prefix=5)
    assert short['reason'] == 'generation_duration_shorter_than_fixed_scope'
    assert short['generated_frames'] == list(range(45))


@pytest.mark.parametrize('prefix', [0, -1, 49, True, 1.5])
def test_origin_cannot_be_arbitrary_or_empty(prefix):
    with pytest.raises(ValueError, match='condition_prefix'):
        g100.observation_clock({}, {}, 15., 49, prefix=prefix)


def legacy_clock(member, task, fps, frames):
    """The HEAD54b origin0 result shape, including historical float operations."""
    duration = (int(member['evaluation_frame_count'])-1) / float(member['media_fps'])
    scheduled = [f for f in range(frames) if f/fps <= duration + 1e-9]
    scale = task['physical_times_s'][-1] / duration
    times = [f/fps*scale for f in scheduled]
    reason = ('generation_duration_shorter_than_fixed_scope' if (frames-1)/fps + 1e-9 < duration else
              'native_frames_within_fixed_horizon_below_model_minimum' if len(scheduled) < 4 else None)
    return dict(generated_frames=scheduled, physical_times_s=times, media_horizon_s=duration,
                physical_horizon_s=task['physical_times_s'][-1], physics_seconds_per_media_second=scale,
                applicable=reason is None, reason=reason)


@pytest.mark.parametrize('model', [m for m in MODELS if m != 'physrvg_ti2v5b'])
def test_other_eleven_origin0_clock_is_byte_equivalent(model, monkeypatch):
    monkeypatch.setattr(cm, 'descriptor', lambda task: ({'kind': 'frozen'}, {}, None))
    registration = MODELS[model]
    for count in (2, 4, 10, 64):
        member = dict(evaluation_frame_count=str(count), media_fps='30')
        task = dict(physical_times_s=[k*.02 for k in range(count)])
        expected = legacy_clock(member, task, registration.fps, registration.frames)
        assert json.dumps(g100.observation_clock(member, task, registration.fps, registration.frames), sort_keys=True) == json.dumps(expected, sort_keys=True)


# Produced by the original HEAD54b build_inputs over the same 100-member fixture.
# Only machine-local paths and the codec-dependent reference file SHA are normalized.
LEGACY_HEAD54B_ROW_DIGESTS = {
    'ltx_i2v': 'a8b93a4b6507857098c13ba232e0861a8815ad7a8f375b592f8c69ddd239b875',
    'cogvideox_i2v': '18ff2744641a7a5a97dcc34cab9c89e745fb2e6c6456d3ed58faab1b7521a5ef',
    'wan_ti2v5b': 'a19dd81c5efcfa4561c3fa7a31c57b6e70f5eef7d2ff8d0179d6360541ae239b',
    'hunyuan15_i2v': '2e1809d64552d5312c6a0bb36bc0cf84231875d2c93ebed09298b4b217600fed',
    'cosmos': 'abb0a4f31381868410dc07c4cdd5bddd8f83d6cef289fd5f753fef1809a8188b',
    'dynamicrafter_i2v': '2f2af320c87bdadbdd6ee7d3414f59812f20304ba4d8d4487617eea6d2d85825',
    'videogpa_ti2v5b': '80b838919c5fc2ab3977b3e225517c7db13cd57aa48b6a9eb3a4ee88460fb88b',
    'cosmos3_nano': 'e8b2159faba81405dca4f66a754fb6cf1bf8a709ec596db44b2cd87f9ade7cff',
    'wan22_i2v_a14b': 'd1da5e3f6b3d202a7ab74b576ac12f144a6c9238435b899ea92d5009e8014d07',
    'physalign_wan22_i2v_a14b': '92ea253bf921893b2601189801fd91374064f06233ff3794be4b47e19a034855',
    'minimax_h3': '092507d19ef5afb73ae3aa5ba546f02bb511bf15fbac1f4a32547115e8be90d1',
}


@pytest.mark.parametrize('model', LEGACY_HEAD54B_ROW_DIGESTS)
def test_other_eleven_original100_rows_match_head54b_digest(prepared, model, monkeypatch):
    spec, _, root = prepared
    profile = MODELS[model]
    if model == 'dynamicrafter_i2v':
        # Isolate the origin change using HEAD54b's profile. A separate runner
        # change may explicitly register the native 1024x576 generation canvas.
        from dataclasses import replace
        profile = replace(profile, canvas=None)
        monkeypatch.setitem(MODELS, model, profile)
    spec.update(model=model, frames=profile.frames, fps=profile.fps)
    run = root/'run'
    _, rows, _, _ = g100.build_inputs(spec, run)
    normalized = json.loads(json.dumps(rows, sort_keys=True)
        .replace(str(run.resolve()), '<run>').replace(str(root.resolve()), '<fixture>'))
    for row in normalized:
        row['source_video_sha256'] = '<reference-video-sha>'
    assert len(rows) == 100
    digest = hashlib.sha256(json.dumps([row_digest(row) for row in normalized]).encode()).hexdigest()
    assert digest == LEGACY_HEAD54B_ROW_DIGESTS[model]


def test_physrvg_build_keeps_native49_and_adds_runner_granularity_only_here(prepared):
    spec, tasks, root = prepared
    original_prompt_sha = g100.sha256(root / 'prompt.txt')
    spec.update(model='physrvg_ti2v5b', frames=49, fps=15)
    plan, rows, _, _ = g100.build_inputs(spec, root / 'physrvg')
    assert plan['native_output_frames'] == 49 and plan['evaluation_output_frames'] == 45
    assert plan['raw_origin_frame'] == 4 and plan['conditioning_frame'] == 0
    for row in rows:
        assert row['num_frames'] == 49 and row['output_fps'] == 15.
        assert row['condition_frames'] == 1 and row['condition_frame_index'] == 0
        assert row['prompt_granularity'] == 'registered_condition_continuation'
        assert row['raw_origin_frame'] == 4 and row['evaluation_output_frames'] == 45
        assert g100.sha256(row['prompt_file']) == original_prompt_sha
    # All other legacy row metadata remains absent rather than adding origin0 fields.
    spec.update(model='cogvideox_i2v', frames=81, fps=16)
    _, legacy_rows, _, _ = g100.build_inputs(spec, root / 'legacy')
    assert all(not {'evaluation_video', 'raw_origin_frame', 'conditioning_input_frames',
                    'evaluation_output_frames', 'prompt_granularity'} & set(r) for r in legacy_rows)


def test_tracking_gravity_vp_and_qwen_use_same_current_clip(physrvg_row, monkeypatch):
    row, original, root = physrvg_row
    g100.prepare_evaluation_video(row)
    task = dict(initial_objects={'object': [4, 3, 20, 18]}, target_name='object', image_size=[32, 24])
    jobs = g100.tracking_jobs([row], {row['item_id']: task})
    assert jobs[0]['video'] == row['evaluation_video']
    assert jobs[0]['prompt_frame'] == 0 and jobs[0]['frames'] == list(range(5))
    assert jobs[0]['video_sha256'] == g100.sha256(row['evaluation_video'])
    sam = root / 'sam'
    masks = sam / 'runs/sam31_visible_projection_full30_masks'
    masks.mkdir(parents=True)
    jid = jobs[0]['id']
    stem = hashlib.sha256(jid.encode()).hexdigest()[:12]
    for f in jobs[0]['frames']:
        np.savez_compressed(masks / (stem+'_'+str(f)+'.npz'), mask=np.ones((24,32), bool))
    g100.write_rows(sam / 'tracks_v4.jsonl', [dict(id=jid, video_sha256=jobs[0]['video_sha256'],
        tracks={'object': dict(frames=list(range(5)), xyxy=[[4,3,20,18]]*5)})])
    seen = []
    def measure(t, video, frames, times, mask_paths, output):
        seen.append(video)
        assert video == row['evaluation_video'] and times == pytest.approx([k*.04 for k in range(5)])
        assert np.array_equal(decode(video)[0][0], original[4])
        return dict(status='ok', gravity=9.81)
    monkeypatch.setattr(cm, 'measure', measure)
    predictions = g100.score_generated([row], {row['item_id']: task}, sam, root/'scores')
    assert predictions[0]['status'] == 'ok' and predictions[0]['raw_origin_frame'] == 4
    assert seen == [row['evaluation_video']]
    ctx = ev.context(row)
    assert ctx['generated_frames'] == 45 and ctx['native_generated_frames'] == 49
    assert ctx['generated_sha256'] == jobs[0]['video_sha256']
    assert ev.generated_video(row) == jobs[0]['video']
    vp = ev.vp_case(row, ctx, {'object_name': 'object'}, {})
    assert vp['metrics']['condition_ssim']['value'] == pytest.approx(1.)
    evidence = ev.qwen_evidence(row, ctx, root/'qwen_evidence')
    assert evidence['video']['path'] == str(Path(row['evaluation_video']).resolve())
    assert evidence['video']['frame_count'] == 45 and evidence['frames'][0]['time_seconds'] == 0
    assert np.array_equal(cv2.imread(evidence['frames'][0]['path']), original[4])
    ev.verify_evidence(evidence)


def test_optional_vp_full_mask_jobs_use45_clip_frames(physrvg_row, monkeypatch):
    row, _, root = physrvg_row
    g100.prepare_evaluation_video(row)
    from scripts import sam31_frontend as frontend
    monkeypatch.setattr(frontend, 'prepare', lambda *a: None)
    def no_gpu(*args):
        raise RuntimeError('CPU fixture: no SAM process is launched')
    monkeypatch.setattr(frontend, 'run', no_gpu)
    output = root/'vp'
    output.mkdir()
    ev.automatic_masks([row], {row['sample_id']: ev.context(row)},
                       {row['item_id']: {'object_name': 'object'}}, {},
                       {'sam3':'unused','checkpoint':'unused'}, output)
    jobs = g100.read_rows(output/'vp_mask_jobs.jsonl')
    job = next(j for j in jobs if j['id'].endswith('_generated'))
    assert job['video'] == row['evaluation_video'] and job['frames'] == list(range(45))
    assert job['prompt_frame'] == 0 and job['fps'] == 15.


def test_origin_and_partial_drift_are_retained_and_rejected(physrvg_row):
    row, _, root = physrvg_row
    wrong = dict(row, raw_origin_frame=0)
    with pytest.raises(ValueError, match='registered_evaluation_origin'):
        g100.prepare_evaluation_video(wrong)
    partial = root/'evaluation.partial.avi'
    partial.write_bytes(b'original failed partial')
    with pytest.raises(FileExistsError, match='partial_retained'):
        g100.prepare_evaluation_video(row)
    assert partial.read_bytes() == b'original failed partial'


def test_clip_binding_drift_is_rejected_before_optional_judging(physrvg_row):
    row, _, root = physrvg_row
    g100.prepare_evaluation_video(row)
    binding = Path(row['evaluation_video']).with_suffix('.evaluation.json')
    receipt = json.loads(binding.read_text())
    receipt['raw_origin_frame'] = 0
    binding.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='evaluation_video_binding_changed'):
        ev.context(row)


def test_reviewed_guards_reject_clock_drift_before_fitting():
    d = dict(module='foreground_safe_control_RGB')
    p = dict(known_interval={'integration_substep_s':1/7680})
    assert cm.native_control_clock(d, p, [k/30 for k in range(4)]) is None
    assert cm.native_control_clock(d, p, [k/25 for k in range(4)]) == 'observation_interval_not_on_solver_step_grid'
    assert cm.native_control_clock(d, p, [k/10 for k in range(4)]) is None
    assert cm.native_control_clock(d, p, [k/25 for k in range(8)]) == 'registered_four_observation_model'
    group = dict(module='known_group_outline', registered_physical_times_s=[0,.02,.04])
    known = dict(known_group_condition={'step_s':.005,'world_force_updates_from_config':[[0,0,0]]*3})
    assert cm.native_control_clock(group, known, [0,.02,.04]) is None
    assert cm.native_control_clock(group, known, [0,.02,.06]) == 'registered_control_schedule_shorter_than_observation_scope'


@pytest.mark.parametrize('h', [0., -1/7680, float('nan'), float('inf'), -float('inf')])
def test_nonpositive_or_nonfinite_tick_is_rejected_before_division(h):
    d = dict(module='foreground_safe_control_RGB')
    p = dict(known_interval={'integration_substep_s':h})
    assert cm.native_control_clock(d, p, [k/30 for k in range(4)]) == 'invalid_registered_integration_substep'


def test_existing_physrvg_run_cannot_reuse_raw0_predictions(prepared, monkeypatch):
    spec, _, root = prepared
    spec.update(model='physrvg_ti2v5b', frames=49, fps=15)
    plan = g100.execution_plan(spec)
    old_plan = {k:v for k,v in plan.items() if k not in
                {'raw_origin_frame','conditioning_input_frames','evaluation_output_frames','origin_rule'}}
    old = root/'old-run'
    old.mkdir()
    (old/'registered.json').write_text(json.dumps({'plan':old_plan}))
    with pytest.raises(ValueError, match='temporal_origin_changed'):
        g100.existing_run(spec, old, root/'recheck')


def test_origin0_rows_keep_old_optional_evaluation_context(physrvg_row):
    row, _, _ = physrvg_row
    for key in ['evaluation_video','raw_origin_frame','conditioning_input_frames',
                'evaluation_output_frames','evaluation_origin_source','prompt_granularity']:
        row.pop(key)
    row['model_name'] = 'legacy-origin0-fixture'
    seal_completion(row)
    before = row_digest(row)
    assert g100.evaluation_video(row) == row['generated_video_resized_to_source']
    assert g100.prepare_evaluation_video(row) is None
    assert g100.verified_evaluation_video(row) is None
    ctx = ev.context(row)
    assert ctx['generated_frames'] == 49
    assert not {'raw_origin_frame','conditioning_input_frames','native_generated_frames',
                'evaluation_binding_sha256'} & set(ctx)
    assert ctx['generated_sha256'] == g100.sha256(row['generated_video_resized_to_source'])
    assert row_digest(row) == before


def test_legacy_relative_native_path_needs_no_clip_or_io():
    row = {'protocol':'gravity100', 'model_name':'cogvideox_i2v',
           'generated_video_resized_to_source':'./existing/resized.mp4'}
    assert g100.evaluation_video(row) == './existing/resized.mp4'
    assert g100.prepare_evaluation_video(row) is None
