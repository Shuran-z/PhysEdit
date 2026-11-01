"""One transaction: preserve choices/owners/history and upgrade observation-only contracts."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time


def main():
    root=Path('/srv/phylabel');data=root/'data';stamp=str(int(time.time()))
    catalog=json.loads((Path(__file__).parent/'resources/event_contracts.json').read_text())
    readiness=json.loads((Path(__file__).parent/'resources/core100_readiness.json').read_text())
    gaps={r['clip_id']:r for r in readiness['rows']}
    db=sqlite3.connect(data/'annotations.sqlite3');db.row_factory=sqlite3.Row
    backup=root/'private'/('before-event-upgrade-'+stamp+'.sqlite3')
    dest=sqlite3.connect(backup);db.backup(dest);dest.close();backup.chmod(0o600)
    db.execute('BEGIN IMMEDIATE')
    # No existing human labels are discarded. Stop and plan migration if humans have started.
    if db.execute('SELECT count(*) FROM annotations a JOIN tasks t ON a.task_id=t.id WHERE t.batch_id=?',('formal3600_v1',)).fetchone()[0]:
        raise RuntimeError('Human records exist; preserve and explicitly migrate them before retrying')
    rows=db.execute('SELECT * FROM tasks WHERE batch_id=? ORDER BY id',('formal3600_v1',)).fetchall()
    assert len(rows)==3600
    assert collections.Counter(r['primary_id'] for r in rows)==dict(r01=520,r02=520,r03=520,r04=520,r05=520,r06=500,r07=500)
    upgraded=0;quality_reusable=0;worker=[]
    for row in rows:
        p=json.loads(row['payload']);proto=catalog['clips'][p['clip_id']]
        digest=hashlib.sha256(json.dumps(proto,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if p['clip_id'][:3]!='T15' and p['protocol_sha256']!=digest:
            old=p.get('machine',{})
            p.setdefault('protocol_history',[]).append({'at':time.time(),'protocol':p['protocol'],'protocol_sha256':p['protocol_sha256'],'machine':old})
            cache=old.get('quality_prediction')
            if (cache and cache.get('status')=='ok' and old.get('media_verified',{}).get('sha256')==p['video_sha256']
                and p['protocol'].get('target_en')==proto.get('target_en')):
                p['prior_quality_prediction']=cache;quality_reusable+=1
            p['protocol']=proto;p['protocol_sha256']=digest
            p['machine']={'pipeline_status':'pending','event_prediction':{'status':'pending','video_sha256':p['video_sha256']},'reason':'new scene-specific event observation contract; prior machine history preserved'}
            upgraded+=1
        g=gaps[p['clip_id']]
        p['evaluation_registration']={k:g[k] for k in ['reference_blockers','boundary_blockers','pair_registration_blockers','window_alignment','measurement_calibration','nearacc_eligible','pairacc_eligible']}
        db.execute('UPDATE tasks SET payload=?,version=version+1 WHERE id=?',(json.dumps(p,ensure_ascii=False),row['id']))
        # Worker sees observation definitions and immutable media identity only, never reference answers.
        keep=['id','clip_id','primary_id','video_sha256','protocol','protocol_sha256','fps','frames','duration_s','window_s','remote_media','prior_quality_prediction']
        if p.get('machine',{}).get('pipeline_status') not in ('complete','blocked_quality','evaluator_failure'):
            worker.append({k:p[k] for k in keep if k in p})
    from store import Store
    report={'upgraded_tasks':upgraded,'preserved_T15_tasks':180,'quality_reusable':quality_reusable,'worker_pending':len(worker),'total':3600,'reference_admission_granted':False,'backup':str(backup)}
    Store.log(db,'system','observation_contracts_v2_installed',detail=report)
    db.commit()
    import gzip
    sys.stdout.buffer.write(gzip.compress(json.dumps({'schema':'formal-event-worker-v2','report':report,'tasks':worker},ensure_ascii=False).encode()))


if __name__=='__main__':main()
