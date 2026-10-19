import ast
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import sam31_frontend as frontend
from sam31_scope import STAGES, bind_scope


@pytest.fixture
def job(tmp_path):
    video = tmp_path/'video.avi'
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'FFV1'), 30, (80, 64))
    assert writer.isOpened()
    for f in range(5):
        image = np.full((64, 80, 3), 200, np.uint8)
        image[20:35, 20+f:35+f] = [30, 40, 50]
        writer.write(image)
    writer.release()
    return dict(id='case', video=str(video), video_sha256=frontend.sha(video), fps=30,
                frames=[1, 2, 3, 4], prompt_frame=0, target_name='target',
                scene_boxes={'target': [20, 20, 35, 35]})


def prepare(tmp_path, jobs):
    path = tmp_path/'jobs.jsonl'
    frontend.write_rows(path, jobs)
    root = tmp_path/'run'
    receipt = frontend.prepare(path, root)
    return root, receipt


def test_lock_and_scope_only_adaptation():
    manifest = frontend.lock()
    scope = dict(cases=3, book_cases=1, frames=12, prefix_frames=15,
                 initial_actual_cases=0, shard_sizes=[2, 1])
    for name in STAGES:
        data = (frontend.FROZEN/name).read_bytes()
        tree, changes = bind_scope(data, scope)
        assert changes
        # Every executable operation outside assert expressions is unchanged.
        class DropAssertions(ast.NodeTransformer):
            def visit_Assert(self, node):
                return None
        assert ast.dump(DropAssertions().visit(tree)) == ast.dump(DropAssertions().visit(ast.parse(data)))
        assert hashlib.sha256(data).hexdigest() == manifest['sources'][name]
    tree, _ = bind_scope('for w in (0,1):\n assert len(js[w])==519\n', scope)
    exec(compile(tree, '<scope>', 'exec'), {'js': [[0, 1], [0]], '_sam31_shard_sizes': [2, 1]})
    with pytest.raises(AssertionError):
        exec(compile(tree, '<scope>', 'exec'), {'js': [[0], [0]], '_sam31_shard_sizes': [2, 1]})


def test_odd_shards_and_denominator(tmp_path, job):
    jobs = [{**job, 'id': str(k)} for k in range(3)]
    jobs += [{**job, 'id': 'missing', 'video': str(tmp_path/'absent')},
             {**job, 'id': 'sha_drift', 'video_sha256': 'bad'},
             {**job, 'id': 'empty', 'frames': []}]
    root, receipt = prepare(tmp_path, jobs)
    assert receipt['registered_cases'] == 6 and receipt['eligible_cases'] == 3
    scope = json.loads((root/'generation_scope.json').read_text())
    assert scope['shard_sizes'] == [2, 1] and scope['frames'] == 12
    assert receipt['input_failures'] == {'missing': 'missing_source_video',
                                        'sha_drift': 'video_sha256_mismatch',
                                        'empty': 'empty_registered_window'}
    assert len(frontend.read_rows(root/'all_jobs.jsonl')) == 6
    with pytest.raises(FileExistsError):
        frontend.prepare(tmp_path/'jobs.jsonl', root)


@pytest.mark.parametrize('change', [
    {'gravity_truth': 9.81}, {'v0': [1, 0, 0]}, {'boxes': [[0, 0, 1, 1]]},
    {'frames': [2, 1]}, {'frames': [1, 1]}, {'frames': [-1]},
    {'prompt_frame': 2}, {'fps': 0}, {'fps': float('nan')},
])
def test_truth_and_invalid_contract_rejected(job, change):
    with pytest.raises(ValueError):
        frontend.validate_job({**job, **change})


def fake_tracker(root, source, jobs_name, stem, sam3, checkpoint):
    """Artificial observations, not a substitute for GPU model validation."""
    rows = []
    masks = root/'runs'/(stem+'_masks')
    masks.mkdir(exist_ok=True)
    for j in frontend.read_rows(root/jobs_name):
        boxes = []
        for f in j['frames']:
            m = np.zeros((64, 80), np.uint8)
            m[20:35, 20+f:35+f] = 1
            np.savez_compressed(masks/f'{hashlib.sha256(j["id"].encode()).hexdigest()[:12]}_{f}.npz', mask=m)
            boxes.append([20+f, 20, 35+f, 35])
        row = dict(id=j['id'], frames=j['frames'], boxes=boxes,
                         reasons=['fixture']*len(boxes), box_mode='fixture',
                         tracking_frames=list(range(j['prompt_frame'], j['frames'][-1]+1)),
                         semantic_point_prompts=j['semantic_point_prompts'])
        if 'semantic_text' in j:
            row.update(selected_initial_obj_id=1, initial_candidates=[])
        rows.append(row)
    frontend.write_rows(root/'runs'/(stem+'_tracks.jsonl'), rows)


