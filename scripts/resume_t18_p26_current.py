"""Resume the two repaired, owned T18 queues without duplicating live workers."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT

CODE=r'''
import json,os,subprocess,hashlib,fcntl,time
from pathlib import Path
b=Path('/21231_data1/liyuhan_t18_migration_20261027')
guard=(b/'resume_20261030.lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
mesh=b/'importer/assets_generated/backgrounds_v4/geometry/physics_lab_bench_v4.obj'
assert hashlib.sha256(mesh.read_bytes()).hexdigest()=='92c57a7e7facd7bd1968049c39dc826e919c000d8e6d7b7aff6ff147457839a2'
envfix=json.loads((b/'environment_fix_receipt.json').read_text())
env=dict(os.environ,PYTHONPATH=envfix['PYTHONPATH'],PYOPENGL_PLATFORM=envfix['PYOPENGL_PLATFORM'],LD_PRELOAD=envfix['LD_PRELOAD'],OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
py=envfix['python']; pre=subprocess.run([py,'-c','import cv2,genesis;print(cv2.__version__)'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
assert pre.returncode==0,pre.stderr.decode()[-500:]
launch=json.loads((b/'launch.json').read_text());started=[]
for q in launch:
 root=Path(q['root']);assert root.parent==b and root.name.endswith('_cwd_fix_assets_v2')
 live=[]
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:
   c=p.read_bytes()
   if str(root).encode() in c and b'worker_assets_v2.py' in c:live.append(int(p.parent.name))
  except (OSError,ProcessLookupError):pass
 if live:q['pid']=live[0];started.append(dict(root=str(root),pid=live[0],action='already_live'));continue
 lease=(root/'worker.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);lease.close()
 cmd=[py,str(b/'worker_assets_v2.py'),'--project',str(b/'importer/everyday_bifurcation_72k_T16_T20_v1'),'--plan',q['active_plan'],'--root',str(root),'--gpu','auto','--minimum-free-memory-mib','8192','--renderer-timeout-seconds','3600']
 with (root/'resume_20261030.log').open('a') as log:p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
 q['pid']=p.pid;started.append(dict(root=str(root),pid=p.pid,action='resumed',command=cmd))
time.sleep(3)
for q in started:
 p=Path('/proc')/str(q['pid'])/'cmdline';q['live_after_launch']=p.exists() and str(q['root']).encode() in p.read_bytes()
assert all(q['live_after_launch'] for q in started)
temp=b/'launch.json.tmp';temp.write_text(json.dumps(launch));temp.replace(b/'launch.json')
(b/'resume_20261030.json').write_text(json.dumps(started,indent=2))
(b/'deployment_status.json').write_text(json.dumps(dict(status='resumed_asset_verified_queues',queues=launch)))
print(json.dumps(started))
'''
if __name__=='__main__':
    result=remote_text('p26',CODE,timeout=65,attempts=1)
    (ROOT/'t18_p26_resume_20261030.json').write_text(result,encoding='utf8')
    print(result)
