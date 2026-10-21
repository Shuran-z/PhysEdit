"""Separate exact published-seed endpoint replays from conditional refinement."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'five_scene_source_replay_launch_20261020.json'
    if receipt.exists():raise RuntimeError('diagnostic task already launched')
    launch=json.loads((ROOT/'five_scene_boundary_launch_20261020.json').read_text())
    root=launch['pipeline_root']+'/published_seed_diagnostic'
    wait=json.loads((ROOT/'t13_unreproduced_control_launch_20261020.json').read_text())
    subprocess.run(['ssh','p25','mkdir','-p',root],check=True)
    for name in ['five_scene_boundary_worker.py','five_scene_boundary_rules.py']:
        subprocess.run(['scp','-q',str(Path('scripts',name).resolve()),'p25:'+root+'/'+name],check=True)
    code=r'''
import pathlib,json,subprocess
source=pathlib.Path(SOURCE_DIRECTORY);root=pathlib.Path(ROOT_DIRECTORY)
plan={j['job_id']:j for j in json.loads((source/'plan.json').read_text())};status=json.loads((source/'run_seedfixed/status.json').read_text());jobs=[];seen=set()
for row in status:
 if row['status']!='failed' or 'endpoint event not reproduced' not in row.get('error',''):continue
 j=plan[row['job_id']];key=(j['scene_id'],j['family_id'])
 if key in seen:continue
 seen.add(key);jobs.append(j)
(root/'plan.json').write_text(json.dumps(jobs))
pipeline="""import pathlib,subprocess,json,time
r=pathlib.Path(RUN_DIRECTORY)
while True:
 p=pathlib.Path('/proc')/str(WAIT_PID)/'cmdline'
 if not p.exists() or b't13_unreproduced_control_20261020' not in p.read_bytes():break
 (r/'queue_status.json').write_text(json.dumps(dict(status='waiting_for_owned_GPU3_control')));time.sleep(20)
(r/'queue_status.json').write_text(json.dumps(dict(status='replaying_exact_published_endpoint_seeds')))
with (r/'worker.log').open('w') as log:subprocess.run(['python3',str(r/'five_scene_boundary_worker.py'),'--root',str(r/'run'),'--plan',str(r/'plan.json'),'--gpu','3','--endpoints-only','--published-endpoint-replay'],stdout=log,stderr=subprocess.STDOUT,check=True)
(r/'queue_status.json').write_text(json.dumps(dict(status='completed_published_seed_diagnostic')))
""".replace('RUN_DIRECTORY',repr(str(root))).replace('WAIT_PID',str(WAIT_PID))
(root/'pipeline.py').write_text(pipeline)
with (root/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(root/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(pid=p.pid,planned_contexts=len(jobs),scenes=sorted({j['scene_id'] for j in jobs}))))
'''.replace('SOURCE_DIRECTORY',repr(launch['pipeline_root'])).replace('ROOT_DIRECTORY',repr(root)).replace('WAIT_PID',str(wait['pid']))
    p=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    data=dict(host='p25',root=root+'/run',pipeline_root=root,gpu=3,diagnostic_only=True,**json.loads(p.stdout))
    receipt.write_text(json.dumps(data,indent=2));print(json.dumps(data))


if __name__=='__main__':main()
