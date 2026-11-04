import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from physedit import core100_critical as critical
from physedit import core100_rebalanced as roster
from scripts.build_core100_six_replacement_roster import TARGETS, source_truth, state, WORK, new_prompts

ROOT=Path(__file__).resolve().parents[1]


def prepared():
    p=json.loads((ROOT/'catalog/prepared_core100_critical_protocol_v3.json').read_text())
    path=(ROOT/'catalog'/p['registry']).resolve()
    return critical.load(path,p['registry_sha256'])


def test_new_roster_preserves_exactly_94_parent_inputs_and_old_pointer():
    _,old,old_tasks,_=roster.load()
    _,new,new_tasks,mapping=roster.load(ROOT/'catalog/core100_critical_pairs_v3.json')
    assert old['version']=='core100-critical-pairs-v2-20261101'
    assert Counter(t['clip_id'][:3]for t in new_tasks)=={f'T{i:02}':5 for i in range(1,21)}
    assert {r['clip_id']for r in mapping}==set(TARGETS)
    assert all(a==b for a,b in zip(old_tasks,new_tasks)if a['clip_id']not in TARGETS)
    assert all(a['reference']['sha256']!=b['reference']['sha256']for a,b in zip(old_tasks,new_tasks)if a['clip_id']in TARGETS)
    assert len(new['model_generation_and_annotation_pending'])==14
    assert all(not t['legacy_annotations_reusable']and not t['legacy_generated_outputs_reusable']for t in new_tasks if t['clip_id']in TARGETS)


def test_prepared_protocol_does_not_change_active_protocol_or_old_inputs():
    old,_=critical.load();new,_=prepared()
    assert old['roster_release']=='core100-critical-pairs-v2-20261101'
    assert new['roster_release']=='core100-critical-pairs-v3-20261103'
    a={r['clip_id']:r for r in old['input_bindings']};b={r['clip_id']:r for r in new['input_bindings']}
    assert all(a[cid]==b[cid]for cid in a if cid not in TARGETS)
    assert new['summary']['numerical_boundary_cases']==100
    assert new['summary']['critical_rgb_distance_pending']==['T03_C02']


def test_new_labels_are_read_from_their_own_states():
    expected={'T04_C02':0,'T06_C02':0,'T06_C03':1,'T10_C05':1,'T18_C01':1,'T18_C02':0}
    data,_=prepared();rows={r['clip_id']:r for r in data['cases']}
    for cid,y in expected.items():
        theta,events,end,_=source_truth(state(cid),cid)
        assert list(events.values())==[y]
        u=critical.primary(rows[cid]);assert u['theta']==theta and u['label']==y and rows[cid]['end_frame_index']==end
        assert rows[cid]['old_outputs_or_labels_transferred']is False


def test_clock_uses_remaining_static_hold_and_does_not_leak_event():
    s=state('T18_C01');schedule,texts=new_prompts(s,'T18_C01',.04,None,154,{})
    assert schedule['extractor_start_from_condition_s']==pytest.approx(1.4-4/30)
    assert schedule['extractor_release_from_condition_s']==pytest.approx(3.2-4/30)
    assert schedule['physical_observation_duration_s']==5.
    assert len(texts)==3
    assert all('0.04'in t and 'release'in t and 'contact'not in t and 'collapse'not in t for t in texts)


def test_prepared_export_binds_new_roster_and_leaves_unknown_reference_unscored(tmp_path):
    data,path=prepared();out=tmp_path/'run'
    critical.prepare(out,'preflight_only',fps=24,seeds=(0,),registry_path=path,expected_sha256=critical.sha(path))
    rows=[json.loads(l)for l in(out/'inputs.jsonl').read_text().splitlines()]
    keys=[json.loads(l)for l in(out/'answers.jsonl').read_text().splitlines()]
    assert len(rows)==len(keys)==100
    assert all(r['reference_release_version']==data['roster_release']for r in rows)
    c=next(k for k in keys if k['clip_id']=='T03_C02')
    assert c['boundary']['status']=='unavailable'
    assert all(k['full_EventExact_applicable']is False for k in keys)


