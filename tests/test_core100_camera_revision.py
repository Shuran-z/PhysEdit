import copy
import json
import math
from pathlib import Path
import sys

import pytest

from physedit import boundary,core100_critical as critical,core100_rebalanced as roster


def prepared():
    pointer=critical.ROOT/'catalog/prepared_core100_critical_protocol_v4.json'
    data=json.loads(pointer.read_text());path=(pointer.parent/data['registry']).resolve()
    return critical.load(path,data['registry_sha256'])


def test_camera_revision_changes_only_one_input_and_keeps_prior_rosters():
    data,_=prepared()
    _,old,old_tasks,_=roster.load(critical.ROOT/'catalog/core100_critical_pairs_v3.json')
    root,new,new_tasks,mapping=roster.load(critical.ROOT/'catalog/core100_critical_pairs_v4.json')
    assert new['registered_cases']==100 and new['scene_counts']==old['scene_counts']
    assert new['retained']==99 and new['replaced']==1
    assert len(new['model_generation_and_annotation_pending'])==15
    assert [t['clip_id']for a,t in zip(old_tasks,new_tasks)if a!=t]==['T03_C02']
    a=next(t for t in old_tasks if t['clip_id']=='T03_C02');b=next(t for t in new_tasks if t['clip_id']=='T03_C02')
    assert a['reference']['sha256']!=b['reference']['sha256']
    assert a['prompt_variants_en']==b['prompt_variants_en']
    assert b['new_generation_required']and b['new_annotation_required']
    assert not b['legacy_generated_outputs_reusable']and not b['legacy_annotations_reusable']
    assert not b['legacy_inversion_calibration_reusable']
    assert critical.sha(critical.ROOT/b['reference']['local_path'])==b['reference']['sha256']
    assert critical.load()[0]['roster_release']=='core100-critical-pairs-v2-20261101'


def test_camera_changes_do_not_change_physics_clock_or_numerical_boundary():
    from scripts.build_core100_camera_revision import physical_config
    data,_=prepared();row=next(r for r in data['cases']if r['clip_id']=='T03_C02')
    parent=critical.load(critical.ROOT/data['camera_revision_parent']['path'],data['camera_revision_parent']['sha256'])[0]
    old=next(r for r in parent['cases']if r['clip_id']=='T03_C02')
    a=copy.deepcopy(critical.primary(old));b=copy.deepcopy(critical.primary(row))
    for u in [a,b]:
        for k in ['reference_id','rgb_distance_admitted','rgb_blockers']:u.pop(k)
    assert a==b
    assert row['horizon_s']==old['horizon_s']==5.
    assert row['normalization_domain']==old['normalization_domain']==[.006,.1]
    assert critical.primary(row)['intervals']==[[.1,.4]]
    assert critical.primary(row)['bin']is None
    root=critical.ROOT/'benchmarks/core100_critical_pairs_v4_20261103/evidence'
    c2=json.loads((root/'cam02_source_config.json').read_text());c3=json.loads((root/'cam03_source_config.json').read_text())
    assert physical_config(c2)==physical_config(c3)
    altered=copy.deepcopy(c2);altered['random_seed']+=1
    assert physical_config(altered)!=physical_config(c3)
    assert data['summary']['critical_rgb_distance_cases']==100
    assert data['summary']['critical_rgb_distance_pending']==[]


def test_old_camera_binding_is_rejected_and_new_reference_is_available(tmp_path):
    data,path=prepared();out=tmp_path/'plan'
    critical.prepare(out,'SYNTHETIC_ONLY',fps=24.,registry_path=path,expected_sha256=critical.sha(path))
    answer=next(k for k in boundary.read_rows(out/'answers.jsonl')if k['clip_id']=='T03_C02')
    row=next(r for r in data['cases']if r['clip_id']=='T03_C02')
    assert answer['boundary']['status']=='verified'
    with pytest.raises(ValueError,match='critical_reference_identity_mismatch'):
        critical.bind_answer(answer,reference_video_sha256=row['camera_revision']['previous_video_sha256'],horizon_s=5.,registry=data)
    assert all(k['inversion']['status']=='pending_reference_validation'for k in boundary.read_rows(out/'answers.jsonl'))


