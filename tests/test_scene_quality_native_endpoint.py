from physedit.boundary_pipeline import quality_route
def record(last):
    return {'status':'ok','quality':{'policy_version':'scene-integrity-v2','contradictions':[],
        'checks':{k:{'label':'absent','evidence_indices':[0,12],'evidence_times_s':[0,last],'reason':'Original actors remain visible.'}
        for k in ['foreign_objects','scene_replacement','identity_loss','geometry_corruption']}}}
def test_fractional_registered_horizon_uses_native_frame_endpoint():
    job={'window_s':209/30,'generated_fps':24,'last_observed_time_s':167/24}
    assert quality_route(record(167/24),job,.9)=='pass'
def test_missing_more_than_one_native_frame_stays_pending():
    job={'window_s':7.,'generated_fps':24,'last_observed_time_s':6.5}
    assert quality_route(record(6.5),job,.9)=='review'
