"""Hash-check and package a frozen release plan without modifying source files."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time

root = Path(sys.argv[1])
rows = json.loads((root / 'plan.json').read_text())
receipts = []
for scene in sorted({r['scene'] for r in rows}):
    selected = [r for r in rows if r['scene'] == scene]
    target = root / (scene + '.tar.gz')
    if target.exists() and target.with_suffix('.receipt.json').exists():
        receipts.append(json.loads(target.with_suffix('.receipt.json').read_text()))
        continue
    members = {}
    for r in selected:
        p = Path(r['local_source'])
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r['sha256'], p
        sid = r['sample_id']
        members[f'{sid}/videos/{sid}__{r["camera"]}.mp4'] = p
        for cfg in r.get('source_render_configs', []):
            p = Path(cfg['path'])
            assert hashlib.sha256(p.read_bytes()).hexdigest() == cfg['sha256'], p
            members[f'{sid}/configs/{cfg["camera"]}.json'] = p
            p = Path(cfg['source'])
            assert hashlib.sha256(p.read_bytes()).hexdigest() == cfg['source_sha256'], p
            members[f'{sid}/source_configs/{cfg["camera"]}.json'] = p
        state = (r.get('trajectory') or {}).get('path') or (r.get('post_render_audit') or {}).get('state', {}).get('path')
        if state:
            p = Path(state)
            if not p.exists() and Path(state + '.gz').exists():
                p = Path(state + '.gz')
            assert p.is_file(), p
            members[f'{sid}/metadata/{p.name}'] = p
    temp = target.with_suffix('.partial')
    with tarfile.open(temp, 'w:gz', compresslevel=1, dereference=True) as archive:
        for name, p in sorted(members.items()):
            archive.add(p, arcname=name, recursive=False)
    with tarfile.open(temp) as archive:
        assert set(archive.getnames()) == set(members)
    temp.rename(target)
    h = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    receipt = dict(scene=scene, file=str(target), bytes=target.stat().st_size,
                   sha256=h.hexdigest(), videos=len(selected), members=len(members), finished=time.time())
    target.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2))
    receipts.append(receipt)
(root / 'complete.json').write_text(json.dumps(receipts, indent=2))
