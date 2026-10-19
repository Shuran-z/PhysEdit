import copy
import hashlib
import json

import numpy as np
import pytest

from gravtrace.camera import Camera, lookat_camera
from gravtrace.motion import ballistic
from physedit.velocity_kinematics import RegisteredPlanes, fit_registered_velocity, sample_digest
from physedit.velocity_kinematics import fit_coverage_velocity


def make_registration(tmp_path, extra_proof=False):
    times=np.linspace(0,.4,17);camera=lookat_camera([1.2,-1.5,.9],[0,0,.2],51,[854,480])
    corners=np.array([[x,y,z] for x in [-.06,.06] for y in [-.03,.03] for z in [-.01,.01]])
    x0=[0,0,.4];v=[1.1,0,.2]
    points=ballistic(times,x0,v,3.71,np.array([0,0,-1]))
    boxes=Camera.from_dict(camera,[854,480]).project_box(points[:,None,:]+corners)
    sample=dict(id='registered',scenario='projectile',fps=40,image_size=[854,480],camera=camera,
                object=dict(position=x0,corners=corners.tolist()),motion=dict(gravity_dir=[0,0,-1],speed=[0,8],
                angle_deg=[-89,89],t0=[0,0]),boxes=dict(frames=list(range(len(times))),times=times.tolist(),xyxy=boxes.tolist()),
                window=dict(contact_check=False))
    header=tmp_path/'header.json';header.write_text(json.dumps({'fps':40,'objects':[{'name':'box','fixed':False,'motion':{'initial_velocity':[37,0,0]}}]}))
    state=tmp_path/'state.npz'
    if extra_proof:points=np.r_[points,points[-1:]+[.01,0,0],points[-1:]+[.02,0,0]]
    np.savez(state,names=np.array(['box']),position=points[:,None,:])
    row=dict(id='registered',status='registered',axis=[1.,0.,0.],object_name='box',max_plane_drift_m=0,
             input_sample_sha256=sample_digest(sample),source_frame_indices=list(range(len(times))),
             source_plane_validation_frames=list(range(len(points))),source_header_path=str(header),source_state_path=str(state),
             source_header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),source_state_sha256=hashlib.sha256(state.read_bytes()).hexdigest())
    registry=tmp_path/'planes.json';registry.write_text(json.dumps([row]));sha=hashlib.sha256(registry.read_bytes()).hexdigest()
    # The stored g is deliberately wrong. It is only an initialization for the
    # separate velocity trajectory, never overwritten or used as a truth label.
    pred=dict(status='ok',gravity=2.99,frames=len(times),params=dict(speed=.5,angle=.1,azimuth=0,t0=0))
    return sample,pred,row,registry,sha


@pytest.mark.parametrize('extra_proof',[False,True])
def test_registered_velocity_recovers_without_changing_frozen_g(tmp_path,extra_proof):
    s,p,row,path,sha=make_registration(tmp_path,extra_proof);before=copy.deepcopy(p)
    r=fit_registered_velocity(s,p,RegisteredPlanes(path,sha))
    assert r['status']=='ok',r
    np.testing.assert_allclose(r['velocity_vector_mps'],[1.1,0,.2],atol=1e-5)
    assert p==before and r['frozen_gravity_result_changed'] is False
    assert r['trajectory_curvature_fitted_for_velocity'] is True


@pytest.mark.parametrize('fault',['source','sample','missing_member','state_nan','outside_frames'])
def test_binding_faults_are_preserved_as_input_failures(tmp_path,fault):
    s,p,row,path,sha=make_registration(tmp_path)
    if fault=='source':
        with open(row['source_header_path'],'a') as f:f.write(' ')
    elif fault=='sample':s['boxes']['xyxy'][0][0]+=1
    elif fault=='missing_member':s['id']='missing'
    elif fault=='state_nan':
        with np.load(row['source_state_path']) as z:points=z['position'].copy()
        points[3,0,1]=np.nan;np.savez(row['source_state_path'],names=np.array(['box']),position=points)
        row['source_state_sha256']=hashlib.sha256(open(row['source_state_path'],'rb').read()).hexdigest()
    else:row['source_plane_validation_frames']=list(range(100))
    if fault in ['state_nan','outside_frames']:
        path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    r=fit_registered_velocity(s,p,RegisteredPlanes(path,sha))
    assert r['status']=='input_failure',r


def test_nonplanar_source_cannot_be_promoted_by_registration(tmp_path):
    s,p,row,path,sha=make_registration(tmp_path)
    with np.load(row['source_state_path']) as z:points=z['position'].copy()
    points[5,0,1]=.004;np.savez(row['source_state_path'],names=np.array(['box']),position=points)
    row['source_state_sha256']=hashlib.sha256(open(row['source_state_path'],'rb').read()).hexdigest()
    path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert fit_registered_velocity(s,p,RegisteredPlanes(path,sha))['status']=='input_failure'


def test_registration_hash_and_truth_leak_rejected(tmp_path):
    s,p,row,path,sha=make_registration(tmp_path)
    with pytest.raises(ValueError):RegisteredPlanes(path,'wrong')
    s['motion']['v0']=[1.1,0,.2]
    assert fit_registered_velocity(s,p,RegisteredPlanes(path,sha))['reason']=='velocity_truth_in_estimator_input'


