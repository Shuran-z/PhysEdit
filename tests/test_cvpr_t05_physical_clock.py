"""The actual T05 pass occurs inside 5 physics seconds despite the media prelude."""
import importlib.util
from pathlib import Path
import pytest

P=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/critical_t05_friction/clock_policy.py'
spec=importlib.util.spec_from_file_location('t05_clock',P);clock=importlib.util.module_from_spec(spec);spec.loader.exec_module(clock)
ARGS=dict(pre_static_frames=27,sim_dt=1/480,physics_steps_per_frame=16)


def test_recorded_post_step_clock_correctly_places_c03_pass_at_4p9s():
    assert clock.physical_time(4,**ARGS)==0
    assert clock.physical_time(26,**ARGS)==0
    assert clock.physical_time(27,**ARGS)==pytest.approx(1/30)
    assert clock.physical_time(173,**ARGS)==pytest.approx(4.9)
    assert(173-4)/30>5


def test_five_second_source_window_keeps_original_condition_image():
    w=clock.source_window(condition_frame_index=4,horizon_s=5,frame_count=210,**ARGS)
    assert w['condition_frame_index']==4
    assert(w['first_event_frame'],w['last_event_frame'])==(27,176)
    assert w['native_covers']and w['generated_origin_frame']==0


def test_removing_prelude_does_not_invent_missing_physics_duration():
    w=clock.source_window(condition_frame_index=4,horizon_s=7,frame_count=210,**ARGS)
    assert not w['native_covers']
    assert w['last_event_frame']==209
    assert clock.physical_time(209,**ARGS)==pytest.approx(6.1)
