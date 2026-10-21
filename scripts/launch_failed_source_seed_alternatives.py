"""Try the other original endpoint seed for failed conditional brackets outside the same-seed T11 scans."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'five_scene_alternate_seed_launch_20261020.json'
    if receipt.exists():raise RuntimeError('alternate original-seed execution already exists')
    parent=json.loads((ROOT/'five_scene_boundary_launch_20261020.json').read_text())
    root=parent['pipeline_root']+'/alternate_published_seed'
    subprocess.run(['ssh','p25','mkdir','-p',root],check=True)
    for name in ['five_scene_boundary_worker.py','five_scene_boundary_rules.py']:
        subprocess.run(['scp','-q',str(Path('scripts',name).resolve()),'p25:'+root+'/'+name],check=True)
    code=r'''
import pathlib,json,subprocess
base=pathlib.Path(BASE_DIRECTORY);root=pathlib.Path(ROOT_DIRECTORY)
status=json.loads((base/'run_seedfixed/status.json').read_text());failed={r['job_id'] for r in status if r['status']=='failed' and 'endpoint event not reproduced' in r.get('error','')}
jobs=[]
for job in json.loads((base/'plan.json').read_text()):
 if job['job_id'] not in failed:continue
 a,b=[e['config'] for e in job['endpoints']]
 if a.get('random_seed')==b.get('random_seed'):continue
 job['seed_endpoint']=1;job['seed_choice_policy']='other published endpoint seed; both original endpoint outcomes must reproduce before refinement';jobs.append(job)
jobs.sort(key=lambda j:(j['family_id']!='driver_initial_speed_mps',j['family_id']))
(root/'plan.json').write_text(json.dumps(jobs))
with (root/'worker.log').open('w') as log:p=subprocess.Popen(['python3',str(root/'five_scene_boundary_worker.py'),'--root',str(root/'run'),'--plan',str(root/'plan.json'),'--gpu','0'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(pid=p.pid,plan=jobs)))
'''.replace('BASE_DIRECTORY',repr(parent['pipeline_root'])).replace('ROOT_DIRECTORY',repr(root))
    p=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    result=json.loads(p.stdout);jobs=result.pop('plan')
    (ROOT/'five_scene_alternate_seed_plan_20261020.json').write_text(json.dumps(jobs))
    launch=dict(host='p25',root=root+'/run',pipeline_root=root,gpu=0,planned_attempts=len(jobs),**result)
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
