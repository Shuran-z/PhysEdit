"""Run with sudo on the existing host; preserve the domain's original application."""
import datetime
import json
import os
import pwd
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout


def main():
    staging=Path(sys.argv[1]).resolve();stamp=sys.argv[2]
    root=Path('/srv/phylabel');release=root/'releases'/stamp
    if release.exists():raise RuntimeError('Release already exists')
    try:pwd.getpwnam('phylabel')
    except KeyError:run('useradd','--system','--home','/srv/phylabel','--shell','/usr/sbin/nologin','phylabel')
    release.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(staging/'annotation_site',release)
    data=root/'data';(data/'media').mkdir(parents=True,exist_ok=True)
    for f in (staging/'package'/'media').glob('*.mp4'):
        target=data/'media'/f.name
        if not target.exists():shutil.copyfile(f,target)
    sys.path.insert(0,str(release));from store import Store
    private=root/'private';private.mkdir(exist_ok=True);private.chmod(0o700)
    store=Store(data/'annotations.sqlite3')
    import sqlite3
    with store.connect() as source_db:
        backup_path=private/('before-release-'+stamp+'.sqlite3')
        backup_db=sqlite3.connect(backup_path);source_db.backup(backup_db);backup_db.close();backup_path.chmod(0o600)
    invites=store.provision(include_qa=True)
    private=root/'private';private.mkdir(exist_ok=True);private.chmod(0o700)
    invite_file=private/('invitations-'+stamp+'.json')
    invite_file.write_text(json.dumps(invites,ensure_ascii=False,indent=2));invite_file.chmod(0o600)
    for name in ['pilot_manifest.json','qa_manifest.json']:
        package=json.loads((staging/'package'/name).read_text())
        with store.connect() as db:exists=db.execute('SELECT 1 FROM batches WHERE id=?',(package['batch']['id'],)).fetchone()
        if not exists:store.import_batch(package,data/'media')
    # Migrate only untouched real tasks. Existing human records and historical QA are immutable.
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute("SELECT t.* FROM tasks t JOIN batches b ON t.batch_id=b.id WHERE b.mode!='qa' AND t.state='unstarted' AND NOT EXISTS (SELECT 1 FROM annotations a WHERE a.task_id=t.id)").fetchall()
        migrated=[]
        for r in rows:
            p=json.loads(r['payload'])
            if p.get('review_policy')=='vlm_human_dispute_only_v2':continue
            p.update(review_policy='vlm_human_dispute_only_v2',reviewer_id='')
            db.execute("UPDATE tasks SET reviewer_id='',payload=?,version=version+1 WHERE id=?",(json.dumps(p,ensure_ascii=False),r['id']))
            migrated.append(r['id'])
        if migrated:
            store.log(db,'system','review_policy_migrated',detail={'task_ids':migrated,'policy':'vlm_human_dispute_only_v2','old_records_preserved':True})
            b=db.execute("SELECT metadata FROM batches WHERE id='pilot6'").fetchone()
            if b:
                meta=json.loads(b['metadata']);meta.update(note='VLM先评、一次人工复核；仅争议随机抽样20%由管理员二审。未抽中的争议保留待定。')
                db.execute("UPDATE batches SET metadata=? WHERE id='pilot6'",(json.dumps(meta,ensure_ascii=False),))
    run('chown','-R','phylabel:phylabel',str(data))
    for base,dirs,files in os.walk(data):
        Path(base).chmod(0o750)
        for name in files:(Path(base)/name).chmod(0o640)
    current=root/'current'
    if current.exists() and not current.is_symlink():raise RuntimeError('Current is not a symlink')
    link=root/'current.next';link.symlink_to(release);link.replace(current)
    service='''[Unit]
Description=PHY2 private video annotation
After=network.target
[Service]
User=phylabel
Group=phylabel
WorkingDirectory=/srv/phylabel/current
ExecStart=/usr/bin/python3 /srv/phylabel/current/server.py --host 127.0.0.1 --port 13081 --data-dir /srv/phylabel/data --prefix /physics/
Restart=on-failure
RestartSec=3
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/phylabel/data
[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system/phylabel.service').write_text(service)
    run('systemctl','daemon-reload');run('systemctl','enable','--now','phylabel.service');run('systemctl','restart','phylabel.service')
    import time
    for i in range(20):
        try:
            response=json.load(urllib.request.urlopen('http://127.0.0.1:13081/health',timeout=3));assert response['ok'];break
        except Exception:
            if i==19:raise
            time.sleep(.25)
    config=Path('/etc/nginx/sites-enabled/label.yeegoods.cn.conf').resolve()
    original=config.read_text();marker='    location = /api/map-reference {'
    if '# PHY2 annotation prefix' not in original:
        if original.count(marker)!=1 or 'server_name label.yeegoods.cn;' not in original:raise RuntimeError('Unexpected nginx configuration')
        backup=private/('nginx-label-'+stamp+'.conf');backup.write_text(original)
        addition='''    # PHY2 annotation prefix: existing root application is preserved.
    location = /physics { return 301 /physics/; }
    location /physics/ {
        proxy_pass http://127.0.0.1:13081/;
        client_max_body_size 64m;
        proxy_read_timeout 60s;
        access_log off;
        add_header Referrer-Policy no-referrer always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;
    }

'''
        config.write_text(original.replace(marker,addition+marker))
        try:run('nginx','-t')
        except Exception:config.write_text(original);raise
        run('systemctl','reload','nginx')
    print(json.dumps({'release':str(release),'private_invitations':str(invite_file),'created_accounts':len(invites),'service':run('systemctl','is-active','phylabel.service').strip()}))


if __name__=='__main__':main()
