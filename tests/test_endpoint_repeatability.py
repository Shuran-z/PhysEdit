import copy

import pytest

from physedit.core100_bindings import bind_answer,load
from scripts.collect_t11_c02_endpoint_rechecks import summarize


def report(labels):
    rows=[]
    for side,value in enumerate([1.,2.]):
        for index,label in enumerate(labels[side]):
            rows.append(dict(theta=value,repeat_index=index,labels={'event':label},
                hashes_verified=True,original_solver_seed_clock_verified=True,forces_unchanged=True))
    return dict(brackets=[dict(event='event',bracket=[1.,2.],labels=[1,0])],probes=rows)


def test_repeat_disagreement_does_not_become_a_verified_threshold():
    check=summarize(report([[1,0,0],[0,0,0]]))[0]
    assert check['status']=='discordant'
    assert not check['numerical_endpoint_repeatability_confirmed']
    assert not check['physics_quality_approval_granted']


def test_partial_repeats_remain_pending_and_three_agreements_are_local_only():
    assert summarize(report([[1,1],[0]]))[0]['status']=='pending'
    check=summarize(report([[1,1,1],[0,0,0]]))[0]
    assert check['status']=='reproduced'
    assert not check['unique_or_global_threshold_certified']


def test_unverified_or_duplicate_executions_cannot_inflate_repetition_count():
    data=report([[1,1,1],[0,0,0]])
    data['probes'][0]['hashes_verified']=False
    with pytest.raises(ValueError,match='unverified'):summarize(data)
    data=report([[1,1,1],[0,0,0]])
    data['probes'].append(data['probes'][0])
    with pytest.raises(ValueError,match='duplicate'):summarize(data)


@pytest.mark.parametrize('status',['pending','discordant'])
def test_failed_endpoint_rechecks_keep_answer_truth_but_block_usable_boundary(status):
    data=copy.deepcopy(load())
    row=next(r for r in data['cases']if r['clip_id']=='T11_C02')
    axis=row['conditional_axes']['case_friction_coefficient']
    record=axis['boundary_records'][0]
    axis['boundary_records']=[record]
    record['endpoint_repeatability']=dict(status=status)
    answer=dict(point_id=row['clip_id'],events=copy.deepcopy(row['reference_events']),
        target_event=record['event'])
    before=copy.deepcopy(answer)
    result=bind_answer(answer,reference_video_sha256=row['reference_video_sha256'],
        horizon_s=row['horizon_s'],axis=axis['parameter'],registry=data)
    assert result['boundary']['status']=='unavailable'
    assert result['events']==answer['events'] and answer==before
    assert record['bracket'] and record['endpoint_labels']==[1,0]


def test_verified_uniform_readback_does_not_exclude_or_relabel_source():
    from scripts.audit_core100_pending6_readback import apply_readback
    row=dict(clip_id='case',sample_id='source',reference_video_sha256='a',
        end_frame_index=154,horizon_s=5.,reference_events={'event':1},status='incomplete',
        theta=.1,boundary_records=[])
    before=copy.deepcopy(row)
    item={k:copy.deepcopy(row[k])for k in ['clip_id','sample_id','reference_video_sha256','end_frame_index','horizon_s']}
    item.update(family='original',verified_distinct_probes=10,labels_by_event={'event':[1]},
        opposite_endpoints_observed=False)
    apply_readback({'case':row},{'cases':[item]},'proof.json')
    assert all(row[k]==v for k,v in before.items())
    assert row['completed_original_scan_readback']['no_applicability_exclusion_granted']
    item['end_frame_index']=209
    with pytest.raises(ValueError,match='reference_or_window_changed'):
        apply_readback({'case':row},{'cases':[item]},'proof.json')


def test_reproduced_wide_bracket_is_added_without_replacing_discordant_narrow_evidence():
    from scripts.collect_t11_c02_endpoint_rechecks import apply_report
    from physedit.core100_bindings import original_family_reference_ready
    data=copy.deepcopy(load());row=next(r for r in data['cases']if r['clip_id']=='T11_C02')
    axis=row['conditional_axes']['case_friction_coefficient']
    axis['boundary_records']=[b for b in axis['boundary_records']if b['bracket'][1]-b['bracket'][0]<.01]
    truth=copy.deepcopy(row['reference_events']);source=copy.deepcopy(row['theta'])
    evidence={k:row[k]for k in ['clip_id','sample_id','reference_video_sha256','horizon_s','end_frame_index']}
    evidence.update(source_vector=source,family=axis['parameter'],
        source_config_sha256=row['original_reference_review']['original_record']['original_config_sha256'],
        probes=[],brackets=[])
    for b in axis['boundary_records']:
        evidence['brackets'].append(dict(event=b['event'],bracket=b['bracket'],labels=b['endpoint_labels']))
        for theta,label in zip(b['bracket'],b['endpoint_labels']):
            for index in [0,1,2]:
                evidence['probes'].append(dict(theta=theta,repeat_index=index,labels={b['event']:label},
                    hashes_verified=True,original_solver_seed_clock_verified=True,forces_unchanged=True))
    event=axis['boundary_records'][0]['event']
    evidence['probes'][1]['labels'][event]=0  # A known failing narrow endpoint.
    evidence['brackets'].append(dict(event=event,bracket=[1.2,2.],labels=[1,0],
        required_endpoint_execution_indices=[[0,4],[0,5]],matched_device_required=True))
    for theta,label,repeat in [(1.2,1,4),(2.,0,5)]:
        for index in [0,repeat]:
            evidence['probes'].append(dict(theta=theta,repeat_index=index,labels={event:label},
                hashes_verified=True,original_solver_seed_clock_verified=True,forces_unchanged=True,
                gpu_identity={'selected_gpu_uuid':'same-device'}))
    apply_report({row['clip_id']:row},evidence,'rechecked-proof.json')
    assert len(axis['boundary_records'])==3
    assert axis['boundary_records'][0]['endpoint_repeatability']['status']=='discordant'
    assert axis['boundary_records'][-1]['endpoint_repeatability']['status']=='reproduced'
    assert row['reference_events']==truth and row['theta']==source
    assert not original_family_reference_ready(row)
    result=bind_answer(dict(point_id=row['clip_id'],target_event=event,events=truth),
        reference_video_sha256=row['reference_video_sha256'],horizon_s=row['horizon_s'],
        axis=axis['parameter'],registry=data)
    assert result['boundary']['bracket']==[1.2,2.]
