import os
from scripts.state_integrity_cache import state_identity


def test_verification_cache_invalidates_on_changed_file_or_expected_digest(tmp_path):
    p=tmp_path/'state.gz';p.write_bytes(b'original')
    receipt=dict(stored_state_sha256='stored',state_sha256='plain',source_config_sha256='config')
    initial=state_identity(p,receipt)
    assert state_identity(p,receipt)==initial
    assert state_identity(p,dict(receipt,state_sha256='different'))!=initial
    assert state_identity(p,dict(receipt,source_config_sha256='other-config'))!=initial
    p.write_bytes(b'changed!');stat=p.stat();os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns+10000000))
    assert state_identity(p,receipt)!=initial
