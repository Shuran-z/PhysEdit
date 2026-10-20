import gzip
import hashlib
import json
from scripts.compress_completed_t18_states import compress_job


def test_active_job_is_untouched_and_completed_state_is_lossless(tmp_path):
    folder=tmp_path/'job';probe=folder/'0.5';probe.mkdir(parents=True)
    raw=b'{"frames": [1, 2, 3]}'
    source=probe/'physics.json';source.write_bytes(raw)
    receipt={'theta':.5,'state_sha256':hashlib.sha256(raw).hexdigest(),'state_path':str(source)}
    (probe/'receipt.json').write_text(json.dumps(receipt))
    assert compress_job(folder,tmp_path)==(0,0,0)
    assert source.read_bytes()==raw
    (folder/'result.json').write_text(json.dumps({'probes':[receipt]}))
    assert compress_job(folder,tmp_path)[0]==1
    saved=json.loads((probe/'receipt.json').read_text())
    assert gzip.decompress((probe/'physics.json.gz').read_bytes())==raw
    assert saved['state_sha256']==receipt['state_sha256']
    assert not source.exists()
    assert compress_job(folder,tmp_path)==(0,0,0)
    # Recover a hypothetical interruption between probe and job receipt writes.
    (folder/'result.json').write_text(json.dumps({'probes':[receipt]}))
    compress_job(folder,tmp_path)
    assert json.loads((folder/'result.json').read_text())['probes'][0]['state_path']==saved['state_path']
