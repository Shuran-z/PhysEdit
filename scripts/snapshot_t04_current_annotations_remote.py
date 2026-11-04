import sqlite3,json,datetime,hashlib
from pathlib import Path
O=Path('/home/ubuntu/t04-critical-followup');O.mkdir(exist_ok=True);c=sqlite3.connect('file:/srv/phylabel/data/annotations.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('BEGIN');tasks=[]
for r in c.execute("SELECT * FROM tasks WHERE batch_id='formal3600_v1' ORDER BY id"):
 p=json.loads(r['payload'])
 if not p.get('clip_id','').startswith('T04_C'):continue
 t=dict(r);t['payload']=p;t['annotations']={}
 for a in c.execute('SELECT * FROM annotations WHERE task_id=?',(r['id'],)):
  d=dict(a);d['payload']=json.loads(d['payload']);t['annotations'][d['stage']]=d
 tasks.append(t)
c.close();r=dict(snapshot_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),tasks=tasks,read_only=True);raw=json.dumps(r,ensure_ascii=False,indent=2).encode();(O/'TASKS.json').write_bytes(raw);print(json.dumps({'tasks':len(tasks),'sha256':hashlib.sha256(raw).hexdigest(),'path':str(O/'TASKS.json')}))
