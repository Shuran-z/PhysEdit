import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('inventory',Path(__file__).parents[1]/'scripts/refresh_72000_inventory.py')
module=importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
spec.loader.exec_module(module)


def row(engine='genesis',decision='accept'):
    r={'scene':'T19','engine':engine,'sha256':'abc',
       'source_quality':'REVIEW_ONLY_RETIRED_REFERENCE_NOT_REACTIVATED'}
    proof={'video_sha256':'abc','reviewer':'reviewer','decision':decision,'evidence':['hash-bound-evidence'],
           'checks':dict.fromkeys(['identity_geometry','contact_physics','declared_controls','event_visibility','temporal_coverage'],True)}
    r['visual_physics_adjudication']=proof
    r['quality_reactivation']={**proof,'authorization':'author_20261029_review_genesis1830_keep_qualified'}
    if decision=='reject':proof['reason']='observed defect'
    return r


def test_no_batch_acceptance_without_review():
    r=row();del r['quality_reactivation']
    assert module.admission(r)=='UNUSABLE_RETIRED'


def test_unified_prompt_pointer_defers_to_current_catalog(tmp_path,monkeypatch):
    import json
    monkeypatch.setattr(module,'OUT',tmp_path)
    (tmp_path/'ACTIVE_PROMPTS.json').write_text(json.dumps({'policy':'core100-aligned-compact-three-prompts','manifest':'catalog.gz','manifest_sha256':'hash'}))
    (tmp_path/'ACTIVE_CATALOG.json').write_text('{}')
    module.apply_prompt_completions([])


def test_exact_genesis_acceptance_and_uncertainty():
    assert module.admission(row())=='USABLE_VERIFIED_VISUAL_PHYSICS'
    assert module.admission(row(decision='review'))=='PENDING_REVIEW'
    assert module.admission(row(decision='reject'))=='UNUSABLE_VISUAL_PHYSICS_FAILURE'


def test_isaac_cannot_use_genesis_permission():
    with pytest.raises(AssertionError):module.admission(row('isaac'))


def test_authorized_hash_bound_isaac_review_can_admit_only_reviewed_video():
    r=row('isaac');r['quality_reactivation']['authorization']='author_20261029_use_qualified_isaac_t19'
    assert module.admission(r)=='USABLE_VERIFIED_VISUAL_PHYSICS'
    r['visual_physics_adjudication']['checks']['identity_geometry']=None
    with pytest.raises(AssertionError):module.admission(r)


def test_wrong_hash_or_missing_contact_check_is_blocked():
    r=row();r['quality_reactivation']['video_sha256']='different'
    with pytest.raises(AssertionError):module.admission(r)


def test_review_does_not_hide_known_integrity_failure():
    r=row(decision='review');r['post_render_audit']={'media_and_state_integrity':'FAIL'}
    assert module.admission(r)=='UNUSABLE_INTEGRITY_FAILURE'
    r=row();r['visual_physics_adjudication']['checks']['contact_physics']=False
    with pytest.raises(AssertionError):module.admission(r)


def test_conflicting_retry_cannot_replace_frozen_published_bytes():
    a={'results':[{'camera':'cam01','sha256':'old'}]}
    b={'results':[{'camera':'cam01','sha256':'new'}]}
    assert module.choose_completed_receipt(a,b,{'cam01':'old'})==0
    assert module.choose_completed_receipt(a,b,{'cam01':'new'})==1
    with pytest.raises(ValueError):module.choose_completed_receipt(a,b,{'cam01':'unknown'})
    with pytest.raises(ValueError):module.choose_completed_receipt(a,b,None)


def test_reviewed_version_update_requires_exact_old_hash_and_declared_input_identity():
    frozen=row('isaac');frozen['video_id']='v';frozen['sha256']='new'
    frozen['visual_physics_adjudication']['video_sha256']='new'
    frozen['quality_reactivation'].update(video_sha256='new',authorization='author_20261029_use_qualified_isaac_t19')
    frozen['media_version_update']={'previous_sha256':'old','current_sha256':'new','input_config_bytes_identical':True,'new_media_hf_sha_verified':True}
    frozen['previous_video_versions']=[{'video_sha256':'old'}]
    original={'video_id':'v','engine':'isaac','scene':'T19','sha256':'old'}
    actual=dict(original);assert module.apply_reviewed_media_version(actual,frozen) and actual['sha256']=='new'
    bad=dict(original,sha256='unrelated')
    with pytest.raises(AssertionError):module.apply_reviewed_media_version(bad,frozen)
    frozen['media_version_update']['input_config_bytes_identical']=False
    with pytest.raises(AssertionError):module.apply_reviewed_media_version(dict(original),frozen)
