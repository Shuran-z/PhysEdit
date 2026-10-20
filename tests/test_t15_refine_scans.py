import copy

import pytest

from scripts.t15_refine_existing_scans_worker import interpolate


def test_support_interpolation_preserves_fixed_physics_and_source():
    left=dict(sample_metadata=dict(laptop_edge_margin_m=.1),dynamic_objects=[dict(name='t15v4_driver_book',pose=dict(position=[.2,0,0]),mass=.3),dict(name='t15v4_closed_laptop',pose=dict(position=[.5,0,0]),mass=.6)])
    right=copy.deepcopy(left);right['sample_metadata']['laptop_edge_margin_m']=.2
    for o in right['dynamic_objects']:o['pose']['position'][0]-=.1
    saved=copy.deepcopy(left);mid=interpolate(left,right,.15,'cfB')
    assert mid['dynamic_objects'][0]['pose']['position'][0]==pytest.approx(.15)
    assert left==saved
    right['dynamic_objects'][0]['mass']=.4
    with pytest.raises(ValueError,match='fixed physics'):interpolate(left,right,.15,'cfB')
