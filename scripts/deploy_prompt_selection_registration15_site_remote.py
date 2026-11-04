"""Deploy a read-only admin metadata endpoint; preserve all annotation and scoring data."""
import datetime,hashlib,json,os,secrets,shutil,sqlite3,subprocess,time,urllib.request,urllib.error
from pathlib import Path
STAGE=Path('/home/ubuntu/prompt-selection15-stage');spec=json.loads((STAGE/'DEPLOY_INPUT.json').read_text());ROOT=Path('/srv/phylabel/current').resolve();DB=Path('/srv/phylabel/data/annotations.sqlite3');stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');BACK=Path('/srv/phylabel/private')/('prompt-selection15-'+stamp);BACK.mkdir(mode=0o700)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tables():
 c=sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True);c.execute('BEGIN');r={}
 for name in ['tasks','annotations','independent_observations','dispute_samples','batches','users','audit']:
  h=hashlib.sha256();n=0
  for row in c.execute('SELECT * FROM '+name+' ORDER BY 1,2'):
   h.update(json.dumps(row,ensure_ascii=True,separators=(',',':')).encode());h.update(b'\n');n+=1
  r[name]={'rows':n,'sha256':h.hexdigest()}
 c.close();return r
def existing_results():
 return {str(p):sha(p) for root in [ROOT/'resources',Path('/srv/phylabel/data/scoring')] for p in root.rglob('*') if p.is_file()}
def request(url,token=None):
 headers={'Cookie':'phylabel_session='+token} if token else {}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=15) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
for f in spec['files']:
 p=ROOT/f['target'];assert sha(STAGE/f['stage'])==f['after_sha256']
 if f['before_sha256'] is None:assert not p.exists()
 else:assert sha(p)==f['before_sha256'],'Site changed concurrently; reconcile instead of overwriting'
registration=json.loads((STAGE/'registration.json').read_text());assert registration['affected_videos']==15;assert all('t04v3_stack_book_bottom.mass' not in x['selected_parameter_keys'] and 't04v3_removable_support_bar.friction' in x['selected_parameter_keys'] for x in registration['records'])
# SQLite online backup is consistent even if annotators have the site open.
src=sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True);dst=sqlite3.connect(BACK/'annotations.sqlite3');src.backup(dst);dst.close();src.close();os.chmod(BACK/'annotations.sqlite3',0o600);before=tables();results=existing_results()
for f in spec['files']:
 p=ROOT/f['target']
 if p.exists():dest=BACK/f['target'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for f in spec['files']:
 p=ROOT/f['target'];oldstat=p.stat() if p.exists() else None;temp=p.with_name(p.name+'.selection15.tmp');temp.write_bytes((STAGE/f['stage']).read_bytes());os.chmod(temp,oldstat.st_mode&0o777 if oldstat else 0o644)
 if oldstat:os.chown(temp,oldstat.st_uid,oldstat.st_gid)
 os.replace(temp,p)
subprocess.run(['systemctl','restart','phylabel.service'],check=True)
for i in range(20):
 try:
  if request('http://127.0.0.1:13081/health')[0]==200:break
 except OSError:time.sleep(.25)
else:raise AssertionError('Health did not recover')
tokens=[];checks={}
try:
 c=sqlite3.connect(DB);admin=c.execute("SELECT id FROM users WHERE role='admin' AND enabled=1 LIMIT 1").fetchone()[0];staff=c.execute("SELECT id FROM users WHERE role!='admin' AND enabled=1 LIMIT 1").fetchone()[0]
 for uid in [admin,staff]:
  token=secrets.token_urlsafe(32);tokens.append(token);c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,secrets.token_hex(16),time.time()+120))
 c.commit();c.close()
 status,body=request('http://127.0.0.1:13081/api/prompt-parameter-registration',tokens[0]);assert status==200 and hashlib.sha256(body).hexdigest()==spec['registry_sha256'];checks['admin_local_exact_registry']=True
 status,body=request('https://label.yeegoods.cn/physics/api/prompt-parameter-registration',tokens[0]);assert status==200 and hashlib.sha256(body).hexdigest()==spec['registry_sha256'];checks['admin_public_exact_registry']=True
 assert request('https://label.yeegoods.cn/physics/api/prompt-parameter-registration')[0]==401;checks['anonymous_denied']=True
 assert request('https://label.yeegoods.cn/physics/api/prompt-parameter-registration',tokens[1])[0]==403;checks['ordinary_annotator_denied']=True
 status,body=request('https://label.yeegoods.cn/physics/assets/app.js');assert status==200 and hashlib.sha256(body).hexdigest()==next(f['after_sha256'] for f in spec['files'] if f['target']=='static/app.js');checks['public_admin_link_asset_verified']=True
finally:
 c=sqlite3.connect(DB)
 for token in tokens:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
 c.commit();c.close()
after=tables();result_after=existing_results();old_results_unchanged=all(result_after.get(k)==v for k,v in results.items());assert old_results_unchanged;assert before==after,'Live annotation activity detected; do not restore or overwrite user work'
for f in spec['files']:assert sha(ROOT/f['target'])==f['after_sha256']
receipt=dict(hf_revision=spec['hf_revision'],registry_sha256=spec['registry_sha256'],affected_reference_videos=15,backup=str(BACK),checks=checks,database_tables_before=before,database_tables_after=after,all_annotation_task_and_result_tables_identical=True,existing_resource_and_score_files_unchanged=True,old_result_files_checked=len(results),temporary_test_sessions_removed=True,changed_files=[f['target'] for f in spec['files']],service_active=subprocess.check_output(['systemctl','is-active','phylabel.service'],text=True).strip())
(BACK/'DEPLOYMENT.json').write_text(json.dumps(receipt,indent=2));(STAGE/'DEPLOYMENT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
