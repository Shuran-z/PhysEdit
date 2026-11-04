"""Read-only consistent task snapshot and exact current deployment bytes."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT=Path('/srv/phylabel/current').resolve()
DEST=Path('/home/ubuntu/core100-remaining74-20261101');DEST.mkdir(exist_ok=True)
names=['formal_critical_cohorts.py','formal_boundary_evaluation.py','server.py','static/app.js',
       'resources/core100_formal_cohorts.json','resources/core100_additional_media_verification.json',
       'resources/core100_reference_observability_progress.json','resources/core100_active_distance_bindings.json',
       'resources/active_distance_join_manifest.json']
with zipfile.ZipFile(DEST/'BEFORE.zip','w',zipfile.ZIP_DEFLATED)as z:
    for n in names:z.write(ROOT/n,n)
c=sqlite3.connect('file:/srv/phylabel/data/annotations.sqlite3?mode=ro',uri=True)
c.row_factory=sqlite3.Row;c.execute('BEGIN');tasks=[]
for r in c.execute("SELECT * FROM tasks WHERE batch_id='formal3600_v1' ORDER BY id"):
    t=dict(r);t['payload']=json.loads(t['payload']);t['annotations']={}
    for a in c.execute('SELECT * FROM annotations WHERE task_id=?',(t['id'],)):
        v=dict(a);v['payload']=json.loads(v['payload']);t['annotations'][v['stage']]=v
    tasks.append(t)
c.close()
raw=json.dumps(tasks).encode();(DEST/'TASKS.json.gz').write_bytes(gzip.compress(raw))
print(json.dumps(dict(tasks=len(tasks),task_snapshot_sha256=hashlib.sha256(raw).hexdigest())))