def test_registered_observation_contract_cannot_be_downgraded(tmp_path,monkeypatch):
    from physedit import boundary
    import sys
    _,path=prepared();out=tmp_path/'input';critical.prepare(out,'SYNTHETIC_NOT_MODEL',fps=24.,registry_path=path,expected_sha256=critical.sha(path))
    spec=json.loads((out/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    def fake_media(video,row):
        video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(row['sample_id'].encode())
        return dict(status='ok',video=str(video),video_sha256=boundary.digest(video))
    monkeypatch.setattr(boundary,'media',fake_media);run=tmp_path/'run';boundary.run(spec,run)
    protocol=json.loads((out/'judge_protocol.json').read_text());protocol.pop('event_job_schema');bad=tmp_path/'old_contract.json';bad.write_text(json.dumps(protocol))
    with pytest.raises(ValueError,match='observation_contract_changed'):critical.judge(run,bad,tmp_path/'bad')


def test_roster_pointer_guard_rejects_changed_declared_digest(tmp_path):
    data,_=prepared();bad=copy.deepcopy(data);bad['roster_pointer']['sha256']='0'*64
    path=ROOT/'review/core100_six_replacements_20261103/TEST_WRONG_POINTER.json'
    path.write_text(json.dumps(bad),encoding='utf8')
    try:
        with pytest.raises(ValueError,match='critical_roster_pointer_changed'):critical.load(path,critical.sha(path))
    finally:path.unlink()


def test_context_attestation_uses_actual_specs_and_new_rgb_is_explicit():
    from scripts.verify_core100_six_replacement_contexts import verify
    report=verify();assert len(report['checks'])==4
    data,_=prepared();assert data['new_reference_context_verification']==report
    _,_,tasks,_=roster.load(ROOT/'catalog/core100_critical_pairs_v3.json')
    for t in tasks:
        if t['clip_id']in ['T18_C01','T18_C02']:
            assert t['reference']['publication_status']=='prepared_local_reference_not_published'
            assert t['sample_id'].startswith('T18_CRITICAL_GPU_PAIR_20261103_')
            assert t['full_source_physics_config_evidence']['simulation_steps_forbidden']is True


def test_new300_pipeline_keeps_failures_pending_review_and_inverse_coverage_separate(tmp_path,monkeypatch):
    """Synthetic integration labels; no model, VLM or physics accuracy claim."""
    import sys
    import math
    from physedit import boundary
    data,path=prepared();by_case={r['clip_id']:r for r in data['cases']}
    inverse=tmp_path/'inverse_fixture.json';target=by_case['T18_C02']
    inverse.write_text(json.dumps(dict(roster_release=data['roster_release'],references=[dict(
        clip_id='T18_C02',reference_video_sha256=target['reference_video_sha256'],horizon_s=target['horizon_s'],
        status='eligible',reason='SYNTHETIC_PIPELINE_FIXTURE_ONLY',protocol_version='fixture-not-physics-validation',
        validation_evidence='SYNTHETIC_NOT_A_REAL_INVERSION_STUDY',measurement_window_s=[0,1])])),encoding='utf8')
    plan=tmp_path/'input';critical.prepare(plan,'SYNTHETIC_NOT_A_MODEL',fps=24.,seeds=(0,1,2),registry_path=path,
        expected_sha256=critical.sha(path),inversion_registry=inverse)
    inputs=boundary.read_rows(plan/'inputs.jsonl');first=lambda cid:next(i['sample_id']for i in inputs if i['clip_id']==cid)
    failed_generation=first('T06_C02')
    failed_quality=[i['sample_id']for i in inputs if i['clip_id']=='T18_C01'][1]
    def fake_media(video,row):
        if row['sample_id']==failed_generation:raise ValueError('SYNTHETIC_GENERATION_FAILURE')
        video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(('SYNTHETIC_MEDIA_'+row['sample_id']).encode())
        return dict(status='ok',video=str(video),video_sha256=boundary.digest(video),fps=row['output_fps'])
    monkeypatch.setattr(boundary,'media',fake_media)
    spec=json.loads((plan/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    run=tmp_path/'run';boundary.run(spec,run)
    keys={k['sample_id']:k for k in boundary.read_rows(run/'answers.jsonl')};source={i['sample_id']:i for i in inputs}
    qualities=[];reviews=[]
    for video in boundary.read_rows(run/'observed_rows.jsonl'):
        sid=video['sample_id']
        if video['status']!='ok':continue
        quality_bad=sid==failed_quality;end=math.floor(source[sid]['evaluation_duration_s']*24+1e-6)/24
        qualities.append(dict(sample_id=sid,video_sha256=video['video_sha256'],status='ok',quality=dict(
            status='unmeasurable'if quality_bad else'measurable',failure='fusion'if quality_bad else'none',
            target_integrity='corrupted'if quality_bad else'intact',support_integrity='intact',confidence=.99,
            evidence_times_s=[0,end],reason='Synthetic route fixture, not a VLM judgement.')))
        k=keys[sid];event=k['target_event'];human={}if quality_bad or k['clip_id']=='T03_C02'else{
            event:dict(label=k['events'][event],evidence='Synthetic oracle fixture, not human annotation data.')}
        reviews.append(dict(sample_id=sid,video_sha256=video['video_sha256'],reviewer='SYNTHETIC_ADJUDICATION_ONLY',
            evidence='Synthetic integration fixture.',quality_status='confirmed_failure'if quality_bad else'pass',events=human))
    qp=tmp_path/'quality.jsonl';rp=tmp_path/'reviews.jsonl';boundary.write_rows(qp,qualities);boundary.write_rows(rp,reviews)
    scheduled=tmp_path/'scheduled';protocol=plan/'judge_protocol.json';critical.judge(run,protocol,scheduled,quality_file=qp)
    jobs=boundary.read_rows(scheduled/'event_jobs.jsonl');assert len(jobs)==298
    assert all(j['sample_id']not in [failed_generation,failed_quality]for j in jobs)
    predictions=[]
    for j in jobs:
        k=keys[j['sample_id']];end=j['last_observed_time_s']
        predictions.append(dict(sample_id=j['sample_id'],video_sha256=j['video_sha256'],status='ok',
            event_contract_sha256=j['event_contract_sha256'],times_s=[0,end],events={e:dict(
                label='uncertain'if k['clip_id']=='T03_C02'else'yes'if y else'no',confidence=.99,evidence_times_s=[0,end],
                reason='Synthetic event oracle, not a model result.',contradictions=[])for e,y in k['events'].items()}))
    ep=tmp_path/'events.jsonl';boundary.write_rows(ep,predictions)
    pre=tmp_path/'prelabel';critical.judge(run,protocol,pre,quality_file=qp,event_file=ep)
    unreviewed=json.loads((pre/'scores.json').read_text());assert unreviewed['near_accuracy']is None
    final=tmp_path/'final';critical.judge(run,protocol,final,quality_file=qp,event_file=ep,reviews_file=rp)
    value=json.loads((final/'scores.json').read_text())
    negatives=sum(critical.primary(c)['rgb_distance_admitted']and critical.primary(c)['bin']=='near'and critical.primary(c)['label']==0 for c in data['cases'])
    assert value['registered']==300 and value['critical_reference_coverage']==.99
    assert value['near_accuracy']==pytest.approx(1-1/(6*negatives))
    assert value['independent_pair_accuracy']==pytest.approx((4+2/3)/5)
    assert value['coupled_pair_accuracy']==pytest.approx((7+2/3)/8)
    assert value['event_measurement']['pending_decisions']==3
    assert value['event_measurement']['target_coverage']==pytest.approx(295/300)
    assert value['event_exact']is None and value['boundary_error']is None
    inverse_jobs=boundary.read_rows(final/'inversion_candidates.jsonl');assert len(inverse_jobs)==3
    gravity=[]
    for i,j in enumerate(inverse_jobs):
        if i==1:continue
        gravity.append(dict(sample_id=j['sample_id'],video_sha256=j['video_sha256'],status='ok',
            gravity=keys[j['sample_id']]['gravity']*(1.1 if i==0 else 1.),reference_registration_sha256=critical.sha(inverse)))
    gp=tmp_path/'inverse_predictions.jsonl';boundary.write_rows(gp,gravity)
    measured=critical.score(run,annotations=final/'critical_annotations.jsonl',screening=final/'screening.jsonl',gravity=gp)
    assert measured['inversion']['registered']==300 and measured['inversion']['eligible']==3 and measured['inversion']['fitted']==2
    assert measured['inversion']['registered_coverage']==pytest.approx(2/300)
    assert measured['inversion']['relative_deviation_mean']==pytest.approx(.05)
