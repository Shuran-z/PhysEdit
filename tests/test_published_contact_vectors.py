from scripts.published_contact_vectors import vector


def sample(recording):
    return dict(scene_id='T17',scene_overrides={'record_contacts':recording},
                actors=[{'name':n} for n in ['t17_can','t17_tissue_box','t17_ramp']],
                contacts=[dict(pair=['t17_can',n],applicable=True,occurred=None,present_at_end=None,first=None)
                          for n in ['t17_tissue_box','t17_ramp']])


def test_explicit_empty_recording_is_negative_but_missing_contract_stays_unknown():
    assert set(vector(sample(True)).values()) == {0}
    assert vector(sample(False)) == {}


def test_inapplicable_pair_is_not_invented_as_negative():
    row=sample(True)
    row['actors']=[{'name':'t17_can'}]
    assert vector(row)=={}
