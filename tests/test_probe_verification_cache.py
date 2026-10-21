import gzip
import hashlib
from pathlib import Path
import pytest
from scripts.probe_verification_cache import verify_probe_files


def case(tmp_path,compressed=False):
    raw=b'{"frames":[1]}';config=tmp_path/'config.json';config.write_bytes(b'{}')
    p=tmp_path/('physics.json.gz' if compressed else 'physics.json');p.write_bytes(gzip.compress(raw) if compressed else raw)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    row=dict(state_path=str(p),state_sha256=sha(raw),config_sha256=sha(config.read_bytes()))
    if compressed:row['stored_state_sha256']=sha(p.read_bytes())
    return row,p


def test_verified_unchanged_files_reuse_cache_without_reading_payload(tmp_path,monkeypatch):
    row,p=case(tmp_path,True);cache={};verify_probe_files(row,tmp_path,cache)
    monkeypatch.setattr(Path,'read_bytes',lambda self:(_ for _ in ()).throw(AssertionError('unexpected reread')))
    assert verify_probe_files(row,tmp_path,cache)==str(p)


def test_changed_state_or_expected_digest_cannot_reuse_cache(tmp_path):
    row,p=case(tmp_path);cache={};verify_probe_files(row,tmp_path,cache)
    p.write_bytes(b'bad state')
    with pytest.raises(ValueError,match='numeric state'):verify_probe_files(row,tmp_path,cache)


def test_config_change_and_compressed_relocation_are_checked(tmp_path):
    row,p=case(tmp_path,True);cache={};row['state_path']=str(tmp_path/'physics.json')
    assert verify_probe_files(row,tmp_path,cache)==str(p)
    (tmp_path/'config.json').write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError,match='config'):verify_probe_files(row,tmp_path,cache)
