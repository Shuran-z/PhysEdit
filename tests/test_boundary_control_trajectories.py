import pytest
from scripts.analyze_boundary_controls import trajectory_difference


def test_equal_labels_do_not_imply_equal_trajectories():
    a=[dict(objects=[dict(name='book',position=[0.,0.,0.])])]*2
    b=[a[0],dict(objects=[dict(name='book',position=[.01,0.,0.])])]
    assert trajectory_difference(a,b)==dict(max_position_difference_m=.01,first_difference_over_1mm_frame=1)


def test_incomplete_or_lost_object_tracks_cannot_appear_consistent():
    with pytest.raises(ValueError,match='incomplete'):trajectory_difference([],[])
    with pytest.raises(ValueError,match='identities'):trajectory_difference([dict(objects=[dict(name='a',position=[0,0,0])])],[dict(objects=[])])
    a=[dict(objects=[dict(name='a',position=[0.,0.,0.]),dict(name='b',position=[0.,0.,0.])])]
    b=[dict(objects=[dict(name='a',position=[0.,0.,0.]),dict(name='b',position=[float('nan'),0.,0.])])]
    with pytest.raises(ValueError,match='nonfinite'):trajectory_difference(a,b)
