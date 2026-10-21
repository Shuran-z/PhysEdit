"""Run first-five endpoint checks, then the fair full queue on p25 GPU0."""
import json
import argparse
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--restart-seed-fixed',action='store_true');args=parser.parse_args()
    receipt=ROOT/'five_scene_boundary_launch_20261020.json'
    if receipt.exists():
        if not args.restart_seed_fixed:raise RuntimeError('existing execution; inspect before launching a duplicate')
        historical=ROOT/'five_scene_boundary_initial_seed_diagnostic_launch_20261020.json'
        if historical.exists():raise RuntimeError('seed-fixed restart already recorded; inspect rather than duplicate')
        historical.write_text(receipt.read_text())
    root='/data_cached/wangzijun_p25/liyuhan/five_scene_boundary_20261020'
    for folder in [root,root+'/first_five']:
        for name in ['five_scene_boundary_worker.py','five_scene_boundary_rules.py']:
            subprocess.run(['scp','-q',str(Path('scripts',name).resolve()),'p25:'+folder+'/'+name],check=True)
    pipeline=r'''import collections,json,pathlib,subprocess,time,sys
root=pathlib.Path(ROOT_DIRECTORY);sys.path.insert(0,str(root))
from five_scene_boundary_rules import intervene
def save(name,value):
 p=root/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2));t.replace(p)
first=root/'first_five'
save('queue_status.json',dict(status='first_five_original_endpoint_checks',gpu=0))
with (root/'first_five_seedfixed.log').open('w') as log:subprocess.run(['python3',str(first/'five_scene_boundary_worker.py'),'--root',str(first/'run_seedfixed'),'--plan',str(first/'plan.json'),'--gpu','0','--endpoints-only'],stdout=log,stderr=subprocess.STDOUT,check=True)
deadline=time.monotonic()+4*3600
while not (root/'plan.json').exists():
 if time.monotonic()>deadline:raise RuntimeError('full original-source preparation not delivered within four hours; canary evidence retained')
 save('queue_status.json',dict(status='waiting_for_full_source_preparation'));time.sleep(20)
ready=[];pending=[]
for job in json.loads((root/'plan.json').read_text()):
 try:intervene(job,sum(job['bracket'])/2);ready.append(job)
 except Exception as exc:pending.append(dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],error=str(exc)))
scenes={s:collections.defaultdict(list) for s in ['T01','T04','T05','T08','T11']}
for job in ready:scenes[job['scene_id']][job['family_id']].append(job)
ordered=[]
while any(any(q.values()) for q in scenes.values()):
 for scene,families in scenes.items():
  live=[f for f,q in families.items() if q]
  if not live:continue
  chosen=min(live,key=lambda f:sum(j['scene_id']==scene and j['family_id']==f for j in ordered))
  ordered.append(families[chosen].pop(0))
save('validated_plan.json',ordered);save('parameter_recipe_pending.json',pending)
save('queue_status.json',dict(status='running_fair_original_backend_queue',planned=len(ordered),held_for_recipe=len(pending),gpu=0))
with (root/'worker_seedfixed.log').open('w') as log:subprocess.run(['python3',str(root/'five_scene_boundary_worker.py'),'--root',str(root/'run_seedfixed'),'--plan',str(root/'validated_plan.json'),'--gpu','0'],stdout=log,stderr=subprocess.STDOUT,check=True)
save('queue_status.json',dict(status='listed_intervals_finished_review_failures',planned=len(ordered)))
'''.replace('ROOT_DIRECTORY',repr(root))
    compile(pipeline,'pipeline.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline_seedfixed.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline_seedfixed.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline_seedfixed.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root+'/run_seedfixed',canary_root=root+'/first_five/run_seedfixed',pipeline_root=root,gpu=0,scenes=['T01','T04','T05','T08','T11'],**json.loads(p.stdout))
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
