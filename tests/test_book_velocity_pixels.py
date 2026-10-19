import copy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from gravtrace.camera import Camera, lookat_camera
from gravtrace.motion import ballistic
from physedit import book_velocity_pixels
from physedit.book_visibility import clip_polygon, clip_observed_polygon, visibility
from physedit.velocity_pixels import RegisteredVelocityPixels
from physedit.velocity_kinematics import RegisteredPlanes, sample_digest
from test_velocity_kinematics import make_nonplanar_registration


def area(poly):
    q=np.roll(poly,-1,axis=0)
    return abs(np.sum(poly[:,0]*q[:,1]-poly[:,1]*q[:,0]))/2


def test_viewport_clipping_uses_visible_pixel_cells_without_changing_geometry():
    source=np.array([[-1,-1],[3,-1],[3,3],[-1,3]],float);before=source.copy()
    clipped=clip_polygon(source,[2,2])
    assert area(clipped)==pytest.approx(4.)
    assert np.all(clipped>=-.5) and np.all(clipped<=1.5)
    np.testing.assert_array_equal(source,before)


def test_hidden_edge_censors_shape_instead_of_inventing_missing_pixels():
    source=np.array([[-1,-1],[3,-1],[3,3],[-1,3]],float)
    visible=clip_observed_polygon(source,[2,2],[0,0,2,1],[True,True,True,False])
    assert area(visible)==pytest.approx(2.)
    assert visible[:,1].max()==pytest.approx(.5)


def test_interior_segmentation_hole_does_not_change_convex_shape_descriptor():
    full=np.ones((12,18),np.uint8);hole=full.copy();hole[3:7,5:8]=0;before=hole.copy()
    np.testing.assert_allclose(book_velocity_pixels.observed_convex_moments(hole),
                               book_velocity_pixels.observed_convex_moments(full),atol=1e-10)
    np.testing.assert_array_equal(hole,before)


def book_fixture(tmp_path,cropped=False):
    sample,saved,row,plane_path,plane_sha=make_nonplanar_registration(tmp_path)
    # Dense declared cuboid samples are a synthetic observation fixture, not a
    # recovered production mesh. All targets stay outside the estimator input.
    corners=np.array([[x,y,z] for x in [-.12,.12] for y in [-.08,.08] for z in [-.016,.016]])
    points=[]
    for a in corners:
        for b in corners:
            if np.count_nonzero(a!=b)==1:points.extend([(1-q)*a+q*b for q in [0.,.25,.5,.75]])
    sample['object']['corners']=np.unique(points,axis=0).tolist()
    if cropped:
        sample['camera']=lookat_camera([1.2,-1.5,.9],[0,0,.2],18,[854,480])
    camera=Camera.from_dict(sample['camera'],sample['image_size'])
    centres=ballistic(np.array(sample['boxes']['times']),sample['object']['position'],[1.1,.3,.2],3.71,np.array([0,0,-1]))
    uv=camera.project(centres[:,None]+np.asarray(sample['object']['corners']))
    full=camera.project_box(centres[:,None]+np.asarray(sample['object']['corners']))
    boxes=[];flags={};cache={};frames=[]
    for k,poly in enumerate(uv):
        mask=np.zeros((480,854),np.uint8)
        hull=cv2.convexHull(poly.astype(np.float32))
        cv2.fillConvexPoly(mask,np.rint(hull[:,0]).astype(int),1)
        yy,xx=np.where(mask);assert len(xx)>0
        boxes.append([float(xx.min()),float(yy.min()),float(xx.max()+1),float(yy.max()+1)])
        flags[str(k)]=[bool(full[k,0]>1),bool(full[k,1]>1),bool(full[k,2]<853),bool(full[k,3]<479)]
        image=np.full((480,854,3),80,np.uint8);cache['rgb_'+str(k)]=image
        mp=tmp_path/f'mask{k}.npz';np.savez_compressed(mp,mask=mask)
        frames.append(dict(frame=k,bgr_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                           mask_path=str(mp),mask_file_sha256=hashlib.sha256(mp.read_bytes()).hexdigest()))
    sample['boxes']['xyxy']=boxes;sample['window']['edges_visible']=flags
    header=json.load(open(row['source_header_path']));header['objects'][0]['asset_id']='book_textbook_01_v2'
    header['objects'][0]['size']=np.ptp(np.asarray(sample['object']['corners']),axis=0).tolist()
    with open(row['source_header_path'],'w') as f:json.dump(header,f)
    row['source_header_sha256']=hashlib.sha256(Path(row['source_header_path']).read_bytes()).hexdigest()
    row['input_sample_sha256']=sample_digest(sample);plane_path.write_text(json.dumps([row]));plane_sha=hashlib.sha256(plane_path.read_bytes()).hexdigest()
    cp=tmp_path/'cache.npz';np.savez_compressed(cp,**cache)
    pixel=dict(id=sample['id'],sample_sha256=sample_digest(sample),cache_path=str(cp),cache_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),frames=frames)
    pp=tmp_path/'pixels.json';pp.write_text(json.dumps([pixel]));psha=hashlib.sha256(pp.read_bytes()).hexdigest()
    return sample,saved,RegisteredPlanes(plane_path,plane_sha),RegisteredVelocityPixels(pp,psha),row,pixel


