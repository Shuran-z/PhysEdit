"""Queue original-entry controls for newly discovered T13 failures."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    dest=ROOT/'t13_remaining_full_retry_launch_20261020.json'
    if dest.exists():raise RuntimeError('task already launched; inspect receipt before resuming')
    diagnostics=json.loads((ROOT/'t13_all_failed_endpoint_diagnostics_20261020.json').read_text())
    failed={r['job_id'] for r in diagnostics if r['root']=='t13_current_boundary_context_bound_20261019'}
    previous=json.loads((ROOT/'t13_original_full_retry_plan_20261020.json').read_text());already={r['job_id'] for r in previous}
    jobs=[r for r in json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()) if r['job_id'] in failed-already]
    plan=ROOT/'t13_remaining_full_retry_plan_20261020.json';plan.write_text(json.dumps(jobs))
    parent=json.loads((ROOT/'t13_original_full_retry_launch_20261020.json').read_text());root='/data_cached/wangzijun_p25/liyuhan/t13_remaining_full_retry_20261020'
    subprocess.run(['ssh','-o','BatchMode=yes','p25','mkdir','-p',root],check=True)
    for file,name in [(plan,'plan.json'),(Path('scripts/t13_current_boundary_worker.py'),'worker.py')]:subprocess.run(['scp','-q',str(file.resolve()),'p25:'+root+'/'+name],check=True)
    pipeline="""import pathlib,json,subprocess,time
root=pathlib.Path(ROOT_DIRECTORY)
while True:
 p=pathlib.Path('/proc')/str(WAIT_PID)/'cmdline'
 if not p.exists() or b't13_original_full_retry_20261020' not in p.read_bytes():break
 (root/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_owned_GPU3_job',pid=WAIT_PID,planned=PLANNED)))
 time.sleep(20)
(root/'resource_status.json').write_text(json.dumps(dict(status='running',gpu=3,planned=PLANNED)))
with (root/'worker.log').open('w') as log:subprocess.run(['python3',str(root/'worker.py'),'--plan',str(root/'plan.json'),'--root',str(root),'--gpu','3','--original-full-render'],stdout=log,stderr=subprocess.STDOUT,check=True)
(root/'resource_status.json').write_text(json.dumps(dict(status='completed',planned=PLANNED)))
""".replace('ROOT_DIRECTORY',repr(root)).replace('WAIT_PID',str(parent['pid'])).replace('PLANNED',str(len(jobs)))
    compile(pipeline,'pipeline.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root,gpu=3,planned_intervals=len(jobs),wait_for_owned_pid=parent['pid'],profile='original_v6_full_render',**json.loads(p.stdout))
    dest.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
