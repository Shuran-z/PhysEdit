import copy
import hashlib
import json

import cv2
import numpy as np
import pytest

from gravtrace.camera import Camera
from gravtrace.motion import ballistic
from physedit import velocity_pixels
from physedit.velocity_kinematics import RegisteredPlanes, sample_digest
from test_velocity_kinematics import make_nonplanar_registration, make_registration


def pixel_fixture(tmp_path):
    sample, saved, row, path, plane_sha = make_nonplanar_registration(tmp_path)
    angles = np.arange(24) * 2 * np.pi / 24
    sample['object']['corners'] = [[.03 * np.cos(a), .03 * np.sin(a), z]
                                    for z in [-.06, .06] for a in angles]
    # Synthetic pixels exercise a numerical observation path, not a production
    # scene. Its known motion is used only to construct test observations.
    centres = ballistic(np.asarray(sample['boxes']['times']), sample['object']['position'],
                        [1.1, .3, .2], 3.71, np.array([0, 0, -1]))
    camera = Camera.from_dict(sample['camera'], sample['image_size'])
    uv = camera.project(centres[:, None] + np.asarray(sample['object']['corners']))
    sample['boxes']['xyxy'] = camera.project_box(centres[:, None] + np.asarray(sample['object']['corners'])).tolist()
    header_path = row['source_header_path']
    header = json.load(open(header_path))
    header['objects'][0]['asset_id'] = 'can_test'
    with open(header_path, 'w') as f:
        json.dump(header, f)
    row['source_header_sha256'] = hashlib.sha256(open(header_path, 'rb').read()).hexdigest()
    row['input_sample_sha256'] = sample_digest(sample)
    path.write_text(json.dumps([row]))
    plane_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cache, frames = {}, []
    for k, poly in enumerate(uv):
        mask = np.zeros(tuple(sample['image_size'][::-1]), np.uint8)
        hull = cv2.convexHull(poly.astype(np.float32))
        cv2.fillConvexPoly(mask, np.rint(hull[:, 0]).astype(int), 1)
        image = np.full((*mask.shape, 3), 80, np.uint8)
        cache['rgb_' + str(k)] = image
        mp = tmp_path / f'mask{k}.npz'
        np.savez_compressed(mp, mask=mask)
        frames.append(dict(frame=k, bgr_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                           mask_path=str(mp), mask_file_sha256=hashlib.sha256(mp.read_bytes()).hexdigest()))
    cp = tmp_path / 'cache.npz'
    np.savez_compressed(cp, **cache)
    pixel_row = dict(id=sample['id'], sample_sha256=sample_digest(sample), cache_path=str(cp),
                     cache_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(), frames=frames)
    registry = tmp_path / 'pixels.json'
    registry.write_text(json.dumps([pixel_row]))
    pixel_sha = hashlib.sha256(registry.read_bytes()).hexdigest()
    return sample, saved, RegisteredPlanes(path, plane_sha), registry, pixel_sha, pixel_row


def test_full_mask_fallback_recovers_motion_without_sam_or_gravity_calls(tmp_path):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    before = copy.deepcopy((sample, saved))
    result = velocity_pixels.fit_pixel_velocity(sample, saved, planes,
                                               velocity_pixels.RegisteredVelocityPixels(path, sha))
    assert result['status'] == 'ok', result
    assert result['source_model_branch'] == 'full_frozen_mask_outline'
    # Quantized single-view masks do not certify each 3D component. Check the
    # measured scalar speed and explicitly retain the direction limitation.
    target_speed = np.linalg.norm([1.1, .3, .2])
    assert abs(result['speed_mps'] / target_speed - 1) < .05
    assert (sample, saved) == before
    assert not result['frozen_gravity_result_changed']
    assert not result['new_sam_inference']
    assert not result['high_precision_certified']
    assert result['attempts'][0]['prediction']['reason'] == 'too_few_adjacent_RGB_flow_pairs'


