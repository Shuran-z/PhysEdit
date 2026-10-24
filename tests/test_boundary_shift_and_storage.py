import gzip
import hashlib
import pytest
from scripts.audit_t13_conditional_boundary_shift import compare_intervals


def test_interval_overlap_is_not_evidence_of_an_identical_critical_root():
    assert compare_intervals([.016,.018],[[.013,.013375],[.02175,.022]])['nearest_interval_gap']==pytest.approx(.002625)
    assert compare_intervals([.016,.018],[[.016,.01625]])['status']=='overlap_or_touch'
    assert compare_intervals([.016,.018],[])['status']=='no_observed_control_boundary'


def test_relocation_keeps_receipt_paths_and_both_payload_digests(tmp_path):
    pytest.importorskip('fcntl')
    from scripts.relocate_completed_t18_states import relocate
    source=tmp_path/'run'/'physics.json.gz';source.parent.mkdir();plain=b'{"frames":[1,2]}'
    source.write_bytes(gzip.compress(plain,mtime=0));stored=source.read_bytes();target=tmp_path/'storage'/'physics.json.gz'
    receipt=dict(state_sha256=hashlib.sha256(plain).hexdigest(),stored_state_sha256=hashlib.sha256(stored).hexdigest())
    assert relocate(source,target,receipt)
    assert source.is_symlink() and source.read_bytes()==stored and gzip.decompress(target.read_bytes())==plain
