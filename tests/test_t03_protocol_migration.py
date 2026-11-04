import copy
import json

import pytest

from physedit.core100_critical import load,primary,replay_disclosure
from scripts import migrate_core100_t03_stage_protocol as migration


def sources():
    # Pin the parent so this test remains reproducible after v4 is activated.
    parent=migration.ROOT/'benchmarks/core100_critical_protocol_v3_20261103/registry_d410b8ae4dff.json'
    base,_=load(parent,'d410b8ae4dff5e4fdc874f2c9cdefcb9c8be84360edad4c0afbe90d2d2df48a2')
    readback,_=migration.checked('CURRENT.json');axes,_=migration.checked('ORIGINAL_AXIS_CONTRACT.json')
    return base,readback,axes,migration.read(migration.CANDIDATE/'RGB_REVIEW.json'),migration.read(migration.APPROVAL)


def test_stage_migration_does_not_transfer_unobservable_floor_or_wrong_seed_labels():
    inputs=sources();before=copy.deepcopy(inputs[0]);out=migration.migrate(*inputs)
    assert inputs[0]==before and out['input_bindings']==before['input_bindings']and out['pairs']==before['pairs']
    rows={c['clip_id']:c for c in out['cases']};old={c['clip_id']:c for c in before['cases']}
    c3=rows['T03_C03'];c2=rows['T03_C02']
    for cid in ['T03_C02','T03_C03']:
        row=rows[cid]
        assert row['theta']==old[cid]['theta']and row['normalization_domain']==old[cid]['normalization_domain']
        assert row['stage_event_revision']['old']['reference_events']['phone_second_fall_original']==1
        assert 'phone_second_fall_original'not in row['judge_protocol']['events']
        assert row['stage_event_revision']['original_complete_C2']['formal_RGB_score']is None
        assert row['stage_event_revision']['old_generated_labels_transferred']is False
    assert primary(c3)['intervals']==[[.1,.4]]and primary(c3)['rgb_distance_admitted']
    assert primary(c3)['bin']is None  # Coarse original-domain-normalized range.
    assert replay_disclosure(c3)['onset_offset_frames']==-4
    assert 'stage'in replay_disclosure(c3)['applicability']
    assert primary(c2)['intervals']==[]and not primary(c2)['rgb_distance_admitted']
    assert out['summary']['critical_rgb_distance_cases']==93
    assert out['summary']['admitted_near_cases']==13


@pytest.mark.parametrize('defect',['video','window','endpoint','family','authority','visual_conflict'])
def test_unmatched_state_window_or_event_choice_cannot_migrate(defect):
    base,readback,axes,reviews,approval=sources()
    source=next(p for p in readback['rows']if p['clip_id']=='T03_C03'and p['kind']=='frozen_reference')
    if defect=='video':source['reference_video_sha256']='other'
    if defect=='window':source['measurement']['window_frames']=[4,124]
    if defect=='endpoint':next(p for p in readback['rows']if p['clip_id']=='T03_C03'and p['kind']=='existing_endpoint')['decoded_state_sha256']='other'
    if defect=='family':next(p for p in axes['cases']if p['clip_id']=='T03_C03')['original_parameter']='supplemental_impulse'
    if defect=='authority':approval['cases']=['T03_C01','T03_C02','T03_C03']
    if defect=='visual_conflict':next(p for p in reviews['reviews']if p['clip_id']=='T03_C03')['label']=0
    with pytest.raises(ValueError):migration.migrate(base,readback,axes,reviews,approval)


def test_clear_visual_evidence_cannot_reuse_the_old_unseeded_R032_boundary():
    base,readback,axes,reviews,approval=sources()
    review=next(r for r in reviews['reviews']if r['clip_id']=='T03_C02');review.update(status='observable',label=1)
    out=migration.migrate(base,readback,axes,reviews,approval);row=next(c for c in out['cases']if c['clip_id']=='T03_C02')
    assert migration.EVENT in row['admitted_rgb_events']
    assert primary(row)['intervals']==[]and not primary(row)['rgb_distance_admitted']


def test_corrected_R032_states_complete_numeric_binding_but_do_not_invent_visual_evidence():
    args=sources();pointer=migration.read(migration.ROOT/'review/core100_v3_remaining8_20261103/T03_CORRECT_SEED_COLLECT.json')
    corrected=migration.read(migration.ROOT/pointer['path'])
    out=migration.migrate(*args,corrected);row=next(c for c in out['cases']if c['clip_id']=='T03_C02')
    assert primary(row)['intervals']==[[.1,.4]]and not primary(row)['rgb_distance_admitted']
    assert row['stage_event_revision']['corrected_original_seed_states_used']
    assert len(row['stage_event_revision']['excluded_numeric_attempts'])==1
    assert replay_disclosure(row)['onset_offset_frames']==0
    assert row['rgb_reference_status']=='reference_stage_visual_review_required'
    assert migration.migrate(out,*args[1:],corrected)==out
    altered=copy.deepcopy(corrected)
    next(p for p in altered['points']if p['status']=='completed')['backend']['actual_init_seed']=0
    with pytest.raises(ValueError,match='seed_changed'):migration.migrate(*args,altered)
