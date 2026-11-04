import copy,json
from physedit.core100_bindings import load,ROOT
from scripts.apply_core100_axis_patches import apply_axis_patches

def test_supplemental_axis_merge_preserves_current_original_axis_and_all_other_cases():
    data=load(verify_evidence=True);cases={r['clip_id']:copy.deepcopy(r)for r in data['cases']}
    supplement=json.loads((ROOT/'review/core100_remaining15_followup_20261031/verified_motion_axis_patches.json').read_text(encoding='utf-8'))
    before=copy.deepcopy(cases)
    # A newer original-axis refinement must survive replay of an older speed-axis supplement.
    cases['T20_C01']['boundary_records'][0]['bracket']=[.31,.44]
    expected=copy.deepcopy(cases['T20_C01']['boundary_records'])
    apply_axis_patches(cases,supplement,ROOT,{})
    assert cases['T20_C01']['boundary_records']==expected
    assert all(cases[cid]==before[cid]for cid in cases if cid!='T20_C01')
    assert cases['T20_C01']['reference_events']==before['T20_C01']['reference_events']
    assert cases['T20_C01']['conditional_axes']['book_drive_speed_mps']['boundary_records'][0]['bracket']==[.89453125,.896484375]
