from scripts.audit_t11_remaining_failures import summarize


def test_changed_trigger_is_reported_separately_from_configuration_mismatch():
    row=dict(audit_status='compared',job_id='job',original_label=0,replay_label=1,pre_first_contact_max_difference_m=1e-6,
        original_force_phases=[dict(first_contact_frame=80,contact_trigger_frame=86,applied_frames=32)],
        replay_force_phases=[dict(first_contact_frame=80,contact_trigger_frame=87,applied_frames=33)],
        dynamic_specs_match=True,physical_scene_overrides_match=True,timing_match=True,effective_properties_match=True,force_config_match=True)
    s=summarize([row,dict(audit_status='no_completed_probe_receipt')])
    assert s['compared_endpoints']==1 and s['changed_event_labels']==1
    assert not any(s['mismatched_fields'].values())
    assert s['changed_label_force_phase_differences']['first_contact_frame']==0
    assert s['changed_label_force_phase_differences']['contact_trigger_frame']==1
    assert s['changed_label_force_phase_differences']['applied_frames']==1
