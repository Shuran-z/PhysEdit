from scripts.export_original_boundary_distances import publication_status, attach_publication_verification
from scripts.verify_original_reference_publication import media_matches


def test_server_reference_keeps_distance_without_claiming_hf_publication():
    assert publication_status('T16', {'release': '/remote/dataset'}) == 'server_only_publication_binding_pending'
    assert publication_status('T19', {'repo_id': 'r', 'revision': 'v'}) == 'retired_T19_render'
    assert publication_status('T14', {'repo_id': 'r', 'revision': 'v'}) == 'published_reference'


def test_media_identity_requires_content_identity_and_size():
    expected = {'bytes': 12, 'sha256': 's', 'git_oid': 'g'}
    assert media_matches(expected, {'size': 12, 'sha256': 's'})
    assert media_matches(expected, {'size': 12, 'blob_id': 'g'})
    assert not media_matches(expected, {'size': 12, 'sha256': 'other', 'blob_id': 'other'})
    assert not media_matches(expected, {'size': 13, 'sha256': 's'})
    assert not media_matches(expected, None)


def test_current_media_proof_does_not_cross_revision_or_changed_media():
    row=dict(repo_id='r',revision='old',engine='genesis',sample_id='s',videos={'cam01':dict(path='v',sha256='hash')})
    proof=dict(repo_id='r',original_revision='old',engine='genesis',sample_id='s',
        status='same_media_at_current_revision',checked_revision='new',camera_checks={'cam01':True},
        media_identity=[dict(camera='cam01',path='v',sha256='hash')])
    result=attach_publication_verification([dict(row)],dict(records=[proof]))[0]
    assert result['publication_verification']['checked_revision']=='new'
    assert result['revision']=='old'
    assert not result['publication_verification']['formal_admission']
    assert 'publication_verification' not in attach_publication_verification(
        [{**row,'revision':'another'}],dict(records=[proof]))[0]
    assert 'publication_verification' not in attach_publication_verification(
        [{**row,'videos':{'cam01':dict(path='v',sha256='changed')}}],dict(records=[proof]))[0]
