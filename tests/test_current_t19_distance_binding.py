from scripts.bind_current_t19_distances import bind

def fixtures():
    old={'engine':'isaac','sample_id':'sample','scene_id':'T19','theta':.1,
         'parameter_name':'impact_eccentricity','videos':{'cam01':{'sha256':'old'}},
         'original_boundary_interval':[.09,.11],'publication_status':'retired_T19_render'}
    video={'engine':'isaac','native_sample_id':'sample','camera':'cam01','sha256':'old',
           'video_id':'video','download':{'revision':'pinned'},'parameter_facts':[['impact_eccentricity_m',.1,'m']]}
    return old,video

def test_exact_media_restores_distance_without_inventing_normalization():
    old,video=fixtures();rows,missing=bind([old],[video],'current')
    assert not missing and rows[0]['original_boundary_interval']==[.09,.11]
    assert rows[0]['normalization_status']=='original_domain_pending'
    assert rows[0]['current_release_binding_verified']
    assert old['publication_status']=='retired_T19_render'

def test_same_name_with_changed_bytes_does_not_inherit_boundary():
    old,video=fixtures();video['sha256']='new'
    rows,missing=bind([old],[video],'current');assert not rows and len(missing)==1

def test_reviewed_replacement_requires_exact_inputs_and_old_hash():
    old,video=fixtures();video['sha256']='new'
    video['media_version_update']={'previous_sha256':'old','current_sha256':'new','input_config_bytes_identical':True,'new_media_hf_sha_verified':True}
    assert len(bind([old],[video],'current')[0])==1
    video['media_version_update']['input_config_bytes_identical']=False
    assert not bind([old],[video],'current')[0]

def test_t14_state_digest_survives_lossless_storage(tmp_path):
    import gzip,hashlib
    from scripts.t14_formal_boundary_worker import sha
    path=tmp_path/'physics.json';raw=b'{"frames":[{"objects":[]}]}'
    path.write_bytes(raw);expected=hashlib.sha256(raw).hexdigest()
    assert sha(path)==expected
    path.with_suffix('.json.gz').write_bytes(gzip.compress(raw));path.unlink()
    assert sha(path)==expected
