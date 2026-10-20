from scripts.t13_current_boundary_worker import precontact_indices


def test_upstream_impact_ends_precontact_comparison_before_contact_frame():
    state={'frames':[
        {'frame_index':i,'contacts':([{'entity_a':'t13_driver_book','entity_b':'t13_falling_book'}] if i==79 else
                                    [{'entity_a':'t13_falling_book','entity_b':'t13_drink_box'}] if i==91 else [])}
        for i in range(168)]}
    assert list(precontact_indices(state))==list(range(79))


def test_missing_telemetry_does_not_assume_unobserved_precontact_window():
    assert list(precontact_indices({'frames':[{'frame_index':i} for i in range(168)]}))==list(range(18))
