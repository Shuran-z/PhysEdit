from scripts.t15_refine_existing_scans_worker import event_audit_usable


def test_observed_fall_is_not_invalidated_by_later_unsettled_tail():
    audit={'valid':False,'errors':['not_settled_tail_speed=0.24'],'event_frames':{'laptop_falls_to_floor':152}}
    assert not event_audit_usable(audit,'laptop_falls_to_floor')
    assert event_audit_usable(audit,'laptop_falls_to_floor',True)


def test_unobserved_event_or_settling_itself_cannot_use_tail_exception():
    audit={'valid':False,'errors':['not_settled_tail_speed=0.24'],'event_frames':{'all_objects_settle':None}}
    assert not event_audit_usable(audit,'laptop_falls_to_floor',True)
    assert not event_audit_usable(audit,'all_objects_settle',True)


def test_scene_exit_or_other_physical_errors_still_block_exception():
    audit={'valid':False,'errors':['not_settled_tail_speed=0.24','actor_left_frozen_scene_floor=phone'],'event_frames':{'laptop_falls_to_floor':152}}
    assert not event_audit_usable(audit,'laptop_falls_to_floor',True)
