"""Independent same-seed replay of the eight unresolved release contexts."""
import base64
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t13_seed0_repeat_launch_20261025.json'
    if marker.exists():print(marker.read_text());return
    base='/data_cached/wangzijun_p25/liyuhan/t13_seed0_repeat_20261025'
    files={n:base64.b64encode(Path(p).read_bytes()).decode() for n,p in
           [('worker.py','scripts/t13_current_boundary_worker.py'),('genesis_seed_bootstrap.py','scripts/genesis_seed_bootstrap.py'),('plan.json',ROOT/'t13_remaining_seeded_scans_plan_20261021.json')]}
    code=r"""
import pathlib,json,base64,subprocess,os,hashlib
b=pathlib.Path(BASE);b.mkdir(exist_ok=False)
for n,raw in FILES.items():(b/n).write_bytes(base64.b64decode(raw))
r=b/'run';r.mkdir()
supervisor=r'''import pathlib,subprocess,time,json,fcntl,shutil,os
b=pathlib.Path(HERE);r=b/'run';python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
while True:
 if shutil.disk_usage(r).free<20*1024**3:
  (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_disk')));time.sleep(20);continue
 rows=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits']).decode().splitlines();lease=None
 for row in sorted(rows,key=lambda x:int(x.split(',')[1]),reverse=True):
  gpu,free=[x.strip() for x in row.split(',')]
  if int(free)<18432:continue
  candidate=pathlib.Path('/tmp/physedit_conditional_gpu_'+gpu+'.lock').open('a')
  try:fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:candidate.close();continue
  lease=candidate;break
 if lease:break
 (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',minimum_free_memory_mib=18432)));time.sleep(20)
(r/'resource_status.json').write_text(json.dumps(dict(status='running_fixed_seed_repeat',gpu=gpu)))
try:
 code=subprocess.call([python,str(b/'worker.py'),'--plan',str(b/'plan.json'),'--root',str(r),'--gpu',gpu,'--original-full-render','--init-seed','0','--seed-bootstrap',str(b/'genesis_seed_bootstrap.py'),'--supplemental-scan'])
finally:lease.close()
(r/'resource_status.json').write_text(json.dumps(dict(status='worker_ended',returncode=code,gpu=gpu)))
'''.replace('HERE',repr(str(b)))
(b/'supervisor.py').write_text(supervisor)
contract=dict(seed=0,independent_same_seed_repeat=True,original_publication_seed_recovered=False,diagnostic_only=True,formal_nearacc_eligible=False,plan_sha256=hashlib.sha256((b/'plan.json').read_bytes()).hexdigest())
(r/'source_contract.json').write_text(json.dumps(contract,indent=2))
with (r/'worker.log').open('w') as log:p=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(b/'supervisor.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
print(json.dumps(dict(host='p25',root=str(r),pipeline_root=str(b),pid=p.pid,planned_intervals=8,diagnostic_only=True,seed=0,**{'source_contract':contract})))
""".replace('BASE',repr(base)).replace('FILES',repr(files))
    launch=json.loads(remote_text('p25',code,timeout=60));marker.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
