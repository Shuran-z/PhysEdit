"""Deploy only the reviewed all100 overlay, with CAS, backup and score checks."""
import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

STAGE = Path(os.environ.get('CORE100_CONNECT_STAGE', '/home/ubuntu/core100-all-connect-20261101'))
ROOT = Path('/srv/phylabel/current').resolve()
DB = Path('/srv/phylabel/data/annotations.sqlite3')
with zipfile.ZipFile(STAGE / 'overlay.zip') as archive:
    for name in archive.namelist():
        target = (STAGE / name).resolve()
        assert target.is_relative_to(STAGE.resolve())
    archive.extractall(STAGE)
spec = json.loads((STAGE / 'DEPLOY_INPUT.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for row in spec['files']:
    assert sha(STAGE / row['target']) == row['after_sha256']
    p = ROOT / row['target']
    assert (sha(p) if p.exists() else None) == row['before_sha256'], 'Concurrent site change: ' + str(p)
    if p.suffix == '.py': compile((STAGE / row['target']).read_text(), str(p), 'exec')

c = sqlite3.connect('file:' + str(DB) + '?mode=ro', uri=True)
c.row_factory = sqlite3.Row; c.execute('BEGIN'); tasks = []
for row in c.execute("SELECT * FROM tasks WHERE batch_id='formal3600_v1' ORDER BY id"):
    task = dict(row); task['payload'] = json.loads(task['payload']); task['annotations'] = {}
    for annotation in c.execute('SELECT * FROM annotations WHERE task_id=?', (task['id'],)):
        value = dict(annotation); value['payload'] = json.loads(value['payload'])
        task['annotations'][value['stage']] = value
    tasks.append(task)
c.close()
task_hash = hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from critical_results import calculate, csv_bytes
before = calculate(tasks)
score_keys = ['per_model', 'admitted_cohort', 'contact_amendment', 'vlm_human_agreement']
old_scores = {key: before[key] for key in score_keys}
backup = Path('/srv/phylabel/private') / ('core100-all-connect-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
backup.mkdir(mode=0o700)
src = sqlite3.connect('file:' + str(DB) + '?mode=ro', uri=True)
dst = sqlite3.connect(backup / 'annotations.sqlite3'); src.backup(dst); dst.close(); src.close()
os.chmod(backup / 'annotations.sqlite3', 0o600)
for row in spec['files']:
    p = ROOT / row['target']
    if p.exists():
        target = backup / row['target']; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)

def request(path, token=None):
    headers = {'Cookie': 'phylabel_session=' + token} if token else {}
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:13081' + path, headers=headers), timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error: return error.code, error.read()

installed = []; token = None
try:
    for row in spec['files']:
        p = ROOT / row['target']; oldstat = p.stat() if p.exists() else (ROOT / 'server.py').stat()
        temporary = p.with_name(p.name + '.all100.tmp')
        temporary.write_bytes((STAGE / row['target']).read_bytes())
        os.chmod(temporary, oldstat.st_mode & 0o777); os.chown(temporary, oldstat.st_uid, oldstat.st_gid)
        temporary.replace(p); installed.append(row)
    importlib.invalidate_caches(); sys.modules.pop('active_distance_results', None)
    sys.modules.pop('core100_connection', None)
    sys.modules.pop('formal_critical_cohorts', None)
    sys.modules.pop('formal_boundary_evaluation', None)
    after = calculate(tasks)
    assert all(after[key] == old_scores[key] for key in score_keys), 'Old score regression'
    old_cohorts=before.get('formal_critical_cohorts',{}).get('cohorts',[])
    new_cohorts={c['cohort_id']:c for c in after.get('formal_critical_cohorts',{}).get('cohorts',[])}
    for cohort in old_cohorts:
        assert new_cohorts.get(cohort['cohort_id'])==cohort, 'Old formal cohort regression: '+cohort['cohort_id']
    connected = after['core100_connection']
    assert connected['summary']['cases'] == 100 and len(connected['scenes']) == 20
    assert connected['summary']['registered_outputs'] == len(tasks) == 3600
    assert after['active_distance_registry']['summary'] == spec['registry_summary']
    assert task_hash == hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
    subprocess.run(['systemctl', 'restart', 'phylabel.service'], check=True)
    for _ in range(30):
        try:
            if request('/health')[0] == 200: break
        except OSError: pass
        time.sleep(.3)
    else: raise RuntimeError('Service did not recover')
    c = sqlite3.connect(DB)
    uid = c.execute("SELECT id FROM users WHERE role='admin' AND enabled=1 LIMIT 1").fetchone()[0]
    token = secrets.token_urlsafe(32)
    c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), uid, secrets.token_hex(16), time.time()+300))
    c.commit(); c.close()
    assert request('/api/core100-connections.csv')[0] == 401
    exports = {}
    export_paths = ['/api/core100-connections.csv','/api/core100-connected-boundaries.csv','/api/core100-connected-outputs.csv']
    if 'formal_critical_cohorts' in after:
        export_paths += ['/api/formal-critical-references.csv','/api/formal-critical-outputs.csv']
    if spec.get('formal_summary',{}).get('newly_admitted_reference_cases'):
        export_paths += ['/api/formal-critical-scene-models.csv']
    for path in export_paths:
        status, body = request(path, token); assert status == 200, (path, status, body[:200])
        name = path.rsplit('/', 1)[1]; (STAGE / name).write_bytes(body)
        exports[name] = dict(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
    status, body = request('/api/critical-results', token); assert status == 200
    live = json.loads(body); assert live['core100_connection']['summary'] == connected['summary']
    assert all(live[key] == old_scores[key] for key in ['per_model', 'admitted_cohort']), 'Live score regression'
    (STAGE / 'LIVE_CONNECTION.json').write_text(json.dumps(live['core100_connection'], indent=2))
    if 'formal_critical_cohorts' in live:
        expected_formal=spec.get('formal_summary',dict(formally_registered_near_points=6,formally_registered_pairs=3))
        assert all(live['formal_critical_cohorts']['summary'][k]==v for k,v in expected_formal.items())
        (STAGE / 'LIVE_FORMAL.json').write_text(json.dumps(live['formal_critical_cohorts'], indent=2))
    receipt = dict(deployed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), backup=str(backup),
        files=spec['files'], old_registry_summary=before['active_distance_registry']['summary'],
        current_registry_summary=spec['registry_summary'], connection_summary=connected['summary'],
        old_scores_preserved=True, no_task_or_annotation_updates=True, immutable_task_snapshot_sha256=task_hash,
        preserved_formal_cohorts=len(old_cohorts),
        live_api_verified=True, anonymous_denied=True, exports=exports,
        service_active=subprocess.check_output(['systemctl','is-active','phylabel.service'],text=True).strip())
    if 'formal_critical_cohorts' in live:
        receipt['formal_summary'] = live['formal_critical_cohorts']['summary']
    (STAGE / 'DEPLOYMENT.json').write_text(json.dumps(receipt, indent=2))
    (backup / 'DEPLOYMENT.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))
except Exception:
    for row in installed:
        p = ROOT / row['target']; old = backup / row['target']
        if sha(p) != row['after_sha256']: continue
        if old.exists(): shutil.copy2(old, p)
        else: p.unlink()
    subprocess.run(['systemctl','restart','phylabel.service'], check=False)
    raise
finally:
    if token:
        c = sqlite3.connect(DB); c.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)); c.commit(); c.close()
