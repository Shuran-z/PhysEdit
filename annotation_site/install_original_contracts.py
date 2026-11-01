"""Preserving migration to source-audited protocols; no media or ownership changes."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time


def main():
    root=Path('/srv/phylabel');stamp=str(int(time.time()))
    cat=json.loads((Path(__file__).parent/'resources/event_contracts.json').read_text())
    report=json.loads((Path(__file__).parent/'resources/original_contract_audit.json').read_text())
    by={r['clip_id']:r for r in report['rows']}
    db=sqlite3.connect(root/'data/annotations.sqlite3');db.row_factory=sqlite3.Row
    dest=sqlite3.connect(root/'private'/('before-original-contracts-'+stamp+'.sqlite3'));db.backup(dest);dest.close()
    db.execute('BEGIN IMMEDIATE');rows=db.execute("SELECT * FROM tasks WHERE batch_id='formal3600_v1' ORDER BY id").fetchall()
    assert len(rows)==3600
    assert collections.Counter(r['primary_id'] for r in rows)==dict(r01=520,r02=520,r03=520,r04=520,r05=520,r06=500,r07=500)
    jobs=[];changed=archived=cached=blocked=0
    for row in rows:
        p=json.loads(row['payload']);proto=cat['clips'][p['clip_id']]
        digest=hashlib.sha256(json.dumps(proto,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if digest==p['protocol_sha256']:continue
        old=p.get('machine',{});source=p['source']['generation_metadata']['source_video_id']
        assert source==proto['original_contract_audit']['source_video_id']
        p.setdefault('protocol_history',[]).append({'at':time.time(),'protocol':p['protocol'],'protocol_sha256':p['protocol_sha256'],'machine':old})
        # Preserve any intervening human work as historical protocol records, never relabel it.
        notes=db.execute('SELECT stage FROM annotations WHERE task_id=?',(row['id'],)).fetchall()
        for n in notes:
            if n['stage'] in ('primary','review','adjudication'):
                db.execute('UPDATE annotations SET stage=? WHERE task_id=? AND stage=?',(n['stage']+'_before_original_'+stamp,row['id'],n['stage']));archived+=1
        quality=old.get('quality_prediction') or p.get('prior_quality_prediction')
        if quality and quality.get('status')=='ok' and quality.get('video_sha256')==p['video_sha256']:
            p['prior_quality_prediction']=quality;cached+=1
        p['protocol']=proto;p['protocol_sha256']=digest
        if old.get('quality_route')=='auto_rejected' and old.get('media_verified',{}).get('sha256')==p['video_sha256']:
            p['machine']={**old,'pipeline_status':'blocked_quality','event_prediction':{'status':'not_scheduled','reason':'quality_blocked','video_sha256':p['video_sha256']},'protocol_rebound_from_history':True};blocked+=1
        else:p['machine']={'pipeline_status':'pending','reason':'source-audited event definitions; prior outputs archived'}
        r=by[p['clip_id']]
        p['evaluation_registration']={'original_protocol_gaps':r['protocol_gaps'],'reference_blockers':r['reference_gaps'],'boundary_blockers':r['boundary_gaps'],'pair_registration_blockers':r['pair_gaps'],'window_alignment':r['window_gap'],'nearacc_eligible':False,'pairacc_eligible':False}
        db.execute("UPDATE tasks SET payload=?,state='unstarted',version=version+1 WHERE id=?",(json.dumps(p,ensure_ascii=False),row['id']));changed+=1
        if p['machine']['pipeline_status']=='pending':
            keep=['id','clip_id','primary_id','video_sha256','protocol','protocol_sha256','fps','frames','duration_s','window_s','remote_media','prior_quality_prediction']
            jobs.append({k:p[k] for k in keep if k in p})
    from store import Store
    receipt={'changed':changed,'historical_human_records_preserved':archived,'quality_cache_available':cached,'quality_blocked_retained':blocked,'worker_jobs':len(jobs),'source_audit_summary':report['summary']}
    Store.log(db,'system','original_source_contracts_installed',detail=receipt);db.commit()
    # Interleave people and scene families for early access; the frozen sampling/owners do not change.
    groups=collections.defaultdict(list)
    for j in jobs:groups[j['primary_id']].append(j)
    for uid,items in groups.items():items.sort(key=lambda t:(int(t['clip_id'][-2:]),(int(t['clip_id'][1:3])-1-(int(uid[-2:])-1)*3)%20,t['id']))
    ordered=[]
    while any(groups.values()):
        for uid in sorted(groups):
            if groups[uid]:ordered.append(groups[uid].pop(0))
    sys.stdout.buffer.write(gzip.compress(json.dumps({'report':receipt,'preserve_processing_order':True,'tasks':ordered},ensure_ascii=False).encode()))


if __name__=='__main__':main()
