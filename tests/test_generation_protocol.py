import sys
import copy

from scripts import phyediting_gen


def test_generated_scoring_defaults_do_not_use_reference_velocity(monkeypatch):
    captured = []
    monkeypatch.setattr(sys, "argv", ["phyediting_gen.py", "score", "items", "rows", "tracks", "out"])
    monkeypatch.setattr(phyediting_gen, "score", captured.append)
    phyediting_gen.main()
    assert captured[0].v0 == "agnostic"
    assert captured[0].offset_mode == "anchor"


def fixed_window_inputs():
    row = {"sample_id": "clip", "condition_frame_index": 23, "output_fps": 16,
           "num_frames": 81, "gravity_truth": 9.81}
    item = {"fps": 30, "image_size": [100, 100], "camera": {}, "object": {},
            "object_name": "book", "window": {"start_frame": 38, "max_frames": 9},
            "motion": {"v0": [2., 1., 0.], "gravity_dir": [0., 0., -1.],
                       "directions": [[1., 0., 0.]]}}
    track = {"tracks": {"book": {"frames": [8, 9, 10, 11, 12],
                                "xyxy": [[1, 2, 10, 12]] * 5}}}
    return row, item, track


def test_missing_scheduled_frame_fails_whole_case(monkeypatch):
    row, item, track = fixed_window_inputs()
    track["tracks"]["book"]["frames"].pop(2)
    track["tracks"]["book"]["xyxy"].pop(2)
    monkeypatch.setattr(phyediting_gen, "safe_fit", lambda _: (_ for _ in ()).throw(AssertionError("must not fit")))
    result = phyediting_gen._score_fixed_window(row, item, track)
    assert result["status"] == "missing_observation"
    assert result["planned_generated_frames"] == [8, 9, 10, 11, 12]
    assert result["missing_generated_frames"] == [10]
    assert result["frames"] == 0


def test_empty_mask_fails_without_camera_mapping(monkeypatch):
    row, item, track = fixed_window_inputs()
    track["tracks"]["book"]["xyxy"][0] = None
    result = phyediting_gen._score_fixed_window(row, item, track, to_first={8: [[1, 0, 0], [0, 1, 0]]})
    assert result["status"] == "missing_observation"
    assert result["planned_frames"] == 5


def test_outside_window_missing_mask_does_not_enter_camera_mapping(monkeypatch):
    row, item, track = fixed_window_inputs()
    track["tracks"]["book"]["frames"].insert(0, 0)
    track["tracks"]["book"]["xyxy"].insert(0, None)
    monkeypatch.setattr(phyediting_gen, "safe_fit", lambda s: {"status": "ok", "frames": 5})
    result = phyediting_gen._score_fixed_window(row, item, track, to_first={0: [[1, 0, 0], [0, 1, 0]]})
    assert result["status"] == "ok" and result["planned_frames"] == 5


def test_complete_fixed_window_has_exact_time_and_no_velocity_prior(monkeypatch):
    row, item, track = fixed_window_inputs()
    captured = []
    def fit(sample):
        captured.append(copy.deepcopy(sample))
        return {"id": sample["id"], "status": "ok", "frames": 5, "gravity": 9.81}
    monkeypatch.setattr(phyediting_gen, "safe_fit", fit)
    result = phyediting_gen._score_fixed_window(row, item, track)
    item["motion"]["v0"] = [-700., 900., -500.]
    row["gravity_truth"] = -1234
    phyediting_gen._score_fixed_window(row, item, track)
    assert captured[0] == captured[1]
    assert captured[0]["motion"]["speed"] == [0., 8.]
    assert "v0" not in captured[0]["motion"] and "directions" not in captured[0]["motion"]
    assert captured[0]["motion"]["t0"] == [0., 0.]
    assert captured[0]["boxes"]["times"] == [0., .0625, .125, .1875, .25]
    assert captured[0]["window"]["contact_check"] is False
    assert result["planned_frames"] == result["frames"] == 5


def test_residual_pixel_is_failure_not_silently_ignored_frame(monkeypatch):
    row, item, track = fixed_window_inputs()
    track["tracks"]["book"]["xyxy"][-1] = [80, 90, 81, 91]
    monkeypatch.setattr(phyediting_gen, "safe_fit", lambda _: (_ for _ in ()).throw(AssertionError("must not fit")))
    result = phyediting_gen._score_fixed_window(row, item, track)
    assert result["status"] == "invalid_observation"
    assert result["observation_reason"] == "tiny_by_original_fitter"
    assert result["unusable_generated_frames"] == [12]
    assert result["planned_generated_frames"] == [8, 9, 10, 11, 12]
    assert result["planned_frames"] == 5 and result["frames"] == 0


def test_tiny_mask_outside_registered_window_does_not_change_score(monkeypatch):
    row, item, track = fixed_window_inputs()
    track["tracks"]["book"]["frames"].append(13)
    track["tracks"]["book"]["xyxy"].append([80, 90, 81, 91])
    monkeypatch.setattr(phyediting_gen, "safe_fit", lambda _: {"status": "ok", "frames": 5})
    result = phyediting_gen._score_fixed_window(row, item, track)
    assert result["status"] == "ok"
    assert result["planned_generated_frames"] == [8, 9, 10, 11, 12]