def test_explicit_inapplicability_keeps_case_without_guessing_plane(tmp_path):
    s,p,row,path,sha=make_registration(tmp_path)
    row.update(status='inapplicable',reason='missing_declared_motion_plane')
    path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert fit_registered_velocity(s,p,RegisteredPlanes(path,sha))==dict(status='inapplicable',reason='missing_declared_motion_plane')


def test_invalid_final_projection_cannot_be_reported_as_success(tmp_path,monkeypatch):
    s,p,row,path,sha=make_registration(tmp_path)
    monkeypatch.setattr(Camera,'project_box',lambda self,points:np.full((len(points),4),np.nan))
    r=fit_registered_velocity(s,p,RegisteredPlanes(path,sha))
    assert r['status']=='fit_failure'
    assert 'invalid_projection' in r['reason']


def test_nonzero_time_offset_cannot_silently_change_velocity_reference(tmp_path):
    s,p,row,path,sha=make_registration(tmp_path)
    p['params']['t0']=.1
    r=fit_registered_velocity(s,p,RegisteredPlanes(path,sha))
    assert r['status']=='inapplicable'
    assert 'reference_conversion' in r['reason']


def make_nonplanar_registration(tmp_path, delay_frames=0):
    s,p,row,path,sha=make_registration(tmp_path)
    times=np.arange(17+delay_frames)/40
    velocity=[1.1,.3,.2]
    points=ballistic(times,s['object']['position'],velocity,3.71,np.array([0,0,-1]))
    frames=list(range(delay_frames,len(times)))
    corners=np.asarray(s['object']['corners'])
    s['boxes']['times']=times[frames].tolist()
    s['boxes']['xyxy']=Camera.from_dict(s['camera'],s['image_size']).project_box(points[frames,None,:]+corners).tolist()
    p['params']['t0']=delay_frames/40
    np.savez(row['source_state_path'],names=np.array(['box']),position=points[:,None,:])
    row.update(status='inapplicable',reason='observed_source_motion_not_in_declared_plane',
               input_sample_sha256=sample_digest(s),source_initial_frame=0,source_frame_indices=frames,
               source_state_sha256=hashlib.sha256(open(row['source_state_path'],'rb').read()).hexdigest())
    path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    return s,p,row,path,sha


@pytest.mark.parametrize('delay_frames',[0,4])
def test_nonplanar_velocity_estimated_at_original_initial_state(tmp_path,delay_frames):
    s,p,row,path,sha=make_nonplanar_registration(tmp_path,delay_frames)
    before=copy.deepcopy(p)
    result=fit_coverage_velocity(s,p,RegisteredPlanes(path,sha))
    assert result['status']=='ok',result
    np.testing.assert_allclose(result['velocity_vector_mps'],[1.1,.3,.2],atol=1e-5)
    assert result['reference']=='declared_initial_state'
    assert result['observation_start_offset_s']==pytest.approx(delay_frames/40)
    assert result['source_model_branch']=='unconstrained_3d' and p==before
    assert not result['high_precision_certified']


@pytest.mark.parametrize('fault',['source_drift','initial_reference','clock','missing_source_sha'])
def test_coverage_does_not_bypass_source_or_clock_faults(tmp_path,fault):
    s,p,row,path,sha=make_nonplanar_registration(tmp_path,4)
    if fault=='source_drift':
        with open(row['source_header_path'],'a') as f:f.write(' ')
    elif fault=='initial_reference':row['source_initial_frame']=1
    elif fault=='clock':p['params']['t0']=.11
    else:del row['source_state_sha256']
    if fault in ['initial_reference','missing_source_sha']:
        path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert fit_coverage_velocity(s,p,RegisteredPlanes(path,sha))['status']=='input_failure'


def test_coverage_preserves_registered_planar_estimate(tmp_path):
    s,p,row,path,sha=make_registration(tmp_path)
    original=fit_registered_velocity(s,p,RegisteredPlanes(path,sha))
    covered=fit_coverage_velocity(s,p,RegisteredPlanes(path,sha))
    assert covered.pop('source_model_branch')=='registered_planar'
    assert covered==original


def test_coverage_rejects_truth_and_invalid_projection(tmp_path,monkeypatch):
    s,p,row,path,sha=make_nonplanar_registration(tmp_path)
    bad=copy.deepcopy(s);bad['motion']['v0']=[1.1,.3,.2]
    assert fit_coverage_velocity(bad,p,RegisteredPlanes(path,sha))['reason']=='velocity_truth_in_estimator_input'
    monkeypatch.setattr(Camera,'project_box',lambda self,points:np.full((len(points),4),np.nan))
    assert fit_coverage_velocity(s,p,RegisteredPlanes(path,sha))['status']=='fit_failure'


def test_original_frame_gap_keeps_true_seconds_without_imputation(tmp_path):
    s,p,row,path,sha=make_nonplanar_registration(tmp_path)
    keep=[k for k in range(17) if k!=5]
    for field in ('times','xyxy','frames'):s['boxes'][field]=[s['boxes'][field][k] for k in keep]
    p['frames']=len(keep)
    row.update(source_frame_indices=keep,input_sample_sha256=sample_digest(s))
    path.write_text(json.dumps([row]));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    result=fit_coverage_velocity(s,p,RegisteredPlanes(path,sha))
    assert result['status']=='ok',result
    assert result['source_observation_gap_count']==1 and result['frames']==16
    np.testing.assert_allclose(result['velocity_vector_mps'],[1.1,.3,.2],atol=1e-5)
