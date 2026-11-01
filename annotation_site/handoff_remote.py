"""Finalize a first deployment: preserve seven invitations, revoke QA, re-invite admin."""
import json
import sqlite3
import sys
from pathlib import Path

from store import Store


def main():
    root=Path('/srv/phylabel');source=Path(sys.argv[1]);output=root/'private/delivery-invitations.json'
    if output.exists():raise RuntimeError('Delivery already finalized; do not rotate again blindly')
    store=Store(root/'data/annotations.sqlite3')
    original=json.loads(source.read_text())
    people=[i for i in original if i['user_id'].startswith('r0')]
    assert len(people)==7
    with store.connect() as db:
        real=db.execute("SELECT COUNT(*) FROM annotations a JOIN tasks t ON a.task_id=t.id WHERE t.batch_id='pilot6'").fetchone()[0]
        assert real==0,'Never erase real annotations'
        assert db.execute("SELECT COUNT(*) FROM users WHERE id LIKE 'r0%' AND password IS NULL AND invite_hash IS NOT NULL").fetchone()[0]==7
        backup=sqlite3.connect(root/'private/before-handoff.sqlite3');db.backup(backup);backup.close()
        (root/'private/before-handoff.sqlite3').chmod(0o600)
        db.execute("UPDATE users SET enabled=0,invite_hash=NULL WHERE role='qa'")
        db.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE role='qa')")
        store.log(db,'system','QA_access_revoked',detail={'real_pilot_annotations':real})
    people.append({'user_id':'admin','name':'项目管理员','role':'admin','token':store.rotate_invite('admin')})
    for i in people:i['url']='https://label.yeegoods.cn/physics/?invite='+i['token']
    output.write_text(json.dumps(people,ensure_ascii=False,indent=2));output.chmod(0o600)
    print(json.dumps({'delivery_file':str(output),'real_pilot_annotations':real,'QA_disabled':True,'accounts':len(people)}))


if __name__=='__main__':main()
