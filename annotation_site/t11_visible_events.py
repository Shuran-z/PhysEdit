"""Observable T11 events, scored separately from legacy world-coordinate targets."""
import hashlib
import json

ACTORS=('t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case')
VERSION='t11-visible-events-v1-20261102'
EVENTS={
 'driver_pencil_contact':dict(actors=list(ACTORS[:2]),kind='contact',name='原橡皮碰到原笔盒'),
 'pencil_eyeglasses_contact':dict(actors=list(ACTORS[1:]),kind='contact',name='原笔盒碰到原眼镜盒'),
 **{actor+'_visible_fall':dict(actors=[actor],kind='fall',name=name+'明确离桌下落')
    for actor,name in zip(ACTORS,('原橡皮','原笔盒','原眼镜盒'))}}
CONTRACT=dict(version=VERSION,scope='T11_visible_event_supplement_only',events=EVENTS,
 window='Use each explicitly registered common reference/output observation window; never stretch or retime media.',
 identity='Track the original actors continuously. A new object is never a substitute.',
 contact='At adjacent native frames, establish boundary contact and a visible motion/deformation response; 2D overlap or proximity alone is insufficient.',
 fall='At adjacent native frames, establish original actor losing tabletop support and visibly moving below that same table surface. Disappearance or occlusion alone is insufficient.',
 negatives='Require complete native-frame window coverage and continuous actor visibility in the relevant event region; otherwise leave the event unresolved.',
 sequence='Report observed occurrence intervals and definite temporal precedence only; do not force the intended chain.',
 legacy_world_height_modified=False,inherit_legacy_labels=False,inherit_critical_distances=False,
 NearAcc=None,PairAcc=None)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def check(record,event,binding):
    """Return an eligibility error, never silently coerce unknown to negative."""
    for key in ('video_sha256','protocol_sha256','start_frame','end_frame','fps'):
        if record.get(key)!=binding.get(key):return key+'_mismatch'
    if record.get('protocol_sha256')!=digest(CONTRACT):return 'unknown_protocol'
    if len(binding.get('video_sha256',''))!=64:return 'invalid_video_hash'
    start,end=binding['start_frame'],binding['end_frame']
    if binding['fps']<=0 or start<0 or start>end:return 'invalid_clock'
    if end>=binding['native_frames']:return 'insufficient_native_window'
    frames=record.get('frames',[])
    if not frames or any(type(i)is not int or i<start or i>end for i in frames):return 'invalid_evidence_frames'
    if len(frames)!=len(set(frames)):return 'duplicate_evidence_frames'
    if not record.get('evidence_artifacts_verified'):return 'unverified_witness_artifacts'
    if record.get('quality')=='failure':
        if binding.get('role')!='output':return 'quality_failure_is_not_reference_truth'
        if record.get('label') is not None:return 'quality_failure_must_not_be_event_negative'
        if record.get('failure_type')not in ('foreign_actor_intrusion','original_actor_identity_loss'):return 'unsupported_quality_failure'
        if not record.get('reason')or not any(i+1 in frames for i in frames):return 'quality_witness_missing'
        return None
    if record.get('label')not in ('yes','no'):return 'unresolved'
    rule=EVENTS[event]
    if record.get('actor_ids')!=rule['actors']or not record.get('original_identity_continuous'):return 'original_actor_identity_missing'
    if record['label']=='no':
        if sorted(frames)!=list(range(start,end+1))or not record.get('actors_visible_whole_window'):return 'negative_window_not_observable'
    else:
        if not any(i+1 in frames for i in frames):return 'adjacent_native_frames_missing'
        interval=record.get('occurrence_frames',[])
        if len(interval)!=2 or any(type(i)is not int or i not in frames for i in interval)or interval[0]>interval[1]:return 'occurrence_interval_missing'
        proof=('boundary_contact_visible','motion_response_visible')if rule['kind']=='contact'else('support_loss_visible','downward_below_table_visible')
        if not all(record.get(k)is True for k in proof):return 'direct_event_evidence_missing'
    return None

def compare(reference,output,event,reference_binding,output_binding):
    if (reference_binding['end_frame']-reference_binding['start_frame'])/reference_binding['fps']>(output_binding['end_frame']-output_binding['start_frame'])/output_binding['fps']+1/output_binding['fps']:
        return dict(correct=None,status='output_window_short')
    if reference_binding['horizon_s']!=output_binding['horizon_s']:return dict(correct=None,status='window_mismatch')
    for name,record,binding in [('reference',reference,reference_binding),('output',output,output_binding)]:
        error=check(record,event,binding)
        if error:return dict(correct=None,status=name+'_'+error)
    if output.get('quality')=='failure':
        return dict(correct=0,status='quality_failure_physical_score',event_label_agreement=None,
            event_label=None,physical_correct=0,legacy_world_height_score=None,NearAcc=None,PairAcc=None)
    return dict(correct=int(reference['label']==output['label']),status='visible_event_scored',
        legacy_world_height_score=None,NearAcc=None,PairAcc=None)

def chronology(observations):
    """Intervals that overlap do not establish a definite order."""
    yes={k:v['occurrence_frames']for k,v in observations.items()
         if v.get('label')=='yes'and len(v.get('occurrence_frames',[]))==2}
    return [(a,b)for a,x in yes.items()for b,y in yes.items()if a!=b and x[1]<y[0]]
