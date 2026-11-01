"""Isolated p26 deployment after an authenticated archive finishes transferring."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tarfile
import time

ROOT=Path('/21231_data1/liyuhan_t18_migration_20261027')
OLD='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'
NEW=str(ROOT/'importer')
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'


def remap(x):
    if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
    if isinstance(x,list):return [remap(v) for v in x]
    return NEW+x[len(OLD):] if isinstance(x,str) and (x==OLD or x.startswith(OLD+'/')) else x


def save(name,data):
    p=ROOT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(data,indent=2));t.replace(p)


def main():
    import fcntl
    lock=(ROOT/'bootstrap.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (ROOT/'launch.json').exists():return
    package=ROOT/'delta.tar.gz'
    while not package.exists() or package.stat().st_size!=17544706:
        save('deployment_status.json',dict(status='transferring_delta',bytes=package.stat().st_size if package.exists() else 0,total=17544706));time.sleep(20)
    if hashlib.sha256(package.read_bytes()).hexdigest()!='236993d96e230f5b6d06ba27159e46a2d9a9d3ddfa96e96dbdaa4aa918ef4d0b':
        raise ValueError('migration archive digest mismatch')
    importer=Path(NEW);importer.mkdir(exist_ok=True)
    for r in json.loads((ROOT/'reuse_manifest.json').read_text()):
        src=Path(r['path']);dest=Path(remap(r['path'])).resolve()
        if importer.resolve() not in dest.parents:raise ValueError('reuse path outside isolated root')
        if hashlib.sha256(src.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('existing dependency changed')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    with tarfile.open(package) as tar:
        for entry in tar:
            dest=(importer/entry.name).resolve()
            if importer.resolve() not in dest.parents or not entry.isfile():raise ValueError('unsafe archive member')
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(entry).read())
    # File relocation only; solver, seed, geometry and timing are unchanged.
    mappings=[]
    for p in importer.rglob('*.json'):
        raw=p.read_bytes();data=json.loads(raw);mapped=remap(data)
        if mapped!=data:
            p.write_text(json.dumps(mapped));mappings.append(dict(path=str(p),original_sha256=hashlib.sha256(raw).hexdigest(),relocated_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    save('path_relocation_receipt.json',dict(old=OLD,new=NEW,files=mappings))
    pending=json.loads((importer/'migration_jobs.json').read_text())
    retries=remap(json.loads((ROOT/'retry_jobs_original.json').read_text()))
    launches=[]
    for i,jobs in enumerate([pending[::2],pending[1::2],retries]):
        plan=ROOT/('plan_'+str(i)+'.json');plan.write_text(json.dumps(jobs));run=ROOT/('run_'+str(i));run.mkdir(exist_ok=True)
        command=[PYTHON,str(ROOT/'worker.py'),'--project',str(importer/'everyday_bifurcation_72k_T16_T20_v1'),
            '--plan',str(plan),'--root',str(run),'--gpu','auto','--minimum-free-memory-mib', '18432' if i==2 else '8192',
            '--renderer-timeout-seconds','3600']
        if i==2:command.append('--preserve-render-settings')
        with (run/'worker.log').open('w') as log:
            p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
        launches.append(dict(host='p26',root=str(run),pid=p.pid,active_plan=str(plan),planned=len(jobs),
            role='original_render_settings_retry' if i==2 else 'pending_context_migration',
            source_reproduction_required=True))
    save('launch.json',launches);save('deployment_status.json',dict(status='launched',queues=launches))


if __name__=='__main__':
    try:main()
    except Exception as e:
        save('deployment_status.json',dict(status='failed',error=type(e).__name__+': '+str(e)))
        raise
