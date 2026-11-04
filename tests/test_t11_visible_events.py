import copy
from annotation_site.t11_visible_events import CONTRACT,EVENTS,check,compare,chronology,digest

def binding(start=0):
    return dict(video_sha256='a'*64,protocol_sha256=digest(CONTRACT),fps=30,
        start_frame=start,end_frame=start+150,native_frames=210,horizon_s=5.)

def positive(event):
    b=binding();return {**b,'label':'yes','frames':[60,61],
      'occurrence_frames':[60,61],'evidence_artifacts_verified':True,
      'actor_ids':EVENTS[event]['actors'],'original_identity_continuous':True,
      'boundary_contact_visible':True,'motion_response_visible':True,
      'support_loss_visible':True,'downward_below_table_visible':True}

def test_contact_overlap_and_fall_disappearance_are_not_proof():
    for e,field in [('driver_pencil_contact','motion_response_visible'),('t11_driver_eraser_visible_fall','downward_below_table_visible')]:
        r=positive(e);assert check(r,e,binding())is None
        r[field]=False;assert check(r,e,binding())=='direct_event_evidence_missing'

def test_negative_requires_all_native_frames_and_visible_identity():
    e='driver_pencil_contact';r=positive(e);r.update(label='no',frames=list(range(151)),actors_visible_whole_window=True)
    assert check(r,e,binding())is None
    r['frames'].pop(83);assert check(r,e,binding())=='negative_window_not_observable'
    r['frames']=list(range(151));r['actors_visible_whole_window']=False
    assert check(r,e,binding())=='negative_window_not_observable'

def test_reference_offset_and_changed_binding_rejected():
    e='driver_pencil_contact';r=positive(e);r.update(start_frame=4,end_frame=154)
    assert check(r,e,binding(4))is None
    r['video_sha256']='b'*64;assert check(r,e,binding(4))=='video_sha256_mismatch'
    r['video_sha256']='a'*64;r['frames']=[2,3]
    assert check(r,e,binding(4))=='invalid_evidence_frames'

def test_supplement_cannot_inherit_legacy_boundary_scores_or_force_order():
    e='driver_pencil_contact';r=positive(e)
    out=compare(r,r,e,binding(),binding());assert out['correct']==1
    assert out['NearAcc']is None and out['PairAcc']is None and out['legacy_world_height_score']is None
    assert chronology({'later':dict(label='yes',occurrence_frames=[90,91]),'earlier':dict(label='yes',occurrence_frames=[60,61])})==[('earlier','later')]
    assert chronology({'a':dict(label='yes',occurrence_frames=[60,63]),'b':dict(label='yes',occurrence_frames=[61,64])})==[]
    b=binding();b['horizon_s']=6
    assert compare(r,r,e,binding(),b)['status']=='window_mismatch'

def test_file_evidence_rejects_tamper_and_wrong_video(tmp_path):
    import json,hashlib,pytest
    from scripts.t11_visible_evaluation import observations
    e='driver_pencil_contact';b=dict(id='ref',**binding());r=dict(id='ref',event=e,**positive(e),reviewer_type='Codex_visual_review_not_independent_human_gold')
    artifact=tmp_path/'witness.jpg';artifact.write_bytes(b'test-fixture')
    r['artifacts']=[dict(path='witness.jpg',sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),frames=[60,61],source_video_sha256=b['video_sha256'])]
    path=tmp_path/'reviews.json';path.write_text(json.dumps([r]))
    registry=dict(references=[b],outputs=[])
    assert observations(path,registry,tmp_path)[('ref',e)]['evidence_artifacts_verified']
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError,match='Artifact missing or changed'):observations(path,registry,tmp_path)
    artifact.write_bytes(b'test-fixture');r['artifacts'][0]['source_video_sha256']='b'*64;path.write_text(json.dumps([r]))
    with pytest.raises(ValueError,match='video identity'):observations(path,registry,tmp_path)

def test_fixed_registration_keeps_short_and_unreviewed_outputs_pending():
    from scripts.t11_visible_evaluation import score
    ref=dict(id='ref',**binding());short=dict(id='out',clip_id='ref',model='M',**binding());short['native_frames']=100
    result=score(dict(references=[ref],outputs=[short]),{})
    assert result['registered_event_slots']==5 and result['scored_event_slots']==0
    assert {r['status']for r in result['rows']}=={'insufficient_native_window'}

def test_foreign_actor_quality_failure_is_not_a_negative_event():
    e='driver_pencil_contact';ref=positive(e);out={**positive(e),'quality':'failure','label':None,
        'failure_type':'foreign_actor_intrusion','reason':'Separate orange actor appears.'}
    rb={**binding(),'role':'reference'};ob={**binding(),'role':'output'}
    result=compare(ref,out,e,rb,ob)
    assert result['correct']==0 and result['event_label']is None
    assert result['event_label_agreement']is None
    out['label']='no'
    assert compare(ref,out,e,rb,ob)['correct']is None
    out['label']=None
    assert check(out,e,rb)=='quality_failure_is_not_reference_truth'
