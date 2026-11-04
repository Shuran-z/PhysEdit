import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from physedit import boundary
from physedit import critical_supplement as supplement


def test_separate_roster_has_true_opposite_pairs_and_conservative_near_coverage():
    manifest,conditions,truth=supplement.load()
    assert len(conditions)==8 and len(truth['pairs'])==4
    assert {r['scene_id']for r in conditions}=={'T04','T05','T10','T11'}
    near=[r for r in truth['points']if r['distance']['bin']=='near']
    assert len(near)==2 and {r['scene_id']for r in near}=={'T10'}
    assert {next(iter(r['events'].values()))for r in near}=={0,1}
    assert all(r['inversion']['status']=='pending_reference_validation'for r in truth['points'])
    assert not manifest['summary']['formal_model_scores_computed']
    active=json.loads(supplement.ACTIVE.read_text(encoding='utf8'))
    assert active['separate_from_core100']and supplement.sha(supplement.DEFAULT/'MANIFEST.json')==active['manifest_sha256']


def test_export_keeps_all_seeds_and_never_exports_reference_answers(tmp_path):
    result=supplement.export(supplement.DEFAULT,tmp_path/'inputs','TEST_MODEL_ONLY',fps=24,seeds=[0,1])
    assert result['registered']==result['generation_candidates']==16
    rows=boundary.read_rows(tmp_path/'inputs/inputs.jsonl');keys=boundary.read_rows(tmp_path/'inputs/answers.jsonl')
    for row in rows:
        assert not(set(row)&{'events','boundary','distance','reference_download','inversion','target_event'})
        assert row['evaluation_duration_s']<=(row['num_frames']-1)/row['fps']+1e-6
        assert row['condition_sha256']==supplement.sha(row['condition_image'])
        assert row['source_width']>0 and row['source_height']>0
    assert all(k['pairing_mode']=='independent'for k in keys)


def test_declared_hold_and_mixed_source_clock_are_preserved():
    _,conditions,_=supplement.load()
    for row in conditions:
        clock=row['declared_schedule']
        assert row['evaluation_duration_s']==pytest.approx(clock['initial_hold_duration_s']+clock['active_state_frames']*clock['active_frame_period_s'])
        assert all(c['ltx']<=120 and c['cogvideox']<=218 and c['wan']<=504 for c in row['prompt_token_counts'])
    t10=next(r for r in conditions if r['point_id']=='T10_S01')
    assert t10['evaluation_duration_s']==pytest.approx(13/30+192*.02)
    assert t10['evaluation_duration_s']!=pytest.approx(205*.02)
    t11=next(r for r in conditions if r['point_id']=='T11_S01')
    assert '11/6 s'in t11['prompt_variants_en'][0]
    assert 'until relay-case contact'in t11['prompt_variants_en'][0]


def prepared(tmp_path,monkeypatch):
    exported=tmp_path/'export';supplement.export(supplement.DEFAULT,exported,'TEST_FIXTURE_NOT_A_MODEL',fps=24)
    spec=json.loads((exported/'spec.json').read_text());spec['generation_command']=[sys.executable,'-c','pass']
    def synthetic_media(path,row):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(row['sample_id'].encode())
        return dict(status='ok',video=str(path),video_sha256=boundary.digest(path))
    monkeypatch.setattr(boundary,'media',synthetic_media)
    run=tmp_path/'run';boundary.run(spec,run)
    return run,boundary.read_rows(run/'answers.jsonl'),boundary.read_rows(run/'observed_rows.jsonl')


def annotations(tmp_path,keys,observed,*,constant=False):
    data=[]
    for key,video in zip(keys,observed):
        event=key['target_event'];label=1 if constant else key['events'][event]
        data.append(dict(sample_id=key['sample_id'],video_sha256=video['video_sha256'],
            method='unit_test_fixture_only',evidence='Synthetic score-path regression, not generated-video evidence.',events={event:label}))
    path=tmp_path/'annotations.jsonl';boundary.write_rows(path,data);return path


def test_constant_answer_is_not_a_cross_boundary_response(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    result=supplement.score(run,annotations=annotations(tmp_path,keys,videos,constant=True))
    assert result['balanced_accuracy']==.5 and result['near_accuracy']==.5
    assert result['independent_pair_accuracy']==0
    assert result['event_exact']is None and not result['EventExact_applicable']


def test_target_vector_match_is_never_presented_as_full_chain_EventExact(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    result=supplement.score(run,annotations=annotations(tmp_path,keys,videos))
    assert result['balanced_accuracy']==result['near_accuracy']==result['independent_pair_accuracy']==1
    assert result['event_exact']is None and all(r['event_exact']is None for r in result['rows'])
    assert result['inversion']['registered']==8 and result['inversion']['eligible']==0


def test_missing_outputs_stay_in_denominator(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    ann=annotations(tmp_path,keys,videos)
    Path(videos[0]['video']).write_bytes(b'changed_or_failed_generation')
    result=supplement.score(run,annotations=ann)
    assert result['registered']==8 and result['balanced_accuracy']==.875
    assert result['independent_pair_accuracy']==.75
    assert result['event_measurement']['target_coverage']==7/8


def test_supplement_score_rejects_a_different_input_release(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    rows=boundary.read_rows(run/'inputs.jsonl');rows[0]['input_release']='core100'
    (run/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows))
    with pytest.raises(ValueError,match='scope_changed'):supplement.score(run)


def test_reference_labels_cannot_be_replaced_at_score_time(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    key=keys[0];key['events'][key['target_event']]=1-key['events'][key['target_event']]
    (run/'answers.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in keys),encoding='utf8')
    with pytest.raises(ValueError,match='reference_answers_changed'):supplement.score(run)


def test_full_passage_window_cannot_be_shortened_to_fit_runner(tmp_path,monkeypatch):
    run,keys,videos=prepared(tmp_path,monkeypatch)
    rows=boundary.read_rows(run/'inputs.jsonl')
    next(r for r in rows if r['point_id']=='T05_S02')['evaluation_duration_s']=5
    (run/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows),encoding='utf8')
    with pytest.raises(ValueError,match='observation_window_changed'):supplement.score(run)
