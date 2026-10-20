import pytest

from scripts.export_original_boundary_distances import distances


def test_recorded_centre_distance_has_both_sides():
    assert distances(.23,point=.235)['signed_distance']==pytest.approx(-.005)
    assert distances(.26,point=.235)['absolute_distance']==pytest.approx(.025)


def test_interval_does_not_invent_a_point():
    result=distances(.02,bracket=[.018,.019])
    assert result['absolute_distance'] is None
    assert result['distance_lower']==pytest.approx(.001)
    assert result['distance_upper']==pytest.approx(.002)
    assert distances(.0185,bracket=[.018,.019])['distance_lower']==0


def test_missing_value_stays_missing_and_nonfinite_is_rejected():
    assert all(x is None for x in distances(.1).values())
    with pytest.raises(ValueError):distances(float('nan'),point=.2)
