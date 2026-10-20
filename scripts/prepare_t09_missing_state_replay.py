"""Launch isolated original-backend supplementation of missing T09 states."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT

REMOTE_ROOT='/data_cached/wangzijun_p25/liyuhan/t09_missing_state_replay_20261020'


def main():
    previous=ROOT/'t09_missing_state_replay_launch_20261020.json'
    if previous.exists():raise RuntimeError('launch receipt exists; inspect/resume that task instead of launching a duplicate')
    evidence=json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text())
    missing={r['sample_id'] for r in evidence if r['scene_id']=='T09' and r['status']=='original_annotation_path_missing'}
    published={r['sample_id']:r for f in ROOT.glob('published_batch_*.json') for r in json.loads(f.read_text()) if r['scene_id']=='T09'}
    jobs=[published[sid] for sid in sorted(missing)]
    if len(jobs)!=300:raise ValueError('missing source set changed; inspect before launch')
    plan=ROOT/'t09_missing_state_replay_plan_20261020.json';plan.write_text(json.dumps(jobs))
    subprocess.run(['ssh','-o','BatchMode=yes','p25','mkdir','-p',REMOTE_ROOT],check=True)
    for source,name in [(plan,'plan.json'),(Path('scripts/t09_missing_state_worker.py'),'worker.py')]:
        subprocess.run(['scp','-q',str(source.resolve()),'p25:'+REMOTE_ROOT+'/'+name],check=True)
    code=r"""
import json,pathlib,subprocess
root=pathlib.Path(REMOTE_DIRECTORY)
pipeline='''import json,pathlib,subprocess,time
root=pathlib.Path(TASK_DIRECTORY)
command=['python3',str(root/'worker.py'),'--plan',str(root/'plan.json'),'--root',str(root/'run'),'--gpu','4']
with (root/'canary.log').open('w') as log:subprocess.run(command+['--limit','1'],stdout=log,stderr=subprocess.STDOUT,check=True)
rows=json.loads((root/'run/status.json').read_text())
if not rows or rows[0]['status']!='supplemental_original_backend_state':raise RuntimeError('original-backend source canary failed')
while pathlib.Path('/proc/3813793/cmdline').exists():
 (root/'pipeline_status.json').write_text(json.dumps(dict(status='waiting_for_owned_T13_GPU4_job',pid=3813793)))
 time.sleep(20)
(root/'pipeline_status.json').write_text(json.dumps(dict(status='running_missing_300',gpu=4)))
with (root/'worker.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
(root/'pipeline_status.json').write_text(json.dumps(dict(status='completed')))
'''.replace('TASK_DIRECTORY',repr(str(root)))
(root/'pipeline.py').write_text(pipeline)
with (root/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(root/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p25',root=str(root/'run'),pipeline_root=str(root),pid=p.pid,gpu=4,planned_states=300,wait_for_owned_pid=3813793)))
"""
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.replace('REMOTE_DIRECTORY',repr(REMOTE_ROOT)).encode(),capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=json.loads(p.stdout);previous.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
