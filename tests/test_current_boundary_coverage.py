from scripts.audit_current_boundary_coverage import identity,classify

def video():
    return {'video_id':'v','sha256':'current','camera':'cam01'}

def test_same_name_or_path_is_not_media_proof():
    assert identity(video(),{'videos':['cam01.mp4']},[]) is None

def test_old_revision_cannot_bridge_an_unrelated_record():
    inv={'revision':'old','videos':{'cam01':{'sha256':'current'}}}
    assert identity(video(),{'revision':'new'},[inv]) is None
    assert identity(video(),{'revision':'old'},[inv])=='same_source_revision_and_inventory_video_sha256'

def test_explicit_config_hash_is_accepted_but_not_unverified_prompt_claim():
    digest='a'*64
    v=dict(video(),prompt_binding_evidence={'config_evidence':{'expected_sha256':digest,'verified':True}})
    assert identity(v,{'reference_config_sha256':digest},[])=='exact_source_config_sha256'
    v['prompt_binding_evidence']['config_evidence']['verified']=False
    assert identity(v,{'reference_config_sha256':digest},[]) is None

def test_changed_media_requires_exact_declared_input_replacement():
    v=video();old={'videos':{'cam01':{'sha256':'old'}}}
    assert identity(v,old,[]) is None
    v['media_version_update']={'previous_sha256':'old','current_sha256':'current','input_config_bytes_identical':True,'new_media_hf_sha_verified':True}
    assert identity(v,old,[])=='reviewed_input_identical_media_replacement'
    v['media_version_update']['previous_sha256']='different'
    assert identity(v,old,[]) is None

def test_no_flip_is_a_completed_search_not_a_missing_boundary():
    assert classify({'search_complete_no_flip':True,'necessary_search_pending':True})=='search_complete_no_flip'
    assert classify({})=='source_lookup_pending'
    assert classify({'numeric_identity_pending':True,'necessary_search_pending':True})=='numeric_identity_pending'
