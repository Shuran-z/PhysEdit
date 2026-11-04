import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'annotation_site'))
from formal_boundary_evaluation import same_admission,summarize,explicit_admission

def test_ordinary_reference_cannot_admit_an_altered_solver_distance():
    ref=dict(clip_id='T16_C04',reference_video_sha256='v',source_state_sha256='s',reference_release_version='r',horizon_s=5,end_frame_index=154)
    axis=dict(theta=84,reference_events={'contact':1},normalization_span=25,normalization_domain=[65,90])
    boundary=dict(event='contact',bracket=[84.5,85])
    entry=dict(clip_id='T16_C04',family_id='angle',reference_video_sha256='v',reference_state_sha256='s',reference_release_version='r',horizon_s=5,theta=84,reference_label=1,target_event='contact',boundary_interval=[84.5,85],normalization_span=25,distance_admitted=False)
    assert not explicit_admission(ref,'angle',axis,boundary,entry)
    entry['distance_admitted']=True
    assert explicit_admission(ref,'angle',axis,boundary,entry)
    assert not explicit_admission(ref,'other_axis',axis,boundary,entry)
    entry['verified_original_boundary_intervals']=[[84.5,85],[82,83]]
    boundary['bracket']=[82,83]
    assert explicit_admission(ref,'angle',axis,boundary,entry)
    boundary['bracket']=[81,82]
    assert not explicit_admission(ref,'angle',axis,boundary,entry)

def test_admission_cannot_move_to_another_axis_event_window_or_source():
    ref=dict(clip_id='T17_C04',source_state_sha256='s',horizon_s=6.4)
    axis=dict(theta=1.,reference_events={'contact':0},normalization_domain=[0.,4.])
    boundary=dict(event='contact',bracket=[1.1,1.2])
    entry=dict(clip_id='T17_C04',target_event='contact',reference_state_sha256='s',horizon_s=6.4,
        family_id='speed',theta=1.,reference_label=0,boundary_interval=[1.1,1.2],normalization_domain=[0.,4.],
        visual_observability='passed_native_review',reference_admission='admitted_exact_context')
    assert same_admission(ref,'speed',axis,boundary,entry)
    alias=copy.deepcopy(entry);alias['family_id']='initial_speed'
    assert same_admission(ref,'can_initial_speed_mps',axis,boundary,alias)
    for key,value in [('reference_state_sha256','old'),('horizon_s',5.),('family_id','force'),('target_event','fall'),('theta',2.),('boundary_interval',[1.1,1.3])]:
        wrong=copy.deepcopy(entry);wrong[key]=value
        assert not same_admission(ref,'speed',axis,boundary,wrong)

def test_pending_is_not_zero_or_removed_from_frozen_denominator():
    rows=[dict(correct=1,blockers=[]),dict(correct=None,blockers=['window_missing']),dict(correct=0,blockers=[])]
    summary=summarize(rows)
    assert summary['registered']==3 and summary['scored']==2 and summary['pending']==1
    assert summary['accuracy_on_scored']==.5 and summary['complete_cohort_accuracy']is None
    assert summary['fixed_denominator_bounds']==[1/3,2/3]
