import copy,json
from pathlib import Path
import pytest
from scripts import admit_remaining20_references as module

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining20_20261101'

def baseline():
    return json.loads((WORK/'live_before/resources/core100_formal_cohorts.json').read_text(encoding='utf8'))

def test_complete_original_contact_negative_extends_live80_without_boundary_promotion():
    old=baseline();new=module.extend_remaining20(copy.deepcopy(old))
    assert new['cohorts'][:-1]==old['cohorts']
    ref=new['cohorts'][-1]['references'][0]
    assert ref['clip_id']=='T15_C04'and ref['target_event']=='laptop_contacts_phone'
    assert ref['horizon_s']==5 and ref['reference_label']==0
    assert ref['distance_admitted']is False and ref['bin']is None
    assert not new['cohorts'][-1]['pairs']
    assert ref['observability_evidence']['reviewed_native_frames']==list(range(210))
    assert new['summary']['formally_registered_near_points']==old['summary']['formally_registered_near_points']
    assert new['summary']['formally_registered_pairs']==old['summary']['formally_registered_pairs']

def test_missing_native_frame_cannot_satisfy_full_frame_review(monkeypatch):
    read=module.read
    def altered(path):
        value=read(path)
        if path.name=='FULL_FRAME_EXTRACTION.json':
            value=copy.deepcopy(value)
            next(r for r in value if r['clip_id']=='T15_C04')['sheets'][0]['last_frame']=22
        return value
    monkeypatch.setattr(module,'read',altered)
    with pytest.raises(AssertionError):module.extend_remaining20(baseline())

def test_terminal_T11_events_are_not_replaced_with_earlier_falls():
    decisions=json.loads((WORK/'FULL_FRAME_DECISIONS.json').read_text())
    rows=[r for r in decisions if r['clip_id'].startswith('T11')]
    assert len(rows)==5
    assert all(r['status']=='pending_original_terminal_RGB_observability'and r['reference_label']is None for r in rows)
    assert all(r['reviewed_native_frames']==list(range(210))for r in rows)
