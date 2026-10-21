import types
import pytest
from scripts.genesis_seed_bootstrap import install_seed_control


def test_only_unspecified_or_matching_seed_can_use_supplemental_control():
    calls=[];g=types.SimpleNamespace(init=lambda **kw:calls.append(kw))
    install_seed_control(g,0);g.init(backend='cuda',seed=None);g.init(backend='cuda',seed=0)
    assert calls==[dict(backend='cuda',seed=0)]*2
    with pytest.raises(ValueError,match='different seed'):g.init(seed=123)
    with pytest.raises(ValueError,match='named'):g.init('cuda')
