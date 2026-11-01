"""Two isolated repetitions of the unresolved original T07-B endpoint."""
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT

CODE=r'''
import json,subprocess,os,fcntl,hashlib
from pathlib import Path
old=Path('/data_cached/wangzijun_p25/liyuhan/t07_B_original_plus_seed_20261027')
b=old.parent/'t07_B_endpoint_repeats_20261030';b.mkdir(exist_ok=True)
lock=(b/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
marker=b/'launch.json'
if marker.exists():print(marker.read_text());raise SystemExit(0)
job=json.loads((old/'plan.json').read_text())[0];job['search_grid']=[job['source_theta']]
(b/'plan.json').write_text(json.dumps([job]))
driver=r"""
import subprocess,os,json,sys
from pathlib import Path
b=Path(__file__).parent;old=Path(OLD)
results=[]
for i in range(2):
 root=b/('repeat_'+str(i));root.mkdir(exist_ok=True)
 cmd=[sys.executable,str(old/'worker.py'),'--plan',str(b/'plan.json'),'--root',str(root),'--gpu','auto','--minimum-free-memory-mib','12288','--preserve-render-settings']
 with (root/'worker.log').open('a') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONPATH=str(old)),timeout=7200)
 status=root/'results.json';results.append(dict(repeat=i,returncode=r.returncode,results=json.loads(status.read_text()) if status.exists() else None))
 (b/'status.json').write_text(json.dumps(results,indent=2))
""".replace('OLD',repr(str(old)))
(b/'driver.py').write_text(driver)
with (b/'driver.log').open('a') as log:p=subprocess.Popen(['python3',str(b/'driver.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(host='p25',root=str(b),pid=p.pid,planned_repeats=2,target_theta=job['source_theta'],sample_id=job['sample_id'],plan_sha256=hashlib.sha256((b/'plan.json').read_bytes()).hexdigest(),scope='Endpoint repeatability diagnostic only; preserve published negative label and original interval; no seed substitution or new boundary certification')
marker.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
if __name__=='__main__':
    result=remote_text('p25',CODE,timeout=30,attempts=1)
    (ROOT/'t07_endpoint_repeats_launch_20261030.json').write_text(result,encoding='utf8');print(result)
