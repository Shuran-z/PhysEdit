"""p25-only recovery of two verified empty-video render stalls; originals retained."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time

P=Path('/data_cached/wangzijun_p25/t18_t19_parallel_return_20261028')
O=Path('/data_cached/wangzijun_p25/t19_stall_recovery_20261029')
jobs=[('T19__bg01_home_ase__g04_high__mass_ratio__p020','cam03',410075),
      ('T19__bg01_home_ase__g04_high__impact_eccentricity__p002','cam02',4130653)]

def main():
    O.mkdir(exist_ok=False)
    evidence=[]
    for sid,cam,pid in jobs:
        cp=P/'configs'/sid/(cam+'.json')
        cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
        assert str(cp).encode() in cmd and any(a.endswith(b'/render_sample.py') for a in cmd)
        v=P/'outputs'/sid/'videos'/(sid+'__'+cam+'.mp4')
        log=P/'logs'/(sid+'__'+cam+'.log')
        assert v.stat().st_size==44 and time.time()-log.stat().st_mtime>3600
        evidence.append(dict(sample=sid,camera=cam,pid=pid,empty_mp4_bytes=44,
            idle_seconds=time.time()-log.stat().st_mtime,action='SIGTERM verified stalled renderer only'))
    (O/'stall_evidence.json').write_text(json.dumps(evidence,indent=2))
    for sid,cam,pid in jobs:os.kill(pid,signal.SIGTERM)
    # Parent workers write their failure receipt and release their sample lock.
    deadline=time.time()+120
    while any((P/'locks'/sid).exists() for sid,cam,pid in jobs):
        if time.time()>deadline:raise RuntimeError('Original worker did not relinquish ownership')
        time.sleep(2)
    s=(P/'batch_p25.py').read_text()
    s=s.replace("O=Path('/data_cached/wangzijun_p25/t18_t19_parallel_return_20261028')",'O=Path('+repr(str(O))+')')
    anchor="env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYTHONUNBUFFERED='1')"
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+"\n   runtime=O/'runtime'/sid/cam;runtime.mkdir(parents=True,exist_ok=True)\n   env.update(TMPDIR=str(runtime),XDG_CACHE_HOME=str(runtime),TI_OFFLINE_CACHE_FILE_PATH=str(runtime/'taichi'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')")
    s=s.replace('timeout=7200','timeout=1200')
    (O/'worker.py').write_text(s)
    spec=importlib.util.spec_from_file_location('worker',O/'worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
    def rewrite(x):
        if isinstance(x,dict):return {k:rewrite(v) for k,v in x.items()}
        if isinstance(x,list):return [rewrite(v) for v in x]
        if isinstance(x,str) and x.startswith(str(P)+'/outputs/'):return str(O)+x[len(str(P)):]
        return x
    ids={s for s,c,p in jobs};plan=[r for r in json.loads((P/'plan.json').read_text()) if r['sample'] in ids]
    for row in plan:
        for c in row['configs']:
            p=Path(c['path']);assert w.sha(p)==c['sha256']
            q=O/'configs'/row['sample']/(c['camera']+'.json');q.parent.mkdir(parents=True,exist_ok=True)
            q.write_text(json.dumps(rewrite(json.loads(p.read_text())),indent=2));c.update(path=str(q),sha256=w.sha(q))
        row['output']=str(O/'outputs'/row['sample'])
    w.save(O/'plan.json',plan)
    for row in plan:
        while True:
            snap=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],text=True)
            available=[tuple(map(int,l.split(','))) for l in snap.splitlines() if int(l.split(',')[0]) in [0,2,5] and int(l.split(',')[1])>=18000]
            if available:break
            w.save(O/'status.json',dict(phase='WAITING_MEMORY',sample=row['sample']));time.sleep(30)
        gpu=max(available,key=lambda x:x[1])[0]
        w.save(O/'status.json',dict(phase='RUNNING',sample=row['sample'],gpu=gpu))
        result=w.run(row,gpu)
        if result.get('error'):
            w.save(O/'status.json',dict(phase='FAILED',sample=row['sample'],error=result['error']));return
    w.save(O/'status.json',dict(phase='COMPLETE',recovered_videos=6))

if __name__=='__main__':main()
