"""Resume only event-usable T15 tail failures, after this task's GPU3 controls."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    target=ROOT/'t15_event_tail_refinement_launch_20261020.json'
    if target.exists():raise RuntimeError('existing launch; inspect before resuming')
    root='/data_cached/wangzijun_p25/liyuhan/t15_event_specific_tail_refinement_20261020'
    wait=[json.loads((ROOT/name).read_text()) for name in ['t13_original_full_retry_launch_20261020.json','t13_remaining_full_retry_launch_20261020.json']]
    parents=[(r['pid'],r['root']) for r in wait]
    subprocess.run(['ssh','-o','BatchMode=yes','p25','mkdir','-p',root],check=True)
    subprocess.run(['scp','-q',str(Path('scripts/t15_refine_existing_scans_worker.py').resolve()),'p25:'+root+'/worker.py'],check=True)
    pipeline="""import pathlib,json,subprocess,time
root=pathlib.Path(ROOT_DIRECTORY)
parents=OWN_PARENTS
while True:
 active=[]
 for pid,scope in parents:
  p=pathlib.Path('/proc')/str(pid)/'cmdline'
  if p.exists() and scope.encode() in p.read_bytes():active.append(pid)
 if not active:break
 (root/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_owned_T13_GPU3_jobs',pids=active)))
 time.sleep(20)
(root/'resource_status.json').write_text(json.dumps(dict(status='running',gpu=3)))
command=['python3',str(root/'worker.py'),'--root',str(root),'--gpu','3','--resume-status','/data_cached/wangzijun_p25/liyuhan/t15_refined_missing_intervals_20261019/status.json','--allow-unsettled-tail-for-observed-event','--scans','/data_cached/wangzijun_p25/liyuhan/t15_all_original_contexts_20261019','/data_cached/wangzijun_p25/liyuhan/t15_expanded_original_contexts_20261019']
with (root/'worker.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
(root/'resource_status.json').write_text(json.dumps(dict(status='completed')))
""".replace('ROOT_DIRECTORY',repr(root)).replace('OWN_PARENTS',repr(parents))
    compile(pipeline,'pipeline.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root,gpu=3,wait_for_owned_pids=[r[0] for r in parents],planned_resumable_tail_intervals=6,other_scene_exit_intervals_retained=2,**json.loads(p.stdout))
    target.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