def test_all300_new_inputs_route_review_and_score_without_dropping_failed_outputs(tmp_path,monkeypatch):
    """Synthetic contract test only, not model/VLM/human accuracy evidence."""
    data,path=prepared();plan=tmp_path/'plan'
    critical.prepare(plan,'SYNTHETIC_ONLY',fps=24.,seeds=(0,1,2),registry_path=path,expected_sha256=critical.sha(path))
    inputs=boundary.read_rows(plan/'inputs.jsonl');source={i['sample_id']:i for i in inputs}
    first=lambda cid:next(i['sample_id']for i in inputs if i['clip_id']==cid)
    gen_bad=first('T06_C02');quality_bad=[i['sample_id']for i in inputs if i['clip_id']=='T18_C01'][1]
    uncertain=first('T03_C02')
    def fake_media(video,row):
        if row['sample_id']==gen_bad:raise ValueError('SYNTHETIC_GENERATION_FAILURE')
        video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(('FIXTURE_'+row['sample_id']).encode())
        return dict(status='ok',video=str(video),video_sha256=boundary.digest(video))
    monkeypatch.setattr(boundary,'media',fake_media)
    spec=json.loads((plan/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    run=tmp_path/'run';boundary.run(spec,run)
    answers={a['sample_id']:a for a in boundary.read_rows(run/'answers.jsonl')}
    qualities=[];reviews=[]
    for row in boundary.read_rows(run/'observed_rows.jsonl'):
        if row['status']!='ok':continue
        sid=row['sample_id'];end=math.floor(source[sid]['evaluation_duration_s']*24+1e-6)/24
        bad=sid==quality_bad
        qualities.append(dict(sample_id=sid,video_sha256=row['video_sha256'],status='ok',quality=dict(
            status='unmeasurable'if bad else'measurable',failure='fusion'if bad else'none',
            target_integrity='corrupted'if bad else'intact',support_integrity='intact',confidence=.99,
            evidence_times_s=[0,end],reason='Synthetic fixture only.')))
        target=answers[sid]['target_event']
        reviews.append(dict(sample_id=sid,video_sha256=row['video_sha256'],reviewer='SYNTHETIC_ONLY',
            evidence='Synthetic contract fixture, not human gold.',quality_status='confirmed_failure'if bad else'pass',
            events={}if bad or sid==uncertain else{target:dict(label=answers[sid]['events'][target],evidence='Synthetic oracle.')}))
    qp=tmp_path/'quality.jsonl';rp=tmp_path/'reviews.jsonl';boundary.write_rows(qp,qualities);boundary.write_rows(rp,reviews)
    protocol=plan/'judge_protocol.json';scheduled=tmp_path/'scheduled'
    critical.judge(run,protocol,scheduled,quality_file=qp)
    jobs=boundary.read_rows(scheduled/'event_jobs.jsonl');assert len(jobs)==298
    predictions=[]
    for job in jobs:
        sid=job['sample_id'];end=job['last_observed_time_s'];k=answers[sid]
        predictions.append(dict(sample_id=sid,video_sha256=job['video_sha256'],status='ok',
            event_contract_sha256=job['event_contract_sha256'],times_s=[0,end],events={event:dict(
                label='uncertain'if sid==uncertain else'yes'if y else'no',confidence=.99,
                evidence_times_s=[0,end],reason='Synthetic judge fixture only.',contradictions=[])for event,y in k['events'].items()}))
    ep=tmp_path/'events.jsonl';boundary.write_rows(ep,predictions)
    waiting=tmp_path/'waiting';critical.judge(run,protocol,waiting,quality_file=qp,event_file=ep,reviews_file=rp)
    score=json.loads((waiting/'scores.json').read_text())
    assert score['registered']==300 and score['critical_reference_coverage']==1.
    assert score['event_measurement']['pending_decisions']==1
    assert score['event_measurement']['target_coverage']==pytest.approx(297/300)
    target=answers[uncertain]['target_event']
    next(r for r in reviews if r['sample_id']==uncertain)['events']={target:dict(label=answers[uncertain]['events'][target],evidence='Synthetic adjudication.')}
    final_reviews=tmp_path/'final_reviews.jsonl';boundary.write_rows(final_reviews,reviews)
    final=tmp_path/'final';critical.judge(run,protocol,final,quality_file=qp,event_file=ep,reviews_file=final_reviews)
    score=json.loads((final/'scores.json').read_text())
    assert score['registered']==300 and score['critical_reference_coverage']==1.
    assert score['near_registered_reference_points']==14 and score['near_accuracy']==pytest.approx(35/36)
    assert score['independent_pair_accuracy']==pytest.approx((4+2/3)/5)
    assert score['coupled_pair_accuracy']==pytest.approx((7+2/3)/8)
    assert score['event_measurement']['pending_decisions']==0
    assert score['event_measurement']['final_decision_count']==300
    assert score['event_measurement']['target_coverage']==pytest.approx(298/300)
    assert score['event_exact']is None and score['boundary_error']is None
    assert score['inversion']['eligible']==0 and score['inversion']['registered']==300
