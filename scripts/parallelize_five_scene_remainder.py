"""Distribute only unattempted jobs from the owned five-scene queue."""
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipts=[ROOT/('five_scene_parallel_'+str(i)+'_launch_20261021.json') for i in range(4)]
    if any(p.exists() for p in receipts):raise RuntimeError('parallel remainder already launched')
    previous=json.loads((ROOT/'five_scene_boundary_launch_20261020.json').read_text())
    code=r'''
import pathlib,json,subprocess,os,signal,time,hashlib,collections
launch=LAUNCH;base=pathlib.Path(launch['pipeline_root']);pid=launch['pid'];cmd=pathlib.Path('/proc')/str(pid)/'cmdline'
if not cmd.exists() or str(base/'pipeline_seedfixed.py').encode() not in cmd.read_bytes() or os.getpgid(pid)!=pid:raise RuntimeError('owned queue identity changed')
original=base/'validated_plan.json';jobs=json.loads(original.read_text());root=pathlib.Path(launch['root']);rows=json.loads((root/'status.json').read_text())
attempted={r['job_id'] for r in rows}|{p.parent.name for p in root.glob('*/result.json')}
remaining=[j for j in jobs if j['job_id'] not in attempted]
if len({j['job_id'] for j in remaining})!=len(remaining):raise ValueError('duplicate pending jobs')
directory=base/'parallel_remainder_20261021';directory.mkdir(exist_ok=False)
(directory/'source_contract.json').write_text(json.dumps(dict(previous_launch=launch,original_plan_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),attempted_jobs=len(attempted),pending_jobs=len(remaining),interrupted_partial_job_retained_in_original_root=True)))
os.killpg(pid,signal.SIGTERM)
for _ in range(50):
 if not subprocess.run(['pgrep','-g',str(pid)],capture_output=True).stdout:break
 time.sleep(.2)
else:raise RuntimeError('old owned process group did not exit')
out=[]
for i,gpu in enumerate([0,2,3,4]):
 d=directory/('shard_'+str(i));d.mkdir();plan=remaining[i::4]
 (d/'plan.json').write_text(json.dumps(plan))
 for name in ['five_scene_boundary_worker.py','five_scene_boundary_rules.py']:(d/name).write_bytes((base/name).read_bytes())
 with (d/'worker.log').open('w') as log:p=subprocess.Popen(['python3',str(d/'five_scene_boundary_worker.py'),'--plan',str(d/'plan.json'),'--root',str(d/'run'),'--gpu',str(gpu)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 out.append(dict(launch=dict(host='p25',root=str(d/'run'),pipeline_root=str(d),pid=p.pid,gpu=gpu,planned_intervals=len(plan),scenes=dict(collections.Counter(j['scene_id'] for j in plan)),previous_combined_pid=pid),plan=plan))
print(json.dumps(out))
'''.replace('LAUNCH',repr(previous))
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    rows=json.loads(p.stdout)
    for i,row in enumerate(rows):
        (ROOT/('five_scene_parallel_'+str(i)+'_plan_20261021.json')).write_text(json.dumps(row['plan']))
        receipts[i].write_text(json.dumps(row['launch'],indent=2))
    print(json.dumps([r['launch'] for r in rows]))


if __name__=='__main__':main()
