import hashlib
import json

from scripts import build_core100_distance_bindings as builder


def test_continuation_index_updates_do_not_invalidate_pinned_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'ROOT',tmp_path)
    monkeypatch.setattr(builder,'EVIDENCE',{})
    index=tmp_path/'review'/'sealed_binding_updates.json';index.parent.mkdir()
    index.write_text(json.dumps({'updates':[1]}),encoding='utf-8')
    assert builder.read_pinned(index)=={'updates':[1]}
    first=dict(builder.EVIDENCE)
    index.write_text(json.dumps({'updates':[1,2]}),encoding='utf-8')
    assert builder.read_pinned(index)=={'updates':[1,2]}
    assert len(builder.EVIDENCE)==2
    assert all(builder.EVIDENCE[name]==digest for name,digest in first.items())
    assert all(hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()==digest
               for name,digest in builder.EVIDENCE.items())


def test_active_registry_never_pins_mutable_repeatability_or_readback_heads():
    from physedit.core100_bindings import load
    data=load(verify_evidence=True)
    assert all(not name.endswith('/endpoint_repeatability_latest.json')and
               not name.endswith('/pending_six_native_readback_latest.json')
               for name in data['evidence_sha256'])