@pytest.mark.parametrize('fault', ['cache_bytes', 'mask_bytes', 'pixel_bytes', 'frames', 'sample'])
def test_stale_pixels_cannot_fall_back_to_a_successful_measurement(tmp_path, fault):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    if fault == 'cache_bytes':
        with open(row['cache_path'], 'ab') as f:
            f.write(b'changed')
    elif fault == 'mask_bytes':
        with open(row['frames'][0]['mask_path'], 'ab') as f:
            f.write(b'changed')
    elif fault == 'pixel_bytes':
        row['frames'][0]['bgr_sha256'] = '0' * 64
    elif fault == 'frames':
        row['frames'][0]['frame'] = 40
    else:
        row['sample_sha256'] = '0' * 64
    if fault not in ('cache_bytes', 'mask_bytes'):
        path.write_text(json.dumps([row]))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result = velocity_pixels.fit_pixel_velocity(sample, saved, planes,
                                               velocity_pixels.RegisteredVelocityPixels(path, sha))
    assert result['status'] == 'input_failure', result


def test_velocity_target_is_rejected_before_reading_source(tmp_path):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    sample['motion']['v0'] = [1.1, .3, .2]
    result = velocity_pixels.fit_pixel_velocity(sample, saved, None, None)
    assert result == dict(status='input_failure', reason='velocity_truth_in_estimator_input')
    row['target_v0'] = [1.1, .3, .2]
    path.write_text(json.dumps([row]))
    with pytest.raises(ValueError, match='invalid_or_duplicate'):
        velocity_pixels.RegisteredVelocityPixels(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_converged_flow_must_agree_with_original_silhouette(tmp_path, monkeypatch):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    monkeypatch.setattr(velocity_pixels, '_masked_flow', lambda *a: dict(status='ok',
                        velocity=[7., 7., 7.], acceleration=-3.71, optimizer_success=True))
    result = velocity_pixels.fit_pixel_velocity(sample, saved, planes,
                                               velocity_pixels.RegisteredVelocityPixels(path, sha))
    assert result['status'] == 'ok', result
    assert result['source_model_branch'] == 'full_frozen_mask_outline'
    assert result['attempts'][0]['outline_check']['consistent'] is False
    assert result['attempts'][0]['prediction']['velocity'] == [7., 7., 7.]


def test_two_incompatible_branches_preserve_failure(tmp_path, monkeypatch):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    monkeypatch.setattr(velocity_pixels, '_masked_flow', lambda *a: dict(status='ok',
                        velocity=[7., 7., 7.], acceleration=-3.71))
    monkeypatch.setattr(velocity_pixels, '_silhouette_fit', lambda *a: dict(status='ok',
                        velocity=[7., 7., 7.], acceleration_nuisance=-3.71))
    result = velocity_pixels.fit_pixel_velocity(sample, saved, planes,
                                               velocity_pixels.RegisteredVelocityPixels(path, sha))
    assert result['status'] == 'fit_failure'
    assert len(result['attempts']) == 2
    assert 'speed_mps' not in result


def test_consistent_pixels_cannot_hide_velocity_search_bound(tmp_path, monkeypatch):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    monkeypatch.setattr(velocity_pixels, '_masked_flow', lambda *a: dict(status='ok',
                        velocity=[8., 0., 0.], acceleration=-3.71))
    monkeypatch.setattr(velocity_pixels, '_outline_check', lambda *a: dict(status='ok', consistent=True))
    result = velocity_pixels.fit_pixel_velocity(sample, saved, planes,
                                               velocity_pixels.RegisteredVelocityPixels(path, sha))
    assert result['status'] == 'at_bound' and len(result['attempts']) == 1
    assert 'speed_mps' not in result


def test_planar_branch_never_needs_new_pixels(tmp_path):
    sample, saved, row, path, sha = make_registration(tmp_path)
    planes = RegisteredPlanes(path, sha)
    expected = dict(velocity_pixels.fit_registered_velocity(sample, saved, planes),
                    source_model_branch='registered_planar')
    assert velocity_pixels.fit_pixel_velocity(sample, saved, planes, None) == expected


def test_future_source_positions_and_velocities_cannot_influence_fit(tmp_path):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    pixels = velocity_pixels.RegisteredVelocityPixels(path, sha)
    expected = velocity_pixels.fit_pixel_velocity(sample, saved, planes, pixels)
    source = copy.deepcopy(planes.rows[sample['id']])
    state_path = source['source_state_path']
    with np.load(state_path) as archive:
        positions = archive['position'].copy()
        names = archive['names'].copy()
    positions[1:] = np.nan
    np.savez(state_path, names=names, position=positions,
             velocity=np.full_like(positions, 10000.))
    source['source_state_sha256'] = hashlib.sha256(open(state_path, 'rb').read()).hexdigest()
    registry = tmp_path / 'changed_source.json'
    registry.write_text(json.dumps([source]))
    changed = RegisteredPlanes(registry, hashlib.sha256(registry.read_bytes()).hexdigest())
    assert velocity_pixels.fit_pixel_velocity(sample, saved, changed, pixels) == expected


def test_centred_polygon_moments_translation_and_size():
    square = np.array([[0, 0], [2, 0], [2, 2], [0, 2]], float)
    original = velocity_pixels._polygon_moments(square)
    shifted = velocity_pixels._polygon_moments(square + [500, 200])
    np.testing.assert_allclose(original, [1, 1, np.sqrt(1 / 3), np.sqrt(1 / 3)])
    np.testing.assert_allclose(shifted[:2], original[:2] + [500, 200])
    np.testing.assert_allclose(shifted[2:], original[2:], atol=1e-9)


def test_book_and_cup_cannot_enter_can_pixel_model(tmp_path):
    sample, saved, planes, path, sha, row = pixel_fixture(tmp_path)
    for asset in ['book_thick_01_v2', 'cup_can_style', 'scanned_canopy']:
        assert not velocity_pixels.can_geometry_eligibility(sample, {'asset_id': asset})['eligible']
    source = copy.deepcopy(planes.rows[sample['id']])
    header = json.load(open(source['source_header_path']))
    header['objects'][0]['asset_id'] = 'book_thick_01_v2'
    with open(source['source_header_path'], 'w') as f:
        json.dump(header, f)
    source['source_header_sha256'] = hashlib.sha256(open(source['source_header_path'], 'rb').read()).hexdigest()
    registration = tmp_path / 'book_registration.json'
    registration.write_text(json.dumps([source]))
    bound = RegisteredPlanes(registration, hashlib.sha256(registration.read_bytes()).hexdigest())
    # No pixel loading or automatic alternate estimator for unsupported objects.
    result = velocity_pixels.fit_pixel_velocity(sample, saved, bound, None)
    assert result['status'] == 'inapplicable'
    assert result['original_velocity_result_preserved']
    assert 'speed_mps' not in result


@pytest.mark.parametrize('geometry', [None, [[0, 0, 0]], [[np.nan, 0, 0]] * 24,
                                    [[x, y, z] for x in [-.03, .03]
                                     for y in [-.03, .03] for z in [-.06, .06]]])
def test_can_asset_label_without_round_geometry_is_insufficient(geometry):
    assert not velocity_pixels.can_geometry_eligibility({'object': {'corners': geometry}},
                                                       {'asset_id': 'can_test'})['eligible']


def test_scoring_entry_retains_failed_pixel_input_and_does_not_use_target_for_fit(tmp_path):
    import runpy
    from pathlib import Path
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/phyediting_motion_parameters.py'))
    sample, saved, planes, path, sha, pixels = pixel_fixture(tmp_path)
    plane_path = tmp_path / 'entry_planes.json'
    plane_path.write_text(json.dumps(list(planes.rows.values())))
    record = dict(id=sample['id'], event='synthetic', sample=sample,
                  saved_gravity_prediction=saved, target_v0=[1.1, .3, .2],
                  plane_registration=dict(path=str(plane_path), sha256=hashlib.sha256(plane_path.read_bytes()).hexdigest()),
                  pixel_registration=dict(path=str(path), sha256=sha))
    first = module['evaluate_kinematic_velocity']([record], can_pixels=True)
    assert first['records'][0]['status'] == 'ok'
    record['target_v0'] = [999, 999, 999]
    second = module['evaluate_kinematic_velocity']([record], can_pixels=True)
    assert first['records'][0]['prediction'] == second['records'][0]['prediction']
    with open(pixels['cache_path'], 'ab') as f:
        f.write(b'drift')
    failed = module['evaluate_kinematic_velocity']([record], can_pixels=True)
    assert len(failed['records']) == 1 and failed['records'][0]['status'] == 'input_failure'
    assert not failed['original_predictions_replaced']
    assert not failed['new_sam_inference']
