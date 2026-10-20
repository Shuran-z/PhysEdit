"""Recovery resumes across mixed JSON formats without duplicating batch members."""
import hashlib
import json
import sys

from scripts import collect_completion_states as collector


def test_cached_mixed_formats_are_rebatched_by_release_identity(tmp_path,monkeypatch):
    workspace=tmp_path/'work';workspace.mkdir()
    inventory=tmp_path/'dataset_splits_v2';inventory.mkdir()
    output=tmp_path/'receipts';output.mkdir()
    rows=[];cached=[]
    for i in range(9):
        sid=f'T05_sample_{i:02}'
        sidecar=f'metadata/{sid}__cam01.json'+('.gz' if i else '')
        rows.append(dict(event_id='T05',engine='genesis',sample_id=sid,repo_id='fixture/repo',revision='frozen',sidecar_paths=[sidecar]))
        path=tmp_path/(sid+'.json');path.write_bytes(b'{"frames":[{}]}')
        cached.append(dict(scene_id='T05',sample_id=sid,repo_id='fixture/repo',revision='frozen',sidecar=sidecar,local_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (inventory/'all_selected_trajectories.jsonl').write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    # Old batches omitted uncompressed sample00; a duplicate can remain from an
    # interrupted migration. Resuming must produce each of the nine exactly once.
    (output/'T05_000.json').write_text(json.dumps(cached[1:]+[cached[0]]))
    (output/'T05_001.json').write_text(json.dumps([cached[-1]]))
    monkeypatch.chdir(workspace);monkeypatch.setattr(collector,'OUT',output)
    monkeypatch.setattr(sys,'argv',['recover','--scenes','T05'])
    monkeypatch.setattr(collector.subprocess,'Popen',lambda *a,**k: (_ for _ in ()).throw(AssertionError('cached recovery must not contact server')))
    collector.main()
    batches=[json.loads(path.read_text()) for path in sorted(output.glob('T05_*.json'))]
    ids=[r['sample_id'] for batch in batches for r in batch]
    assert ids==[r['sample_id'] for r in rows]
    assert list(map(len,batches))==[8,1]
