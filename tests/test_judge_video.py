"""Real CPU video evidence and strict per-category visual assessment guards."""
import copy
import json
import pytest
from physedit.judge_video import sampling, local_inputs
from physedit import evaluations as ev, qwen_judge as judge
from test_evaluations import clip, judgement


def test_full_video_includes_last_frame_and_native_pixels(tmp_path, clip):
    e = ev.qwen_evidence(clip[0], clip[1], tmp_path/'e')
    assert e['protocol'] == 'visible_video_full_v2'
    assert e['condition']['size'] == [192,160]
    assert e['frames'][0]['frame_index']==0 and e['frames'][-1]['frame_index']==47
    assert e['frames'][-1]['time_seconds']==47/16
    assert len(e['frames']) % 2 == 0
    assert e['temporal_sampling_error_seconds'] <= .5/16
    ev.verify_evidence(e)
    from pathlib import Path
    Path(e['video']['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='judge_video_drift'):ev.verify_evidence(e)


def test_full_video_budget_rejects_without_clipping():
    with pytest.raises(ValueError, match='exceeds_registered_frame_budget'):
        sampling(3200,30,{'max_video_frames':64})
    assert sampling(81,16,{})[0][-1]==80


def test_processor_missing_video_tensors_rejected(tmp_path, clip):
    e=ev.qwen_evidence(clip[0],clip[1],tmp_path/'e')
    class Processor:
        def apply_chat_template(self,*args,**kwargs):return 'template'
        def __call__(self,**kwargs):return {'input_ids':[1]}
    with pytest.raises(ValueError,match='did_not_encode_video'):
        local_inputs(Processor(),e,'prompt')


@pytest.mark.parametrize('fault',['empty','unobservable_violation','blanket_insufficient','zero_confidence','missing_flag'])
def test_rejects_template_or_inconsistent_judgement(fault):
    v=judgement()
    if fault=='empty':v['identity_change']['evidence']=''
    if fault=='unobservable_violation':v['identity_change'].update(assessable=False,present=True,severity=2)
    if fault=='blanket_insufficient':v['insufficient_evidence']=True
    if fault=='zero_confidence':v['confidence']=0
    if fault=='missing_flag':del v['identity_change']['assessable']
    with pytest.raises(ValueError):judge.parse_judgement(json.dumps(v),require_assessable=True)


def test_unknown_contact_does_not_count_as_absence_or_erase_other_categories():
    v=judgement()
    v['interpenetration'].update(assessable=False,evidence='Contact is hidden; unknown.')
    judge.parse_judgement(json.dumps(v),require_assessable=True)
    r={'sample_id':'one','status':'partial','judgement':v,'reason':'judge_category_not_assessable'}
    s=ev.summarize([{'sample_id':'one'}],[r],'qwen')
    assert s['clear_violation_percent']['interpenetration'] is None
    assert s['category_coverage']['interpenetration']['assessed']==0
    assert s['category_coverage']['camera_motion']['assessed']==1
    assert s['clear_violation_percent']['camera_motion']==0
    assert s['registered']==1 and s['failed']==1


def test_invalid_local_response_retained_without_scoring(tmp_path, monkeypatch):
    jobs=tmp_path/'jobs.jsonl'; spec=tmp_path/'spec.json'; output=tmp_path/'responses.jsonl'
    jobs.write_text(json.dumps({'sample_id':'kept','evidence':{}})+'\n')
    spec.write_text('{}')
    class InvalidModel:
        def __init__(self, config):pass
        def __call__(self, evidence):
            raise judge.InvalidJudgeResponse('judge_missing_visual_reason',
                {'raw':'original rejected answer','processor_inputs':{'video_grid_thw':[1,3]},'backend':'local'})
    monkeypatch.setattr(judge, 'LocalJudge', InvalidModel)
    judge.main(['--spec',str(spec),'--jobs',str(jobs),'--output',str(output)])
    response=json.loads(output.read_text())
    assert response['sample_id']=='kept' and response['status']=='failed'
    assert response['raw']=='original rejected answer'
    assert response['processor_inputs']['video_grid_thw']==[1,3]
    assert 'judgement' not in response
