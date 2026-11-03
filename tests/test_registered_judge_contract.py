import copy
import json

import pytest

from physedit import boundary
from physedit.boundary_pipeline import run_pipeline
from physedit.judge_contract import VERSION,contract_hash,instruction_text,observation_definitions,sampling_valid


@pytest.fixture
def scheduled(tmp_path):
    from tests.test_boundary import BoundaryTests
    helper=BoundaryTests();helper.setUp()
    try:
        run=helper.prepared();protocol=tmp_path/'protocol.json'
        definition=dict(definition='At window end the original upper book contacts the original table.',
            minimum_evidence_times=1,time_semantics='window_end_state',actors=['upper_book','@table'],
            affected_actor_options=['upper_book'],required_contact_pairs=[['upper_book','@table']],
            reference_label=1,theta=.04,distance_bin='near')
        data=dict(event_job_schema=VERSION,samples={sid:dict(target='original upper book',events={'fall':copy.deepcopy(definition)},
            uncertainty_policy='Physical units require calibration; otherwise use uncertain.')for sid in ['p0','p1']})
        protocol.write_text(json.dumps(data),encoding='utf8')
        videos=boundary.read_rows(run/'observed_rows.jsonl');quality=tmp_path/'quality.jsonl'
        boundary.write_rows(quality,[dict(sample_id=v['sample_id'],video_sha256=v['video_sha256'],status='ok',
            quality=dict(status='measurable',failure='none',target_integrity='intact',support_integrity='intact',
                confidence=.99,evidence_times_s=[0,1],reason='Synthetic test only.'))for v in videos])
        out=tmp_path/'schedule';run_pipeline(run,protocol,out,quality_file=quality)
        yield run,protocol,quality,out
    finally:helper.tearDown()


def predictions(out):
    return [dict(sample_id=j['sample_id'],video_sha256=j['video_sha256'],status='ok',
        event_contract_sha256=j['event_contract_sha256'],times_s=[0,.5,1],events={'fall':dict(label='yes',confidence=.99,
            evidence_times_s=[1],contradictions=[],reason='Synthetic last-frame fixture.')})for j in boundary.read_rows(out/'event_jobs.jsonl')]


def test_observation_allowlist_keeps_roles_pairs_and_time_but_not_answers(scheduled):
    _,_,_,out=scheduled;jobs=boundary.read_rows(out/'event_jobs.jsonl');quality=boundary.read_rows(out/'quality_jobs.jsonl')
    for job in jobs:
        event=job['events']['fall'];assert event['actors']==['upper_book','@table']
        assert event['required_contact_pairs']==[['upper_book','@table']]
        assert event['time_semantics']=='window_end_state'
        assert not set(event)&{'reference_label','theta','distance_bin'}
        assert 'calibration'in job['uncertainty_policy']
        assert contract_hash(job)==job['event_contract_sha256']
        text=instruction_text('event prompt',job,'events')
        assert 'upper_book'in text and 'last supplied sample'in text and 'pixels for metres'in text
    assert all(not set(j)&{'events','event_contract_sha256','uncertainty_policy'}for j in quality)


def test_changed_roles_or_clock_cannot_reuse_an_event_prediction(scheduled,tmp_path):
    run,protocol,quality,out=scheduled;records=predictions(out);records[0]['event_contract_sha256']='old_contract'
    ep=tmp_path/'predictions.jsonl';boundary.write_rows(ep,records)
    with pytest.raises(ValueError,match='event_prediction_contract_mismatch'):
        run_pipeline(run,protocol,tmp_path/'bad',quality_file=quality,event_file=ep)


def test_end_state_evidence_must_cite_last_observed_frame(scheduled,tmp_path):
    run,protocol,quality,out=scheduled;records=predictions(out)
    records[0]['events']['fall']['evidence_times_s']=[.5]
    ep=tmp_path/'predictions.jsonl';boundary.write_rows(ep,records)
    dest=tmp_path/'judged';receipt=run_pipeline(run,protocol,dest,quality_file=quality,event_file=ep)
    routes={r['sample_id']:r for r in boundary.read_rows(dest/'routing.jsonl')}
    assert routes['p0']['events']['fall']=='review'and routes['p1']['events']['fall']=='preannotated'
    assert receipt['registered']==2 and receipt['preannotated_event_count']==1
    queue=boundary.read_rows(dest/'review_queue.jsonl');item=next(r for r in queue if r['sample_id']=='p0')
    assert item['machine_review_reasons']==['final_frame_or_full_window_evidence_missing']
    assert item['last_observed_time_s']==1 and item['event_time_semantics']=='window_end_state'


def test_missing_sampling_clock_or_failed_judge_cannot_create_a_prelabel(scheduled,tmp_path):
    run,protocol,quality,out=scheduled;records=predictions(out);records[0]['times_s']=[0,.5]
    ep=tmp_path/'predictions.jsonl';boundary.write_rows(ep,records)
    with pytest.raises(ValueError,match='event_prediction_sampling_contract_invalid'):
        run_pipeline(run,protocol,tmp_path/'bad_clock',quality_file=quality,event_file=ep)
    records=predictions(out);records[0]['status']='evaluator_failure';ep=tmp_path/'failed_predictions.jsonl';boundary.write_rows(ep,records)
    dest=tmp_path/'failed_judge';run_pipeline(run,protocol,dest,quality_file=quality,event_file=ep)
    routes={r['sample_id']:r for r in boundary.read_rows(dest/'routing.jsonl')}
    assert routes['p0']['events']['fall']=='review'


def test_contract_hash_changes_with_temporal_scope_or_tracking_hint():
    job=dict(event_job_schema=VERSION,target='initial book',window_s=1.,generated_fps=24.,last_observed_time_s=1.,
        events={'fall':{'definition':'Contact','time_semantics':'ever'}},uncertainty_policy='unknown -> review')
    old=contract_hash(job);job['events']['fall']['time_semantics']='window_end_state';assert contract_hash(job)!=old
    old=contract_hash(job);job['generated_track_sha256']='new_track';assert contract_hash(job)!=old


def test_observation_contract_rejects_malformed_actor_lists():
    with pytest.raises(ValueError,match='invalid_event_actor_list'):
        observation_definitions({'fall':{'definition':'Contact','actors':{'label':1}}})


@pytest.mark.parametrize('times',[None,[0,{}],[0,True],[0,float('nan')],[0,1,1],[1,0]])
def test_malformed_sampling_is_rejected_without_type_errors(times):
    assert not sampling_valid({'times_s':times},{'generated_fps':24.,'last_observed_time_s':1.})
