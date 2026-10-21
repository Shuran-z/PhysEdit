"""Two isolated original-entry replays to diagnose a still-unreproduced endpoint."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    dest=ROOT/'t13_unreproduced_control_launch_20261020.json'
    if dest.exists():raise RuntimeError('control already dispatched')
    # Select from the completed original-entry retries, not a new event rule.
    launch=json.loads((ROOT/'t13_remaining_full_retry_launch_20261020.json').read_text())
    query="import json,pathlib;print(json.dumps(json.loads((pathlib.Path("+repr(launch['root'])+")/'status.json').read_text())))"
    p=subprocess.run(['ssh','p25','python3 -'],input=query.encode(),capture_output=True,timeout=30);p.check_returncode()
    failed=next(r['job_id'] for r in json.loads(p.stdout) if r['status']=='failed' and 'published endpoint not reproduced' in r['error'])
    job=next(j for j in json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()) if j['job_id']==failed)
    root='/data_cached/wangzijun_p25/liyuhan/t13_unreproduced_control_20261020'
    subprocess.run(['ssh','p25','mkdir','-p',root],check=True)
    subprocess.run(['scp','-q',str(Path('scripts/t13_current_boundary_worker.py').resolve()),'p25:'+root+'/worker.py'],check=True)
    wait=json.loads((ROOT/'t15_event_tail_refinement_launch_20261020.json').read_text())
    pipeline=r'''
import pathlib,json,subprocess,time,hashlib,math
r=pathlib.Path(ROOT_DIRECTORY);job=JOB
(r/'plan.json').write_text(json.dumps([job]))
while True:
 p=pathlib.Path('/proc')/str(WAIT_PID)/'cmdline'
 if not p.exists() or b't15_event_specific_tail_refinement_20261020' not in p.read_bytes():break
 (r/'status.json').write_text(json.dumps(dict(status='waiting_for_owned_GPU3_task')));time.sleep(20)
for i in range(2):
 while float(subprocess.check_output(['nvidia-smi','-i','3','--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<12*1024:time.sleep(20)
 (r/'status.json').write_text(json.dumps(dict(status='running_original_entry_control',repeat=i)))
 with (r/('repeat_'+str(i)+'.log')).open('w') as log:subprocess.run(['python3',str(r/'worker.py'),'--root',str(r/('repeat_'+str(i))),'--plan',str(r/'plan.json'),'--gpu','3','--original-full-render'],stdout=log,stderr=subprocess.STDOUT,check=True)
states=[]
for i in range(2):
 folder=r/('repeat_'+str(i))/job['job_id']; paths=list(folder.glob('*/physics.json'));rows=[]
 for path in paths:
  s=json.loads(path.read_text());positions=[[o['position'] for o in f['objects']] for f in s['frames']]
  rows.append(dict(theta=float(path.parent.name),state_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),positions=positions))
 states.append(rows)
comparisons=[]
for a in states[0]:
 for b in states[1]:
  if a['theta']==b['theta']:
   delta=max(math.dist(x,y) for fa,fb in zip(a['positions'],b['positions']) for x,y in zip(fa,fb))
   comparisons.append(dict(theta=a['theta'],max_between_repeat_position_difference_m=delta))
(r/'comparison.json').write_text(json.dumps(dict(job_id=job['job_id'],comparisons=comparisons,source_labels_unchanged=True),indent=2))
(r/'status.json').write_text(json.dumps(dict(status='completed_original_entry_control',job_id=job['job_id'])))
'''.replace('ROOT_DIRECTORY',repr(root)).replace('JOB',repr(job)).replace('WAIT_PID',str(wait['pid']))
    compile(pipeline,'control.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    receipt=dict(host='p25',root=root,gpu=3,job_id=failed,diagnostic_only=True,**json.loads(p.stdout))
    dest.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':main()
