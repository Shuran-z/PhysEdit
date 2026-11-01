from pathlib import Path
import pytest
from scripts import combine_recovered_boundary_distances as mod

def test_exact_record_normalization_computes_distance_without_promoting_admission(monkeypatch):
    row={'scene_id':'T02','engine':'genesis','sample_id':'one','theta':1.1,'family_id':'B','original_boundary_interval':[1.,1.01]}
    monkeypatch.setattr(mod,'normalization_patches',lambda:{})
    before=mod.normalize(row,Path('source.jsonl'),'recovered_original')
    patch={before['distance_record_id']:{'normalization_span':.5,'normalization_recovery_evidence':{'source':'frozen_plan'}}}
    monkeypatch.setattr(mod,'normalization_patches',lambda:patch)
    after=mod.normalize(row,Path('source.jsonl'),'recovered_original')
    assert after['normalized_distance_lower']==pytest.approx(.18)
    assert after['normalized_distance_upper']==pytest.approx(.2)
    assert after['binning_grants_formal_admission'] is False
    assert 'normalization_span' not in mod.normalize(dict(row,sample_id='different'),Path('source.jsonl'),'recovered_original')
    with pytest.raises(ValueError):mod.normalize(dict(row,normalization_span=2.),Path('source.jsonl'),'recovered_original')
