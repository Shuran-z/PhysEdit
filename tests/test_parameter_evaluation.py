"""Numerical and controller fixtures: real CPU fits/media, no generative/SAM GPU."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from gravtrace.camera import Camera, lookat_camera
from gravtrace.motion import ballistic
from physedit import parameter_evaluation as pe, evaluations as ev, phyediting as pipeline
from physedit.evaluation_settings import validate
from physedit.inversion_inputs import item_digest
from physedit.runners import media_contract as media
from physedit.motion_parameters import sliding_displacement
from scripts import phyediting_gen as gen, sam31_frontend as frontend


def write(path, values):
    pe.write_rows(path, values)
    return path


def video(path, boxes, fps=30):
    cap = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'), fps, (854, 480))
    assert cap.isOpened()
    for b in boxes:
        image = np.full((480, 854, 3), 160, np.uint8)
        x, y, u, v = np.rint(b).astype(int)
        cv2.rectangle(image, (x, y), (u, v), (20, 40, 100), -1)
        cap.write(image)
    cap.release()
    return path


def geometry():
    camera = lookat_camera([1.1, -1.4, .8], [0, 0, .2], 43, [854, 480])
    corners = np.array([[x, y, z] for x in [-.07, .07] for y in [-.035, .035] for z in [-.005, .005]])
    return camera, corners


def case(tmp_path, kind='velocity', suffix='a'):
    camera, corners = geometry()
    n, fps, g = 40, 30, 3.71
    t = np.arange(n)/fps
    origin = [.1, 0, .3]
    v0 = [1.1, .2, .3]
    window = dict(start_frame=23, max_frames=13)
    if kind == 'friction':
        d = np.array([-np.cos(np.radians(14)), 0, -np.sin(np.radians(14))])
        v0 = (.15*d).tolist()
        centres = np.asarray(origin) + sliding_displacement(t, .15, g*(np.sin(np.radians(14))-.12*np.cos(np.radians(14))))[:, None]*d
        window = dict(start_frame=23, max_frames=25)
    else:
        centres = ballistic(t, origin, v0, g, np.array([0, 0, -1]))
    boxes = Camera.from_dict(camera, [854, 480]).project_box(centres[:, None, :]+corners)
    source = video(tmp_path/(suffix+'_source.avi'), np.r_[np.repeat(boxes[:1], 23, axis=0), boxes])
    generated = video(tmp_path/(suffix+'_generated.avi'), boxes)
    condition = tmp_path/(suffix+'_condition.png')
    cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_FRAMES,23);ok,bgr=cap.read();cap.release();assert ok
    assert cv2.imwrite(str(condition),bgr)
    item = dict(id=suffix, event='T07' if kind=='friction' else 'T08', gravity=g, fps=fps,
                image_size=[854,480], camera=camera, camera_id='cam01', object_name='book',
                object=dict(position=origin,corners=corners.tolist()), video=source.name, trajectory='fixture',
                window=window, motion=dict(v0=v0,gravity_dir=[0,0,-1]), split='test_id', sensitivity_px=30,
                generation_prompt='A book moves on a fixed table.')
    row = dict(sample_id=suffix+'_seed',item_id=suffix,model_name='fixture',seed=1,gravity_truth=g,
               source_video=str(source),source_video_sha256=media.sha256(source), source_native_fps=fps,
               source_width=854,source_height=480,condition_frame_index=23,condition_image=str(condition),
               output_fps=fps,num_frames=n,generated_video_resized_to_source=str(generated),
               final_resized=str(generated),input_failure=None)
    prompt=tmp_path/(suffix+'_prompt.txt');prompt.write_text('CPU fixture prompt')
    negative=tmp_path/(suffix+'_negative.txt');negative.write_text('CPU fixture negative')
    row.update(prompt_file=str(prompt),negative_prompt_file=str(negative))
    media.seal_completion(row,settings={'fixture':'cpu'})
    frame_ids = list(range(window['max_frames']))
    details = write(tmp_path/(suffix+'_measurements.jsonl'),[dict(id=row['sample_id'],frames=frame_ids,
                video_sha256=media.sha256(generated), statuses=['fixture']*len(frame_ids))])
    track = dict(id=row['sample_id'],fps=fps,video=str(generated),video_sha256=media.sha256(generated),
                 frontend='sam31_single_view_frozen_v4',frontend_manifest_sha256=frontend.sha(frontend.FROZEN/'manifest.json'),
                 tracks={'book':dict(frames=frame_ids,xyxy=boxes[frame_ids].tolist())},reasons=['fixture']*len(frame_ids),
                 measurements_path=str(details),measurements_sha256=media.sha256(details))
    saved = dict(id=row['sample_id'],status='ok',scenario='projectile',gravity=g,frames=len(frame_ids),
                 params=dict(t0=0,speed=.5,angle=.1,azimuth=0))
    entry = None
    if kind=='friction':
        evidence=tmp_path/(suffix+'_source_conditions.json');evidence.write_text(json.dumps({'known_mu':.12,'slope':14}))
        entry=dict(item_id=suffix,item_sha256=item_digest(item),window=window,
                   source_files=[dict(path=str(evidence),sha256=media.sha256(evidence))],
                   conditions=dict(gravity_mps2=g,slope_angle_deg=14,downhill_direction=d.tolist(),initial_position=origin,
                                   world_corners=corners.tolist(),drag_per_second=0,
                                   evidence={k:True for k in ('clock_verified','camera_verified','initial_identity_verified',
                                       'single_plane_sliding','no_external_force','rotation_stable','effective_friction_verified',
                                       'static_equilibrium_verified')}),requested_effective_friction=.12,
                   requested_initial_velocity_mps=v0)
        row['gravity_inapplicable_reason']='reference_motion_not_supported_by_frozen_generation_score'
        # New routing metadata is part of the generated row's immutable seal.
        media.completion_path(row).unlink()
        media.seal_completion(row,settings={'fixture':'cpu'})
    return item,row,track,saved,entry


def register(tmp_path, cases, metrics):
    items={c[0]['id']:c[0] for c in cases};rows=[c[1] for c in cases]
    tracking=tmp_path/'sam31';tracking.mkdir()
    write(tracking/'tracks_v4.jsonl',[c[2] for c in cases])
    spec=dict(evaluation=dict(metrics=metrics),sam3='unused',checkpoint='unused')
    entries=[c[4] for c in cases if c[4]]
    if 'friction' in metrics and entries:
        manifest=write(tmp_path/'friction.jsonl',entries)
        spec['evaluation']['friction']=dict(manifest=str(manifest),manifest_sha256=media.sha256(manifest))
    return spec,rows,items,tracking


def run(tmp_path,cases,metrics):
    spec,rows,items,tracking=register(tmp_path,cases,metrics)
    original=copy.deepcopy([c[3] for c in cases])
    result=ev.run_additional(spec,rows,items,{},tmp_path/'evaluation',
                             gravity_predictions=[c[3] for c in cases],tracking_root=tracking)
    assert [c[3] for c in cases]==original
    return result,spec,rows,items


def test_validation_enables_motion_and_rejects_misspellings():
    assert validate({'metrics':['gravtrace','velocity','friction']})==['gravtrace','velocity','friction']
    with pytest.raises(ValueError):validate({'metrics':['velocity'],'friction':{}})
    with pytest.raises(ValueError):validate({'metrics':['friction'],'friction':{'manifest':'missing'}})
    with pytest.raises(ValueError):validate({'metrics':['velocity'],'velocity':{'target_speed':1}})


def test_real_single_view_velocity_fit_and_full_summary(tmp_path):
    c=case(tmp_path)
    out,_,rows,items=run(tmp_path,[c],['gravtrace','velocity'])
    record=pe.rows(tmp_path/'evaluation/velocity_results.jsonl')[0]
    assert record['status']=='ok',record
    np.testing.assert_allclose(record['estimate_vector_mps'],c[0]['motion']['v0'],atol=1e-5)
    assert out['velocity']['registered']==1 and out['velocity']['coverage_percent']==100
    assert out['velocity']['groups']['split']['test_id']['scored']==1
    assert not record['prediction']['gravity_optimized']


def test_sliding_point_survives_gravity_inapplicability(tmp_path):
    c=case(tmp_path,'friction')
    c[3].update(status='inapplicable',reason='source is sliding')
    out,_,rows,items=run(tmp_path,[c],['gravtrace','velocity','friction'])
    friction=pe.rows(tmp_path/'evaluation/friction_results.jsonl')[0]
    velocity=pe.rows(tmp_path/'evaluation/velocity_results.jsonl')[0]
    assert friction['status']=='ok',friction
    assert friction['estimate']==pytest.approx(.12,abs=1e-5)
    np.testing.assert_allclose(velocity['estimate_vector_mps'],c[0]['motion']['v0'],atol=1e-5)
    combined=ev.attach_summary({'failures':[{'sample_id':c[1]['sample_id']}]},out,['gravtrace','velocity','friction'])
    assert combined['evaluation_failed']==1
    assert combined['evaluations']['friction']['scored']==1


def test_missing_conditions_and_source_failures_stay_in_denominator(tmp_path):
    a=case(tmp_path,suffix='a');b=case(tmp_path,suffix='b')
    b[1]['input_failure']='original_generation_failure'
    out,_,_,_=run(tmp_path,[a,b],['friction','velocity'])
    assert out['friction']['registered']==2 and out['friction']['failed']==2
    reasons=out['friction']['reasons']
    assert reasons['missing_registered_sliding_conditions']==1
    assert any('original_generation_failure' in k for k in reasons)
    assert out['velocity']['scored']==1 and out['velocity']['registered']==2


@pytest.mark.parametrize('fault',['target','missing_frame','source_sha','item_sha','window','injected_boxes','gravity'])
def test_friction_faults_and_targets_cannot_change_fit(tmp_path,fault):
    c=case(tmp_path,'friction')
    if fault=='target':c[4]['requested_effective_friction']=.5
    elif fault=='missing_frame':c[2]['tracks']['book']['xyxy'][6]=None
    elif fault=='source_sha':Path(c[4]['source_files'][0]['path']).write_text('changed')
    elif fault=='item_sha':c[4]['item_sha256']='wrong'
    elif fault=='window':c[4]['window']=dict(start_frame=23,max_frames=90)
    elif fault=='injected_boxes':c[4]['conditions']['boxes_xyxy']=[[1,2,3,4]]
    else:c[4]['conditions']['gravity_mps2']=9.81
    out,_,_,_=run(tmp_path,[c],['friction'])
    record=pe.rows(tmp_path/'evaluation/friction_results.jsonl')[0]
    if fault=='target':
        assert record['status']=='ok'
        assert record['estimate']==pytest.approx(.12,abs=1e-5)
        assert record['relative_error_pct']==pytest.approx(76,abs=.01)
    else:
        assert record['status']!='ok',record
        assert record['reason'] and out['friction']['registered']==1


def test_zero_velocity_reports_absolute_not_relative_error(tmp_path):
    c=case(tmp_path)
    c[0]['motion']['v0']=[0,0,0]
    out,_,_,_=run(tmp_path,[c],['velocity'])
    record=pe.rows(tmp_path/'evaluation/velocity_results.jsonl')[0]
    assert record['status']=='ok' and record['relative_error_pct'] is None
    assert record['absolute_error']>0 and out['velocity']['zero_target_count']==1


def test_static_friction_bound_is_not_point_coverage(tmp_path):
    c=case(tmp_path,'friction')
    c[2]['tracks']['book']['xyxy']=[c[2]['tracks']['book']['xyxy'][0]]*25
    out,_,_,_=run(tmp_path,[c],['friction'])
    record=pe.rows(tmp_path/'evaluation/friction_results.jsonl')[0]
    assert record['status']=='unidentifiable' and record['estimate'] is None
    assert out['friction']['coverage_percent']==0
    assert out['friction']['point_or_bound_coverage_percent']==100
    assert out['friction']['static_bounds']==1


def test_velocity_target_missing_retains_actual_estimate(tmp_path):
    c=case(tmp_path);c[0]['motion'].pop('v0')
    out,_,_,_=run(tmp_path,[c],['velocity'])
    assert out['velocity']['scored']==0 and out['velocity']['point_estimates']==1
    assert out['velocity']['failures'][0]['reason']=='missing_requested_initial_velocity'


def test_tracking_video_drift_never_uses_reference_pixels(tmp_path):
    c=case(tmp_path);c[2]['video_sha256']=c[1]['source_video_sha256']
    out,_,_,_=run(tmp_path,[c],['velocity'])
    assert out['velocity']['scored']==0
    assert any('track_video_sha256_mismatch' in r for r in out['velocity']['reasons'])


def test_parameter_generation_route_keeps_original_g_rejection(tmp_path):
    c=case(tmp_path,'friction');item,row,track,saved,entry=c
    source_reason='reference_motion_not_supported_by_frozen_generation_score'
    row['input_failure']=source_reason
    item_path=write(tmp_path/'items.jsonl',[item]);manifest=write(tmp_path/'friction.jsonl',[entry])
    spec=dict(items=str(item_path),frames=40,fps=30,evaluation=dict(metrics=['gravtrace','friction'],friction=
              dict(manifest=str(manifest),manifest_sha256=media.sha256(manifest))))
    prompt=tmp_path/'prompt';prompt.mkdir();row.update(prompt_file=str(prompt/'prompt.txt'),negative_prompt_file=str(prompt/'negative.txt'))
    template=write(tmp_path/'template.jsonl',[row]);before=template.read_bytes()
    output=pe.parameter_generation_template(spec,template,tmp_path/'new_template.jsonl')
    updated=pe.rows(output)[0]
    assert updated['input_failure'] is None and updated['gravity_inapplicable_reason']==source_reason
    assert template.read_bytes()==before
    # A drifted source registration cannot reuse this route.
    item['object']['position'][0]+=.1
    item_path.write_text(json.dumps(item)+'\n')
    updated=pe.rows(pe.parameter_generation_template(spec,template,tmp_path/'bad_template.jsonl'))[0]
    assert updated['input_failure']==source_reason


def test_gravity_dispatch_never_fits_a_sliding_case(tmp_path,monkeypatch):
    rows=[dict(sample_id='a',item_id='a',gravity_truth=3.71),
          dict(sample_id='b',item_id='b',gravity_truth=3.71,gravity_inapplicable_reason='source_sliding')]
    seen=[]
    def score(args):
        seen.extend(pe.rows(args.rows))
        write(Path(args.out),[dict(id='a',status='ok',gravity=3.7)])
    monkeypatch.setattr(gen,'score',score)
    input_rows=write(tmp_path/'all_rows.jsonl',rows)
    pe.score_gravity(SimpleNamespace(rows=str(input_rows),out=str(tmp_path/'predictions.jsonl')),rows)
    assert [r['sample_id'] for r in seen]==['a']
    predictions=pe.rows(tmp_path/'predictions.jsonl')
    assert len(predictions)==2 and predictions[1]['reason']=='source_sliding'


def test_motion_requests_are_in_generation_prompt_but_not_estimator(tmp_path,monkeypatch):
    c=case(tmp_path)
    spec,rows,items,_=register(tmp_path,[c],['gravtrace','velocity'])
    original=Path(rows[0]['prompt_file']).read_bytes()
    attached=pe.attach_requested_parameters(spec,copy.deepcopy(rows),items,tmp_path/'requests')[0]
    assert attached['parameter_targets']['velocity_mps']==c[0]['motion']['v0']
    assert 'requested world-coordinate velocity' in Path(attached['prompt_file']).read_text()
    assert Path(rows[0]['prompt_file']).read_bytes()==original
    seen=[]
    real=pe.fit_velocity_with_frozen_gravity
    def fit(sample,prediction):
        seen.append(copy.deepcopy(sample))
        assert 'truth' not in sample and 'v0' not in sample['motion']
        assert 'target_v0' not in sample and 'parameter_targets' not in sample
        return real(sample,prediction)
    monkeypatch.setattr(pe,'fit_velocity_with_frozen_gravity',fit)
    result=pe.velocity_case(c[1],c[0],c[2],c[3])
    assert result['status']=='ok' and len(seen)==1


def test_legacy_prompt_unchanged_without_motion_metrics(tmp_path):
    c=case(tmp_path);spec,rows,items,_=register(tmp_path,[c],['gravtrace'])
    before=copy.deepcopy(rows)
    assert pe.attach_requested_parameters(spec,rows,items,tmp_path/'requests')==before
    assert not (tmp_path/'requests').exists()


def test_full_oneclick_and_existing_video_parameters(tmp_path,monkeypatch):
    """Real controller, real videos and numerical parameter solvers; external models replaced by fixtures."""
    cases=[case(tmp_path,'velocity','ballistic'),case(tmp_path,'friction','sliding')]
    cases.append(case(tmp_path,'velocity','missing'))
    cases[-1][0]['video']='absent.avi'
    by_item={c[0]['id']:c for c in cases}
    item_values=[c[0] for c in cases]
    inputs=write(tmp_path/'items.jsonl',item_values)
    catalog=write(tmp_path/'catalog.jsonl',item_values)
    reference=write(tmp_path/'reference.jsonl',[dict(id=c[0]['id'],target=3.71,prediction=
                dict(status='ok',scenario='incline' if c[4] else 'projectile',gravity=3.71,
                     frames=c[0]['window']['max_frames'])) for c in cases])
    manifest=write(tmp_path/'conditions.jsonl',[c[4] for c in cases if c[4]])
    spec=dict(items=str(inputs),data_root=str(tmp_path),compact='unused',model='ltx_i2v',model_dir='unused',
              sam3='unused',checkpoint='unused',generation_command=['cpu-fixture','{manifest}'],
              applicability=dict(benchmark_items=str(catalog),reference_predictions=str(reference),
                   benchmark_sha256=media.sha256(catalog),reference_predictions_sha256=media.sha256(reference)),
              evaluation=dict(metrics=['gravtrace','velocity','friction'],friction=
                   dict(manifest=str(manifest),manifest_sha256=media.sha256(manifest))))
    generating_rows={}
    def boxes_for(item,ids,fps):
        c=by_item[item['id']]
        camera,corners=geometry();t=np.asarray(ids)/fps
        if c[4]:
            conditions=c[4]['conditions'];direction=np.asarray(conditions['downhill_direction'])
            centres=np.asarray(conditions['initial_position'])+sliding_displacement(t,.15,
                3.71*(np.sin(np.radians(14))-.12*np.cos(np.radians(14))))[:,None]*direction
        else:
            centres=ballistic(t,c[0]['object']['position'],[1.1,.2,.3],3.71,np.array([0,0,-1]))
        return Camera.from_dict(camera,[854,480]).project_box(centres[:,None,:]+corners)
    def launch(command,**kw):
        assert command[0]=='cpu-fixture'
        for row in pe.rows(command[1]):
            generating_rows[row['sample_id']]=row
            item=by_item[row['item_id']][0]
            target=Path(row['generated_video_resized_to_source']);target.parent.mkdir(parents=True,exist_ok=True)
            n=row['num_frames'];box=boxes_for(item,range(min(n,25)),row['output_fps'])
            all_boxes=np.r_[box,np.repeat(box[-1:],n-len(box),axis=0)]
            writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'mp4v'),row['output_fps'],(854,480))
            assert writer.isOpened()
            for b in all_boxes:
                image=np.full((480,854,3),160,np.uint8);x,y,u,v=np.rint(b).astype(int)
                cv2.rectangle(image,(x,y),(u,v),(20,40,100),-1);writer.write(image)
            writer.release()
        return SimpleNamespace(returncode=0)
    def prompts(args):
        write(Path(args.out),[dict(id=r['sample_id'],objects={'book':[300,100,360,170]},prompt_frame=0,
                                  input_failure=r.get('input_failure')) for r in pe.rows(args.rows)])
    def track(root,*unused):
        jobs=pe.rows(Path(root)/'all_jobs.jsonl');tracks=[];details=[]
        for job in jobs:
            sid=job['id'];row=generating_rows.get(sid);frames=job['frames'];failure=job['input_failure']
            boxes=boxes_for(by_item[row['item_id']][0],frames,job['fps']).tolist() if row and not failure else [None]*len(frames)
            statuses=[failure or 'cpu-fixture']*len(frames)
            details.append(dict(id=sid,frames=frames,video_sha256=job.get('video_sha256'),statuses=statuses))
            tracks.append(dict(id=sid,video=job['video'],video_sha256=job.get('video_sha256'),fps=job['fps'],
                frontend='sam31_single_view_frozen_v4',frontend_manifest_sha256=frontend.sha(frontend.FROZEN/'manifest.json'),
                tracks={'book':dict(frames=frames,xyxy=boxes)},reasons=statuses))
        path=write(Path(root)/'measurements_v4.jsonl',details)
        for r in tracks:r.update(measurements_path=str(path),measurements_sha256=media.sha256(path))
        write(Path(root)/'tracks_v4.jsonl',tracks)
    g_calls=[]
    def g_fit(sample):
        g_calls.append(copy.deepcopy(sample))
        assert 'v0' not in sample['motion']
        return dict(status='ok',scenario='projectile',gravity=3.71,frames=len(sample['boxes']['frames']),
                    params=dict(t0=sample['boxes']['times'][0],speed=.5,angle=.1,azimuth=0))
    monkeypatch.setattr(pipeline.subprocess,'run',launch)
    monkeypatch.setattr(gen,'track_jobs',prompts)
    monkeypatch.setattr(frontend,'validate_runtime',lambda *a:dict(cpu_fixture=True))
    monkeypatch.setattr(frontend,'run',track)
    monkeypatch.setattr(gen,'safe_fit',g_fit)
    out=pipeline.pipeline(spec,tmp_path/'oneclick')
    assert len(g_calls)==1  # The sliding source never enters gravity fitting.
    assert out['registered']==3 and out['evaluations']['velocity']['registered']==3
    assert out['evaluations']['velocity']['scored']==2
    assert out['evaluations']['friction']['scored']==1
    assert out['evaluation_failed']==3  # Each ID has an unscored stage; never add per-stage counts.
    assert len(pe.rows(tmp_path/'oneclick/evaluation/friction_results.jsonl'))==3
    assert len(pe.rows(tmp_path/'oneclick/evaluation/velocity_results.jsonl'))==3
    for row in pe.rows(tmp_path/'oneclick/observed_rows.jsonl'):
        if row.get('input_failure'):continue
        assert row['parameter_targets']['velocity_mps']==by_item[row['item_id']][0]['motion']['v0']
    saved=(tmp_path/'oneclick/predictions.jsonl').read_bytes()
    # Re-evaluation uses the existing tracks and predictions, with both external stages forbidden.
    monkeypatch.setattr(gen,'safe_fit',lambda *a:pytest.fail('must not refit gravity'))
    monkeypatch.setattr(pipeline.subprocess,'run',lambda *a,**kw:pytest.fail('must not generate'))
    monkeypatch.setattr(frontend,'run',lambda *a:pytest.fail('must reuse complete tracks'))
    again=ev.existing_run(spec,tmp_path/'oneclick',tmp_path/'recheck',execute=True)
    assert again['evaluations']['velocity']['scored']==2
    assert again['evaluations']['friction']['scored']==1
    assert (tmp_path/'oneclick/predictions.jsonl').read_bytes()==saved


def test_friction_preserves_declared_initial_time_across_model_frame_rates(tmp_path):
    c=case(tmp_path,'friction');item,row,track,saved,entry=c
    window=dict(start_frame=24,max_frames=24)
    entry['window']=window
    row.update(output_fps=25,num_frames=40)
    f,t=pe.scope(row,item,window)
    assert t[0]>0  # 25fps observations do not land on the 30fps state origin.
    camera,corners=geometry();d=np.asarray(entry['conditions']['downhill_direction'])
    points=np.asarray(entry['conditions']['initial_position'])+sliding_displacement(np.asarray(t),.15,
        3.71*(np.sin(np.radians(14))-.12*np.cos(np.radians(14))))[:,None]*d
    expected=Camera.from_dict(camera,item['image_size']).project_box(points[:,None,:]+corners)
    # The observation binding is checked independently in other tests. This
    # fixture isolates the asynchronous-clock algebra with exact pixel boxes.
    old=pe.observations
    try:
        pe.observations=lambda *args:expected.tolist()
        result=pe.friction_case(row,item,track,entry)
    finally:
        pe.observations=old
    assert result['status']=='ok',result
    assert result['estimate']==pytest.approx(.12,abs=1e-5)
    assert result['prediction']['speed_at_window_start_mps']==pytest.approx(.15,abs=1e-4)
    assert result['observation_start_offset_s']==pytest.approx(t[0])


def test_default_friction_window_accepts_source_visibility_metadata(tmp_path):
    c=case(tmp_path,'friction');c[0]['window']['edges_visible']={'23':[True]*4}
    c[4].pop('window');c[4]['item_sha256']=item_digest(c[0])
    conditions,window=pe.declaration(c[4],c[0])
    assert window==dict(start_frame=23,max_frames=25)


@pytest.mark.parametrize('fault',[None,'missing','conditions','failed','ties'])
def test_registered_speed_response_preserves_whole_group(tmp_path,fault):
    from physedit.motion_response import summarize
    items={};rows=[];records=[]
    for i,target in enumerate([0,1,2]):
        name=str(i)
        item=dict(id=name,event='T08',camera_id='cam01',object_name='book',split='test_id',gravity=3.71,
                  camera={},object={},window={'start_frame':23,'max_frames':13},motion={'v0':[target,0,0]})
        items[name]=item;rows.append(dict(sample_id=name,item_id=name,model_name='fixture',seed=1))
        records.append(dict(sample_id=name,status='ok',requested=target,estimate=target*1.2,target_vector_mps=[target,0,0]))
    if fault=='conditions':items['2']['gravity']=9.81
    group=dict(group_id='speed',varying_parameter='initial_speed',fixed_controls={'scene':'shared'},
               members=[dict(item_id=k,item_sha256=item_digest(v),value=i) for i,(k,v) in enumerate(items.items())])
    file=tmp_path/'controls.json';file.write_text(json.dumps([group]))
    if fault=='missing':rows.pop();records.pop()
    if fault=='failed':records[1].update(status='input_failure',reason='retained failure')
    if fault=='ties':
        for record in records:record['estimate']=1.
    out=summarize(rows,records,items,'velocity',dict(response_manifest=str(file),response_manifest_sha256=media.sha256(file)),{})
    if fault in ('missing','conditions','failed'):
        assert out['scored_groups']==0 and out['groups'][0]['reason']
        assert len(out['groups'][0]['members'])==3
    else:
        assert out['scored_groups']==1
        assert out['response_slope']['mean']==pytest.approx(0 if fault=='ties' else 1.2)
        assert out['ordering_consistency']['mean']==(0 if fault=='ties' else 1)
        assert out['spearman_rho']['mean']==(None if fault=='ties' else 1)


def test_all_twelve_model_plans_include_motion_stages_without_models(tmp_path,monkeypatch):
    from physedit.runners.oneclick_registry import MODELS
    c=case(tmp_path)
    inputs=write(tmp_path/'items.jsonl',[c[0]])
    catalog=write(tmp_path/'reference_items.jsonl',[c[0]])
    reference=write(tmp_path/'reference.jsonl',[dict(id=c[0]['id'],target=3.71,prediction=
        dict(status='ok',scenario='projectile',gravity=3.71,frames=13))])
    spec=dict(items=str(inputs),data_root=str(tmp_path),compact='unused',model='ltx_i2v',model_dir='unused',
              sam3='unused',checkpoint='unused',generation_command=['never-run','{manifest}'],
              evaluation={'metrics':['gravtrace','velocity','friction']},applicability=
              dict(benchmark_items=str(catalog),reference_predictions=str(reference),
                   benchmark_sha256=media.sha256(catalog),reference_predictions_sha256=media.sha256(reference)))
    monkeypatch.setattr(pipeline.subprocess,'run',lambda *a,**kw:pytest.fail('plan must not start a process'))
    assert len(MODELS)==12
    for model in MODELS:
        own=copy.deepcopy(spec);own['model']=model
        plan=pipeline.execution_plan(own)
        assert {'velocity','friction'}<=set(plan['stages'])
        assert plan['parameter_inputs']['velocity']['registered']==1
        assert plan['gpu_started'] is False


def test_generated_request_target_cannot_change_during_re_evaluation(tmp_path):
    c=case(tmp_path,'friction')
    c[1]['parameter_targets']={'effective_kinetic_friction':.5,'friction_reference_source_frame':23}
    with pytest.raises(ValueError,match='target_changed_since_generation'):
        pe.friction_case(c[1],c[0],c[2],c[4])


def test_missing_and_invalid_scoring_targets_retain_measured_friction(tmp_path):
    c=case(tmp_path,'friction')
    for target in (None,True,-1):
        c[4]['requested_effective_friction']=target
        result=pe.friction_case(c[1],c[0],c[2],c[4])
        assert result['status']!='ok' and result['estimate']==pytest.approx(.12,abs=1e-5)
        assert result['point_estimate_available'] is True


def test_no_friction_sam_work_when_sliding_conditions_unverified(tmp_path,monkeypatch):
    c=case(tmp_path,'friction');c[4]['conditions']['evidence']['rotation_stable']=False
    c[2]['tracks']['book']['frames']=[];c[2]['tracks']['book']['xyxy']=[]
    monkeypatch.setattr(frontend,'prepare',lambda *a:pytest.fail('inapplicable physics must not start SAM'))
    out,_,_,_=run(tmp_path,[c],['friction'])
    assert out['friction']['scored']==0
    assert out['friction']['failures'][0]['status']=='inapplicable'


def test_extra_friction_scope_uses_same_frontend_without_replacing_original_tracks(tmp_path,monkeypatch):
    c=case(tmp_path,'friction');full_track=copy.deepcopy(c[2]);c[4]['window']=copy.deepcopy(c[4]['window']);c[0]['window']['max_frames']=13
    c[4]['item_sha256']=item_digest(c[0])
    c[2]['tracks']['book']['frames']=list(range(13));c[2]['tracks']['book']['xyxy']=full_track['tracks']['book']['xyxy'][:13]
    c[2]['reasons']=['fixture']*13
    detail_path=Path(c[2]['measurements_path'])
    detail_path.write_text(json.dumps(dict(id=c[1]['sample_id'],frames=list(range(13)),
        video_sha256=c[2]['video_sha256'],statuses=['fixture']*13))+'\n')
    c[2]['measurements_sha256']=media.sha256(detail_path)
    spec,rows,items,tracking=register(tmp_path,[c],['friction'])
    before=(tracking/'tracks_v4.jsonl').read_bytes();calls=[]
    def complete(root,*unused):
        jobs=pe.rows(Path(root)/'all_jobs.jsonl');calls.append(jobs)
        assert jobs[0]['frames']==list(range(25))
        result=copy.deepcopy(full_track)
        detail=write(Path(root)/'measurements_v4.jsonl',[dict(id=c[1]['sample_id'],frames=list(range(25)),
            video_sha256=c[2]['video_sha256'],statuses=['fixture']*25)])
        result.update(measurements_path=str(detail),measurements_sha256=media.sha256(detail))
        write(Path(root)/'tracks_v4.jsonl',[result])
    monkeypatch.setattr(frontend,'run',complete)
    initial={c[1]['sample_id']:dict(prompt_frame=0,objects={'book':full_track['tracks']['book']['xyxy'][0]})}
    out=ev.run_additional(spec,rows,items,initial,tmp_path/'evaluation',gravity_predictions=[c[3]],tracking_root=tracking)
    assert out['friction']['scored']==1 and len(calls)==1
    assert (tracking/'tracks_v4.jsonl').read_bytes()==before
    assert (tmp_path/'evaluation/parameter_inputs/friction_manifest.jsonl').read_bytes()==Path(spec['evaluation']['friction']['manifest']).read_bytes()
