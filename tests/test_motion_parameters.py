import importlib.util
from pathlib import Path

import numpy as np
import pytest

from gravtrace.camera import Camera, lookat_camera
from physedit.motion_parameters import (fit_sliding_friction, scalar_error, sliding_displacement,
                                      summarize_errors, velocity_error, velocity_from_prediction,
                                      fit_velocity_with_frozen_gravity)


def prediction(speed=2., angle=0., azimuth=0.):
    return {'status':'ok','params':dict(speed=speed, angle=angle, azimuth=azimuth)}


def test_velocity_world_basis_and_zero_target():
    np.testing.assert_allclose(velocity_from_prediction(prediction()), [2,0,0])
    np.testing.assert_allclose(velocity_from_prediction(prediction(angle=np.pi/2)), [0,0,2], atol=1e-12)
    np.testing.assert_allclose(velocity_from_prediction(prediction(angle=np.pi/2), [1,0,0]), [-2,0,0], atol=1e-12)
    r=velocity_error(prediction(), [0,0,0])
    assert r['relative_error_pct'] is None and r['vector_relative_error_pct'] is None
    assert r['absolute_error']==2 and r['zero_target']


def test_failed_prediction_and_invalid_target_rejected():
    with pytest.raises(ValueError): velocity_from_prediction({'status':'at_bound'})
    with pytest.raises(ValueError): velocity_error(prediction(), [float('nan'),0,0])
    with pytest.raises(ValueError): velocity_from_prediction(prediction(), [0,0,0])
    with pytest.raises(ValueError): scalar_error(1, -1)


def test_full_denominator_and_zero_target_not_assigned_relative_zero():
    r=summarize_errors([{'status':'ok','relative_error_pct':4},
                        {'status':'ok','zero_target':True,'relative_error_pct':None},
                        {'status':'input_failure','reason':'missing_source'}])
    assert r['coverage_rate']==2/3 and r['relative_error_count']==1
    assert r['mean_pct']==4 and r['zero_target_count']==1
    assert r['reasons']=={'missing_source':1}


def sample(mu=.12, drag=0., gravity=3.71):
    theta=np.radians(14);d=np.array([-np.cos(theta),0,-np.sin(theta)])
    t=np.linspace(0,.6,25);initial=np.array([.1,0,.2]);corners=np.array([[x,y,z] for x in [-.07,.07] for y in [-.035,.035] for z in [-.005,.005]])
    cam=lookat_camera([1.1,-1.4,.8],[0,0,.1],43,[854,480]);a=gravity*(np.sin(theta)-mu*np.cos(theta))
    dist=sliding_displacement(t,.15,a,drag)
    boxes=Camera.from_dict(cam,[854,480]).project_box(initial+dist[:,None,None]*d+corners)
    return dict(times_s=t.tolist(), boxes_xyxy=boxes.tolist(), camera=cam,image_size=[854,480],
                gravity_mps2=gravity,slope_angle_deg=14,downhill_direction=d.tolist(),
                initial_position=initial.tolist(),world_corners=corners.tolist(),drag_per_second=drag,
                evidence=dict(clock_verified=True,camera_verified=True,initial_identity_verified=True,
                              single_plane_sliding=True,no_external_force=True,
                              rotation_stable=True,effective_friction_verified=True))


@pytest.mark.parametrize('mu,drag,g',[(.12,0,3.71),(.05,.08,9.81),(.21,.06,15)])
def test_exact_pixel_physical_recovery(mu,drag,g):
    r=fit_sliding_friction(sample(mu,drag,g))
    assert r['status']=='ok',r
    assert abs(r['friction']-mu)<1e-4
    assert abs(r['speed_at_window_start_mps']-.15)<1e-3
    assert r['gravity_optimized'] is False
    assert r['position_offset_m']==0 and r['initial_position_optimized'] is False


def test_material_declaration_does_not_certify_contact_friction():
    s=sample();s['evidence']['effective_friction_verified']=False
    r=fit_sliding_friction(s)
    assert r['status']=='review_required' and r['friction'] is not None


def test_static_rolling_and_missing_frames_keep_failure():
    s=sample();s['boxes_xyxy']=[s['boxes_xyxy'][0]]*len(s['times_s'])
    assert fit_sliding_friction(s)['status']=='unidentifiable'
    s=sample();s['evidence']['rotation_stable']=False
    assert fit_sliding_friction(s)['status']=='inapplicable'
    s=sample();s['boxes_xyxy'][5]=None
    assert fit_sliding_friction(s)['status']=='input_failure'