@pytest.mark.parametrize('target', ['target', 'book'])
def test_actual_cpu_rgb_stages_and_v4(tmp_path, job, target):
    job = {**job, 'target_name': target, 'scene_boxes': {target: job['scene_boxes']['target']}}
    root, _ = prepare(tmp_path, [{**job, 'id': str(k)} for k in range(3)])
    for w in (0, 1):
        for kind, source in [('identity', 'track_sam31_identity_center_control.py'),
                             ('semantic_books', 'track_sam31_whole_book_control.py')]:
            fake_tracker(root, source, f'sam31_{kind}_full30_w{w}_jobs.jsonl', f'sam31_{kind}_full30_w{w}', None, None)
    for w in range(4):
        frontend.write_rows(root/f'sam31_initial_actual_foreground_w{w}_jobs.jsonl', [])
        (root/'runs'/f'sam31_initial_actual_foreground_w{w}_tracks.jsonl').write_text('')
    for name in STAGES:
        frontend.execute(root, name, [sys.executable, str(root/'sam31_scope.py'), str(root), name])
    result = frontend.measure(root)
    assert result['registered_cases'] == 3 and result['missing_boxes'] == 0
    from gravtrace.observations import refine_box
    cap = cv2.VideoCapture(job['video'])
    for p, integer in zip(frontend.read_rows(root/'tracks_v4.jsonl'),
                          frontend.read_rows(root/'runs/sam31_visible_projection_full30_tracks.jsonl')):
        assert p['tracks'][target]['frames'] == job['frames']
        for k, f in enumerate(job['frames']):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, bgr = cap.read()
            assert ok
            with np.load(root/'runs/sam31_visible_projection_full30_masks'/f'{hashlib.sha256(p["id"].encode()).hexdigest()[:12]}_{f}.npz') as z:
                expected, _ = refine_box(bgr, z['mask'], integer['boxes'][k])
            assert p['tracks'][target]['xyxy'][k] == expected
    cap.release()
    records = frontend.read_rows(root/'measurements_v4.jsonl')
    assert all(len(r['pixel_sha256']) == len(r['mask_sha256']) == 4 for r in records)
    # Missing masks already represented by null are retained, never filled by V4.
    rows = frontend.read_rows(root/'runs/sam31_visible_projection_full30_tracks.jsonl')
    rows[0]['boxes'][1] = None
    rows[0]['reasons'][1] = 'missing_model_prediction'
    frontend.write_rows(root/'runs/sam31_visible_projection_full30_tracks.jsonl', rows)
    result = frontend.measure(root)
    assert result['missing_boxes'] == 1
    assert frontend.read_rows(root/'tracks_v4.jsonl')[0]['tracks'][target]['xyxy'][1] is None
    Path(job['video']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Source video drift'):
        frontend.measure(root)


def test_no_source_run_keeps_all_cases_and_refuses_retry(tmp_path, job):
    root, _ = prepare(tmp_path, [{**job, 'video': str(tmp_path/'missing')}])
    result = frontend.run(root, tmp_path/'no_model', tmp_path/'no_checkpoint')
    assert result['registered_cases'] == 1 and result['missing_boxes'] == 4
    assert not (root/'sam31_official').exists()
    assert frontend.read_rows(root/'tracks_v4.jsonl')[0]['reasons'] == ['missing_source_video']*4
    with pytest.raises(ValueError, match='already attempted'):
        frontend.run(root, tmp_path/'no_model', tmp_path/'no_checkpoint')


def test_checkpoint_and_prepared_drift_rejected_before_model(tmp_path, job):
    root, _ = prepare(tmp_path, [job])
    checkpoint = tmp_path/'checkpoint'
    checkpoint.write_text('incorrect weights')
    with pytest.raises(ValueError, match='checkpoint SHA'):
        frontend.run(root, tmp_path/'no_model', checkpoint)
    assert not (root/'started.json').exists()
    (root/'all_jobs.jsonl').write_text('modified')
    with pytest.raises(ValueError, match='Prepared input/source drift'):
        frontend.run(root, tmp_path/'no_model', checkpoint)


def test_generation_fixed_window_and_missing_video(tmp_path, job):
    items = [dict(id='item', fps=30, object_name='target',
                  window=dict(start_frame=25, max_frames=10), gravity=24)]
    rows = [dict(sample_id='case', item_id='item', output_fps=16, num_frames=12,
                 condition_frame_index=23)]
    initial = [dict(id='case', video=job['video'], prompt_frame=0, objects=job['scene_boxes'])]
    for name, content in [('items', items), ('rows', rows), ('initial', initial)]:
        frontend.write_rows(tmp_path/name, content)
    frontend.generation_jobs(tmp_path/'items', tmp_path/'rows', tmp_path/'initial', tmp_path/'out')
    out = frontend.read_rows(tmp_path/'out')[0]
    planned = [f for f in range(12) if 25/30-1e-6 <= 23/30+f/16 <= 34/30+1e-6]
    assert out['frames'] == planned and out['fps'] == 16
    assert set(out) <= frontend.FIELDS and 'gravity' not in out
    assert out['video_sha256'] == job['video_sha256']
