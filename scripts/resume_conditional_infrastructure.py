"""Resume stopped queues with intact source hashes and resource-only guards."""
import base64
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


GUARD=r'''
import sys,pathlib,shutil,time,subprocess,fcntl,runpy,json
worker=sys.argv[1];args=sys.argv[2:];root=pathlib.Path(args[args.index('--root')+1])
original_disk_usage=shutil.disk_usage
def disk_usage(path):
 while True:
  usage=original_disk_usage(path)
  if usage.free>=20*1024**3:return usage
  (root/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_disk',minimum_free_GiB=20)))
  time.sleep(20)
shutil.disk_usage=disk_usage
while True:
 cards=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits']).decode().splitlines()
 lease=None
 for row in sorted(cards,key=lambda r:int(r.split(',')[1]),reverse=True):
  gpu,free=[x.strip() for x in row.split(',')]
  if int(free)<8192:continue
  candidate=pathlib.Path('/tmp/physedit_conditional_gpu_'+gpu+'.lock').open('a')
  try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:candidate.close();continue
  lease=candidate;break
 if lease:break
 (root/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',gpu='auto')));time.sleep(20)
args[args.index('--gpu')+1]=gpu
sys.argv=[worker]+args;sys.path.insert(0,str(pathlib.Path(worker).parent))
try:runpy.run_path(worker,run_name='__main__')
finally:lease.close()
'''


def main():
    marker=ROOT/'conditional_family_launches_20261023.json'
    launches=json.loads(marker.read_text());changes=[]
    for launch in launches:
        if launch['host']!='p25' or 'five_scene_own_seed' in launch['root']:continue
        code=r'''
import pathlib,json,hashlib,subprocess,os,base64,fcntl
l=LAUNCH;r=pathlib.Path(l['root']);b=pathlib.Path(l['pipeline_root']);marker=r/'infrastructure_recovery_20261025.json'
if marker.exists():print(marker.read_text());raise SystemExit
p=pathlib.Path('/proc')/str(l['pid'])/'cmdline'
if p.exists() and str(b).encode() in p.read_bytes():raise ValueError('queue still running; do not duplicate')
lock=(r/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if hashlib.sha256(pathlib.Path(l['plan']).read_bytes()).hexdigest()!=l['plan_sha256']:raise ValueError('plan changed')
guard=b/'resource_guard_20261025.py';guard.write_bytes(base64.b64decode(GUARD))
(r/'status_before_infrastructure_recovery_20261025.json').write_bytes((r/'status.json').read_bytes())
python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
lock.close()
with (r/'infrastructure_recovery_20261025.log').open('w') as log:
 p=subprocess.Popen([python,str(guard),str(b/'conditional_family_search.py'),'--plan',l['plan'],'--root',str(r),'--gpu','auto','--python',python],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
result=dict(l,previous_pid=l['pid'],pid=p.pid,resource_guard_sha256=hashlib.sha256(guard.read_bytes()).hexdigest(),resource_recovery='disk wait and GPU lease; frozen worker/backend/plan unchanged')
marker.write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''.replace('LAUNCH',repr(launch)).replace('GUARD',repr(base64.b64encode(GUARD.encode()).decode()))
        updated=json.loads(remote_text('p25',code,timeout=60))
        launch.update(updated);changes.append(updated)
        marker.write_text(json.dumps(launches,indent=2))
    (ROOT/'conditional_infrastructure_recovery_20261025.json').write_text(json.dumps(changes,indent=2))
    print(json.dumps([dict(root=l['root'],pid=l['pid']) for l in changes]))


if __name__=='__main__':main()
