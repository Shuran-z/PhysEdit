import pytest
from scripts.t07_original_boundary_worker import table_contact


def collision(a,b):return dict(entity_a=a,entity_b=b)


def test_contact_occurrence_is_not_replaced_with_final_state():
    state=dict(render=dict(pre_static_frames=1),scene_overrides=dict(record_contacts=True),frames=[
        dict(frame_index=0,contacts=[]),dict(frame_index=1,contacts=[collision('frozen_tabletop_collision_slab','t07_smartphone')]),dict(frame_index=2,contacts=[])])
    event=table_contact(state)
    assert event['label']==1 and event['first_table_contact_frame']==1


def test_ramp_contact_and_pre_release_table_contact_are_not_E4_hits():
    state=dict(render=dict(pre_static_frames=1),scene_overrides=dict(record_contacts=True),frames=[
        dict(frame_index=0,contacts=[collision('t07_smartphone','frozen_tabletop_collision_slab')]),
        dict(frame_index=1,contacts=[collision('t07_smartphone','t07_document_folder_ramp')])])
    assert table_contact(state)['label']==0


def test_absent_contact_telemetry_is_not_silently_a_negative_label():
    with pytest.raises(ValueError,match='telemetry'):
        table_contact(dict(render={},frames=[dict(frame_index=0)]))
