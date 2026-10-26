"""Replay timed-out T12 jobs with a longer wall-time, unchanged physics."""
import base64
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    launches=json.loads((ROOT/'t12_remaining_grid_launch_20261022.json').read_text())
    failed={r['job_id'] for r in json.loads((ROOT/'t12_remaining_grid_evidence_20261022.json').read_text()) if r['status']=='failed'}
    payload=base64.b64encode(Path('scripts/t12_remaining_grid_worker.py').read_bytes()).decode()
    changes=[]
    for launch in launches:
        if launch['host']!='p26':continue
        code=r'''
import pathlib,json,subprocess,base64,hashlib,fcntl,os
l=LAUNCH;r=pathlib.Path(l['root']);b=r.parent;marker=r/'timeout_recovery_20261025.json'
if marker.exists():print(marker.read_text());raise SystemExit
jobs=json.loads(pathlib.Path(l['active_plan']).read_text());count=sum(j['job_id'] in FAILED for j in jobs)
if not count:print('null');raise SystemExit
lock=(r/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if hashlib.sha256(pathlib.Path(l['active_plan']).read_bytes()).hexdigest()!=l['active_plan_sha256']:raise ValueError('plan changed')
if hashlib.sha256((pathlib.Path(l['source'])/'12_render_motion_sequence.py').read_bytes()).hexdigest()!=l['backend_sha256']:raise ValueError('backend changed')
(r/'status_before_timeout_recovery_20261025.json').write_bytes((r/'status.json').read_bytes())
worker=b/'t12_timeout_recovery_20261025.py';worker.write_bytes(base64.b64decode(WORKER));python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',GENESIS_DISABLE_CV2='1',__EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json')
env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
lock.close()
with (r/'timeout_recovery_20261025.log').open('w') as log:
 p=subprocess.Popen([python,str(worker),'--plan',l['active_plan'],'--root',str(r),'--source',l['source'],'--gpu',str(l['gpu']),'--renderer-timeout-seconds','3600'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
out=dict(l,previous_pid=l['pid'],pid=p.pid,timeout_recovery_jobs=count,renderer_timeout_seconds=3600,recovery_worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest())
marker.write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''.replace('LAUNCH',repr(launch)).replace('FAILED',repr(failed)).replace('WORKER',repr(payload))
        result=json.loads(remote_text('p26',code,timeout=90))
        if result:launch.update(result);changes.append(result)
    (ROOT/'t12_remaining_grid_launch_20261022.json').write_text(json.dumps(launches,indent=2))
    (ROOT/'t12_timeout_recovery_20261025.json').write_text(json.dumps(changes,indent=2))
    for i,launch in enumerate(changes):(ROOT/f't12_timeout_recovery_{i}_launch_20261025.json').write_text(json.dumps(launch,indent=2))
    print(json.dumps([dict(root=l['root'],pid=l['pid'],timeout_jobs=l['timeout_recovery_jobs']) for l in changes]))


if __name__=='__main__':main()
