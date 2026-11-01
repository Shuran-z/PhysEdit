"""A model lacking admitted points must remain unscored, without crashing."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'annotation_site'))
import scoped_critical

def test_model_without_registered_reference_points(tmp_path,monkeypatch):
    refs=[dict(clip_id='T17_C01',reference_label=0),dict(clip_id='T17_C02',reference_label=1)]
    (tmp_path/'reference_window_admission.json').write_text(json.dumps(dict(references=refs,pairs=[{}])))
    (tmp_path/'core100_final_input_policy.json').write_text('{}')
    monkeypatch.setattr(scoped_critical,'RES',tmp_path)
    result=scoped_critical.calculate_scoped([dict(payload=dict(model='missing_reference_model',clip_id='T01_C01'))])
    row=result['per_model'][0]
    assert row['status']=='missing_registered_points'
    assert row['NearAcc'] is row['PairAcc'] is None
    assert row['NearAcc_bounds'] is row['PairAcc_bounds'] is None
    assert row['native_full_horizon'] is False

def test_only_one_side_registered_has_no_pair_bounds(tmp_path,monkeypatch):
    refs=[dict(clip_id='T17_C01',reference_label=0,horizon_s=6.4),dict(clip_id='T17_C02',reference_label=1,horizon_s=6.4)]
    (tmp_path/'reference_window_admission.json').write_text(json.dumps(dict(references=refs,pairs=[{}])))
    (tmp_path/'core100_final_input_policy.json').write_text('{}')
    monkeypatch.setattr(scoped_critical,'RES',tmp_path)
    monkeypatch.setattr(scoped_critical,'validate_remote',lambda p:None)
    monkeypatch.setattr(scoped_critical,'matches_frozen_input',lambda p,policy:True)
    monkeypatch.setattr(scoped_critical,'observation',lambda *args:(1,'human_binary'))
    p=dict(clip_id='T17_C01',model='one_side',seed=0,prompt_variant=1,frames=193,fps=30.,duration_s=6.4,window_s=6.4,video_sha256='fixed',remote_media=dict(size=100),machine=dict(media_verified=dict(sha256='fixed',frames=193,fps=30.,size=100)))
    row=scoped_critical.calculate_scoped([dict(id='one',payload=p)])['per_model'][0]
    assert row['native_full_horizon'] is True
    assert row['status']=='missing_registered_points'
    assert row['NearAcc'] is row['PairAcc'] is None
    assert row['NearAcc_bounds'] is row['PairAcc_bounds'] is None