@pytest.mark.parametrize('cropped',[False,True])
def test_same_motion_measured_with_full_frames_retained(tmp_path,cropped):
    sample,saved,planes,pixels,row,pixel=book_fixture(tmp_path,cropped)
    before=copy.deepcopy((sample,saved))
    result=book_velocity_pixels.fit_book_pixel_velocity(sample,saved,planes,pixels)
    assert result['status']=='ok',result
    assert abs(result['speed_mps']/np.linalg.norm([1.1,.3,.2])-1)<.08
    assert result['frames']==17 and result['outline_check']['original_frames_retained']==17
    if cropped:assert result['outline_check']['viewport_clipped_frames']>0
    assert not result['new_sam_inference'] and not result['frozen_gravity_result_changed']
    assert (sample,saved)==before


def test_short_window_retained_as_unsupported_new_model(tmp_path):
    sample,saved,planes,pixels,row,pixel=book_fixture(tmp_path)
    for key in ['times','frames','xyxy']:sample['boxes'][key]=sample['boxes'][key][:7]
    saved['frames']=7;row['source_frame_indices']=row['source_frame_indices'][:7];row['input_sample_sha256']=sample_digest(sample)
    p=tmp_path/'short.json';p.write_text(json.dumps([row]));bound=RegisteredPlanes(p,hashlib.sha256(p.read_bytes()).hexdigest())
    r=book_velocity_pixels.fit_book_pixel_velocity(sample,saved,bound,None)
    assert r['status']=='inapplicable' and r['original_velocity_result_preserved']
    assert 'speed_mps' not in r


def test_visibility_must_be_explicit_for_every_original_frame():
    s={'image_size':[854,480],'boxes':{'xyxy':[[10,20,30,40]],'frames':[4]},'window':{}}
    with pytest.raises(ValueError,match='missing_registered_book_edge_visibility'):visibility(s)


def test_future_source_truth_cannot_change_book_fit(tmp_path):
    sample,saved,planes,pixels,row,pixel=book_fixture(tmp_path)
    expected=book_velocity_pixels.fit_book_pixel_velocity(sample,saved,planes,pixels)
    assert expected['status']=='ok',expected
    with np.load(row['source_state_path']) as z:positions=z['position'].copy();names=z['names'].copy()
    positions[1:]=np.nan
    np.savez(row['source_state_path'],names=names,position=positions,velocity=np.full_like(positions,9999.))
    row['source_state_sha256']=hashlib.sha256(Path(row['source_state_path']).read_bytes()).hexdigest()
    p=tmp_path/'changed_future.json';p.write_text(json.dumps([row]));changed=RegisteredPlanes(p,hashlib.sha256(p.read_bytes()).hexdigest())
    assert book_velocity_pixels.fit_book_pixel_velocity(sample,saved,changed,pixels)==expected


def test_pixel_source_drift_stays_failure_not_old_success(tmp_path):
    sample,saved,planes,pixels,row,pixel=book_fixture(tmp_path)
    with open(pixel['cache_path'],'ab') as f:f.write(b'drift')
    r=book_velocity_pixels.fit_book_pixel_velocity(sample,saved,planes,pixels)
    assert r['status']=='input_failure' and 'speed_mps' not in r


def test_book_scoring_entry_isolated_from_target_and_preserves_failure(tmp_path):
    from scripts.phyediting_motion_parameters import evaluate_kinematic_velocity
    sample,saved,planes,pixels,row,pixel=book_fixture(tmp_path)
    plane_path=tmp_path/'entry_planes.json';plane_path.write_text(json.dumps([row]))
    pixel_path=tmp_path/'pixels.json'
    r=dict(id=sample['id'],sample=sample,saved_gravity_prediction=saved,target_v0=[1.1,.3,.2],
           plane_registration=dict(path=str(plane_path),sha256=hashlib.sha256(plane_path.read_bytes()).hexdigest()),
           pixel_registration=dict(path=str(pixel_path),sha256=hashlib.sha256(pixel_path.read_bytes()).hexdigest()))
    first=evaluate_kinematic_velocity([r],book_pixels=True)
    assert first['records'][0]['status']=='ok'
    r['target_v0']=[9000,9000,9000]
    second=evaluate_kinematic_velocity([r],book_pixels=True)
    assert first['records'][0]['prediction']==second['records'][0]['prediction']
    with open(pixel['cache_path'],'ab') as f:f.write(b'drift')
    failed=evaluate_kinematic_velocity([r],book_pixels=True)
    assert len(failed['records'])==1 and failed['records'][0]['status']=='input_failure'
    assert not failed['original_predictions_replaced']
