import pytest

from scripts import egl_uuid_identity


DEVICES = [
    dict(egl_index=0, uuid='GPU-c851cf7f-27a8-2ca7-0aeb-15164aaa44df'),
    dict(egl_index=1, uuid='GPU-56f7a2ac-646d-5b8f-09d5-2782e1690f2e'),
    dict(egl_index=2, uuid='GPU-929415f3-ec39-3689-db83-8ee6d9b696fb'),
    dict(egl_index=3, uuid=None),
]


@pytest.mark.parametrize('identity,expected', [
    ('GPU-56f7a2ac-646d-5b8f-09d5-2782e1690f2e', 1),
    ('GPU-929415f3-ec39-3689-db83-8ee6d9b696fb', 2),
])
def test_uuid_mapping_does_not_use_physical_index(monkeypatch, identity, expected):
    monkeypatch.setattr(egl_uuid_identity, 'egl_uuid_devices', lambda: DEVICES)
    assert egl_uuid_identity.matching_egl_index(identity) == expected


def test_missing_uuid_never_falls_back_to_device_zero(monkeypatch):
    monkeypatch.setattr(egl_uuid_identity, 'egl_uuid_devices', lambda: DEVICES)
    with pytest.raises(RuntimeError, match='exactly one'):
        egl_uuid_identity.matching_egl_index('GPU-a1763893-4894-cb56-2d97-06d695d6f419')


def test_duplicate_uuid_is_rejected(monkeypatch):
    monkeypatch.setattr(egl_uuid_identity, 'egl_uuid_devices', lambda: DEVICES + [DEVICES[1]])
    with pytest.raises(RuntimeError, match='exactly one'):
        egl_uuid_identity.matching_egl_index(DEVICES[1]['uuid'])
