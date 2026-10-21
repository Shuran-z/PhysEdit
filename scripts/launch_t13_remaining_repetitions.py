"""Run two predeclared original-entry repetitions of the remaining T13 tasks."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t13_remaining_repetitions_launch_20261020.json'
    if receipt.exists():raise RuntimeError('bounded repetitions already launched')
    evidence=json.loads((ROOT/'t13_current_solver_evidence_20261019.json').read_text())
    completed={r['result']['job_id'] for r in evidence}
    jobs=[j for j in json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()) if j['job_id'] not in completed]
    root='/data_cached/wangzijun_p25/liyuhan/t13_remaining_repetitions_20261020'
    plan=ROOT/'t13_remaining_repetitions_plan_20261020.json';plan.write_text(json.dumps(jobs))
    subprocess.run(['ssh','p25','mkdir','-p',root],check=True)
    for p,name in [(plan,'plan.json'),(Path('scripts/t13_current_boundary_worker.py'),'worker.py')]:subprocess.run(['scp','-q',str(p.resolve()),'p25:'+root+'/'+name],check=True)
    pipeline=r'''
import pathlib,json,subprocess,time
r=pathlib.Path(ROOT_DIRECTORY)
for i in range(2):
 while float(subprocess.check_output(['nvidia-smi','-i','3','--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<18*1024:
  (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',repeat=i,gpu=3)));time.sleep(20)
 (r/'resource_status.json').write_text(json.dumps(dict(status='running_original_entry_repetition',repeat=i,predeclared_repetitions=2)))
 with (r/('repeat_'+str(i)+'.log')).open('w') as log:subprocess.run(['python3',str(r/'worker.py'),'--root',str(r/('repeat_'+str(i))),'--plan',str(r/'plan.json'),'--gpu','3','--original-full-render'],stdout=log,stderr=subprocess.STDOUT,check=True)
(r/'resource_status.json').write_text(json.dumps(dict(status='completed_bounded_repetitions',predeclared_repetitions=2)))
'''.replace('ROOT_DIRECTORY',repr(root))
    compile(pipeline,'repetitions.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root,gpu=3,planned_intervals=len(jobs),predeclared_repetitions=2,repeat_roots=[root+'/repeat_'+str(i) for i in range(2)],**json.loads(p.stdout))
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
