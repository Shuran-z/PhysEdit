import copy

import pytest

from physedit.core100_critical import load,primary
from scripts.attach_core100_remaining_resolution import apply_t04_repeat_evidence,proof


def fixtures():
    base,_=load();source,_=proof('T04_SOURCE_CONTRACT.json');repeats,_=proof('T04_RECHECK_COLLECT.json')
    return base,source,repeats


def test_failed_same_seed_endpoint_repeats_cannot_be_admitted_as_a_root():
    base,source,repeats=fixtures();old=copy.deepcopy(base)
    updated=apply_t04_repeat_evidence(base,source,repeats)
    assert base==old and updated['input_bindings']==base['input_bindings']
    row=next(c for c in updated['cases']if c['clip_id']=='T04_C02')
    assert not primary(row)['rgb_distance_admitted']
    assert all(.125 not in bracket for bracket in primary(row)['intervals'])
    assert row['original_endpoint_instability']['labels']==[1,0,0]
    assert row['reference_events']==next(c for c in old['cases']if c['clip_id']=='T04_C02')['reference_events']


@pytest.mark.parametrize('defect',['state','seed','running','unknown','new_pattern'])
def test_source_alias_or_unfinished_repeat_does_not_close_admission(defect):
    base,source,repeats=fixtures()
    if defect=='state':source['native_stored_sha256']='wrong'
    if defect=='seed':source['saved_source_seed']+=1
    if defect=='running':repeats['rows'][0]['status']='running'
    if defect=='unknown':repeats['rows'][0]['measurement']['label']=None
    if defect=='new_pattern':repeats['rows'][0]['measurement']['label']=1
    with pytest.raises(ValueError):apply_t04_repeat_evidence(base,source,repeats)
