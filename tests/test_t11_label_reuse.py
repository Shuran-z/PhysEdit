import copy
import pytest
from scripts import reuse_t11_visible_labels as reuse

@pytest.fixture
def case(monkeypatch):
    monkeypatch.setattr(reuse,'final_annotation',lambda t:t['final'])
    p=dict(protocol_sha256='p',video_sha256='v',window_s=5.,fps=24,frames=121,
       protocol=dict(auxiliary_events={
       'driver_pencil_case_contact':dict(actors=['a','b'],definition='Proximity or pixel overlap alone is insufficient.'),
       'a_leaves_table':dict(actors=['a','@original_tabletop'],definition='Actor completely loses support/contact from table.')}))
    f=dict(protocol_sha256='p',video_sha256='v',quality=dict(status='pass'),
       auxiliary_events={'driver_pencil_case_contact':dict(label='yes'),'a_leaves_table':dict(label='yes')})
    t=dict(id='t',payload=p,final=f,annotations=dict(primary=dict(payload=f,user_id='r01',stage='primary')))
    return t,dict(video_sha256='v',horizon_s=5.)

def test_exact_contact_reuse_keeps_original_record(case):
    t,b=case;before=copy.deepcopy(t)
    x=reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))
    assert x['label']=='yes'and x['source']['user_id']=='r01'and t==before

def test_support_loss_positive_is_not_automatically_visible_fall(case,monkeypatch):
    t,b=case;monkeypatch.setitem(reuse.FALLS,'a_visible_fall','a_leaves_table')
    assert reuse.compatible(t,b,'a_visible_fall',dict(actors=['a']))is None
    t['final']['auxiliary_events']['a_leaves_table']['label']='no'
    assert reuse.compatible(t,b,'a_visible_fall',dict(actors=['a']))['label']=='no'

def test_old_window_or_protocol_mismatch_blocks_reuse(case):
    t,b=case;t['payload']['window_s']=6.4
    assert reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))is None
    t['final']['auxiliary_events']['driver_pencil_case_contact']['label']='no'
    assert reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))['source']['window_mapping']=='negative_over_longer_window_implies_negative_in_five_second_prefix'
    t['payload']['window_s']=5.;t['final']['protocol_sha256']='old'
    assert reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))is None

def test_quality_failure_is_never_reused_as_event_negative(case):
    t,b=case;t['final']['quality']=dict(status='failure',failure='new_object_intrusion')
    x=reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))
    assert x['label']is None and x['physical_correct']==0
    t['final']['quality']['failure']='not_specified'
    x=reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))
    assert x['label']is None and x['source']['original_quality']['failure']=='not_specified'
    t['payload']['window_s']=6.4
    assert reuse.compatible(t,b,'driver_pencil_contact',dict(actors=['a','b']))is None
