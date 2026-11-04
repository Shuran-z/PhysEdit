import pytest
from review.cvpr_experiments_20261031.native_pair_schedule import remaining_schedule

def test_resume_preserves_all_slots_and_prioritizes_counterparts():
    inputs=[{'id':str(i)}for i in range(4)]
    completed=[dict(arm=a,id=s,seed=0)for a,s in [('base','0'),('lora','1'),('base','2'),('lora','2')]]
    schedule=remaining_schedule(inputs,['base','lora'],completed)
    assert [(x['arm'],x['input']['id'])for x in schedule]==[('lora','0'),('base','1'),('base','3'),('lora','3')]
    assert len(schedule)+len(completed)==8

@pytest.mark.parametrize('completed',[
    [dict(arm='base',id='0',seed=1)],
    [dict(arm='base',id='0',seed=0)]*2,
    [dict(arm='base',id='not_in_plan',seed=0)],
    [dict(arm='unknown',id='0',seed=0)],
])
def test_untrusted_prior_results_fail_closed(completed):
    with pytest.raises(AssertionError):remaining_schedule([{'id':'0'}],['base','lora'],completed)

def test_finished_plan_creates_no_replay():
    completed=[dict(arm=a,id='0',seed=0)for a in ['base','lora']]
    assert remaining_schedule([{'id':'0'}],['base','lora'],completed)==[]
