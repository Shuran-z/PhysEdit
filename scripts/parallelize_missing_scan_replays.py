"""Split the owned T06/T10 queue onto two GPUs; preserve all cached states."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def partition(jobs):
    groups={scene:[j for j in jobs if j['scene_id']==scene] for scene in ['T06','T10']}
    if sum(map(len,groups.values()))!=len(jobs):raise ValueError('unexpected scene in owned queue')
    if len({j['sample_id'] for j in jobs})!=len(jobs):raise ValueError('duplicate source samples')
    if any(not rows for rows in groups.values()):raise ValueError('both scenes must be present')
    return groups


def main():
    receipt=ROOT/'t06_t10_missing_state_replay_launch_20261020.json'
    previous=json.loads(receipt.read_text())
    if (ROOT/'t10_parallel_state_replay_launch_20261020.json').exists():raise RuntimeError('split already launched')
    original='/data_cached/wangzijun_p25/liyuhan/t06_t10_missing_states_20261020'
    if previous['pipeline_root']!=original:raise ValueError('not the expected owned queue')
    code=r'''
import pathlib,json,subprocess,os,signal,time,hashlib
root=pathlib.Path(DIRECTORY);pid=PID
cmd=pathlib.Path('/proc')/str(pid)/'cmdline'
if not cmd.exists() or str(root/'pipeline.py').encode() not in cmd.read_bytes() or os.getpgid(pid)!=pid:raise RuntimeError('owned process identity changed')
jobs=json.loads((root/'plan.json').read_text())
PARTITION
groups=partition(jobs)
if {k:len(v) for k,v in groups.items()}!={'T06':600,'T10':880}:raise ValueError('original source set changed')
new=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t10_parallel_missing_states_20261020')
new.mkdir(exist_ok=False)
(root/'split_execution_source.json').write_text(json.dumps(dict(previous_pid=pid,source_plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),source_worker_sha256=hashlib.sha256((root/'worker.py').read_bytes()).hexdigest())))
# Only this identified process group is terminated. Completed state files stay.
os.killpg(pid,signal.SIGTERM)
for _ in range(50):
 if not subprocess.run(['pgrep','-g',str(pid)],capture_output=True).stdout:break
 time.sleep(.2)
else:raise RuntimeError('owned group did not stop; no second worker launched')
(root/'plan_t06.json').write_text(json.dumps(groups['T06']))
(new/'plan.json').write_text(json.dumps(groups['T10']))
(new/'worker.py').write_bytes((root/'worker.py').read_bytes())
launches={}
for scene,base,plan,run,gpu in [('T06',root,root/'plan_t06.json',root/'run','4'),('T10',new,new/'plan.json',new/'run_t10_parallel','1')]:
 with (base/'worker_parallel.log').open('w') as log:p=subprocess.Popen(['python3',str(base/'worker.py'),'--plan',str(plan),'--root',str(run),'--gpu',gpu],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 launches[scene]=dict(host='p25',root=str(run),pipeline_root=str(base),pid=p.pid,gpu=int(gpu),planned_states=len(groups[scene]),scene_counts={scene:len(groups[scene])},preserved_source_plan=str(root/'plan.json'),previous_combined_pid=pid)
(root/'queue_status.json').write_text(json.dumps(dict(status='split_into_parallel_scene_queues',launches=launches)))
print(json.dumps(launches))
'''
    import inspect
    code=code.replace('DIRECTORY',repr(original)).replace('PID',str(previous['pid'])).replace('PARTITION',inspect.getsource(partition))
    result=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=45)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    launches=json.loads(result.stdout)
    (ROOT/'t06_t10_combined_queue_before_split_20261020.json').write_text(json.dumps(previous,indent=2))
    receipt.write_text(json.dumps(launches['T06'],indent=2))
    (ROOT/'t10_parallel_state_replay_launch_20261020.json').write_text(json.dumps(launches['T10'],indent=2))
    print(json.dumps(launches))


if __name__=='__main__':main()