def test_stop_and_slope_mismatch_rejected():
    s=sample(.5); assert fit_sliding_friction(s)['status']=='inapplicable'
    s=sample();s['downhill_direction']=[1,0,0]
    assert fit_sliding_friction(s)['reason']=='slope_and_direction_mismatch'


def test_cli_missing_prediction_preserves_registered_item():
    p=Path(__file__).resolve().parents[1]/'scripts/phyediting_motion_parameters.py'
    spec=importlib.util.spec_from_file_location('motion_cli',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    r=m.evaluate_velocity([dict(id='a',motion={'v0':[1,0,0]})],[])
    assert len(r['records'])==1 and r['speed']['coverage_rate']==0
    assert r['records'][0]['reason']=='missing_prediction'


def test_velocity_fit_uses_saved_gravity_and_rejects_truth_input():
    from gravtrace.motion import ballistic
    s=sample();t=np.linspace(0,.35,15);v=[1.1,.2,.3];g=3.71
    corners=np.asarray(s['world_corners']);x0=s['initial_position']
    boxes=Camera.from_dict(s['camera'],s['image_size']).project_box(
        ballistic(t,x0,v,g,np.array([0,0,-1]))[:,None,:]+corners)
    inp=dict(id='calibrated',scenario='projectile',fps=30,image_size=s['image_size'],camera=s['camera'],
             object=dict(corners=corners.tolist(),position=x0),motion=dict(gravity_dir=[0,0,-1],t0=[0,0],
             speed=[0,8],angle_deg=[-89,89]),boxes=dict(frames=list(range(len(t))),times=t.tolist(),
             xyxy=boxes.tolist()),window=dict(contact_check=False))
    pred=dict(prediction(1),gravity=g,frames=len(t));pred['params']['t0']=0.
    r=fit_velocity_with_frozen_gravity(inp,pred)
    assert r['status']=='ok',r
    np.testing.assert_allclose(r['velocity_vector_mps'],v,atol=1e-5)
    assert r['gravity_mps2']==g and r['gravity_optimized'] is False
    inp['motion']['v0']=v
    assert fit_velocity_with_frozen_gravity(inp,pred)['reason']=='velocity_truth_in_estimator_input'


def test_long_window_camera_facing_downhill_initialization_is_finite():
    import json
    s=sample(.24,.012/.19,24.)
    theta=np.radians(14);t=np.linspace(0,2,61);d=np.asarray(s['downhill_direction'])
    cam=lookat_camera([-1.1,-.96,1.22],[0,0,.12],51,[854,480])
    x=np.asarray(s['initial_position'])+sliding_displacement(t,.1,24*(np.sin(theta)-.24*np.cos(theta)),s['drag_per_second'])[:,None]*d
    s.update(camera=cam,times_s=t.tolist(),boxes_xyxy=Camera.from_dict(cam,[854,480]).project_box(x[:,None,:]+np.asarray(s['world_corners'])).tolist())
    r=fit_sliding_friction(s)
    assert r['status']=='ok',r
    assert abs(r['friction']-.24)<1e-5
    json.dumps(r,allow_nan=False)


def test_static_bound_is_conditional_and_never_a_kinetic_point_estimate():
    s=sample();s['boxes_xyxy']=[s['boxes_xyxy'][0]]*len(s['times_s'])
    assert 'static_friction_bound' not in fit_sliding_friction(s)
    s['evidence']['static_equilibrium_verified']=True
    r=fit_sliding_friction(s)
    assert r['status']=='unidentifiable' and r['friction'] is None
    assert r['static_friction_bound']['lower']==pytest.approx(np.tan(np.radians(14)))
    assert not r['static_friction_bound']['point_estimate']


def test_friction_information_coverage_does_not_inflate_point_coverage():
    from scripts.phyediting_motion_parameters import evaluate_friction
    moving=sample()
    static=sample();static['boxes_xyxy']=[static['boxes_xyxy'][0]]*len(static['times_s'])
    static['evidence']['static_equilibrium_verified']=True
    unknown=sample();unknown['evidence']['clock_verified']=False
    out=evaluate_friction([{'id':'moving','measurement':moving,'target_effective_friction':.24},
        {'id':'static','measurement':static},{'id':'unknown','measurement':unknown}])
    assert out['summary']['coverage_rate']==pytest.approx(1/3)
    info=out['information_coverage']
    assert info['kinetic_point_estimates']==1 and info['static_bounds']==1 and info['unresolved']==1
    assert info['point_or_bound_rate']==pytest.approx(2/3)
