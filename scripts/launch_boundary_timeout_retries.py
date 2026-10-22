"""Retry only execution timeouts on the GPU released by the finished T10 queue."""
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT
from scripts.register_five_scene_refinements import LAUNCHES


def main():
    receipt=ROOT/'five_scene_timeout_retry_launch_20261021.json'
    if receipt.exists():raise RuntimeError('timeout retry already launched')
    evidence=json.loads((ROOT/'five_scene_refinement_evidence_20261020.json').read_text())
    successful={x['job_id'] for b in evidence for x in b['rows'] if x['status']=='refined_local_interval'}
    failed={x['job_id']:dict(error=x['error'],previous_root=b['launch']['root']) for b in evidence for x in b['rows'] if x['status']=='failed' and 'timed out' in x['error'] and x['job_id'] not in successful}
    plans={j['job_id']:j for _,name in LAUNCHES if (ROOT/name).exists() for j in json.loads((ROOT/name).read_text())}
    jobs=[dict(plans[k],execution_retry=failed[k]) for k in sorted(failed)]
    if not jobs:raise RuntimeError('no unresolved execution timeouts')
    local=ROOT/'five_scene_timeout_retry_plan_20261021.json';local.write_text(json.dumps(jobs))
    directory='/data_cached/wangzijun_p25/liyuhan/five_scene_timeout_retry_20261021'
    code="import pathlib\np=pathlib.Path("+repr(directory)+")\np.mkdir(exist_ok=False)"
    remote_text('p25',code)
    for path,name in [(local,'plan.json'),(Path('scripts/five_scene_boundary_worker.py'),'five_scene_boundary_worker.py'),(Path('scripts/five_scene_boundary_rules.py'),'five_scene_boundary_rules.py')]:
        subprocess.run(['scp','-q',str(path.resolve()),'p25:'+directory+'/'+name],check=True,timeout=120)
    code=r'''
import pathlib,json,subprocess
r=pathlib.Path(DIRECTORY)
with (r/'worker.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'five_scene_boundary_worker.py'),'--plan',str(r/'plan.json'),'--root',str(r/'run'),'--gpu','1','--renderer-timeout-seconds','3600'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p25',root=str(r/'run'),pipeline_root=str(r),gpu=1,pid=p.pid,planned_intervals=COUNT,renderer_timeout_seconds=3600,scope='execution timeout retry; physical parameters and source event labels retained')))
'''.replace('DIRECTORY',repr(directory)).replace('COUNT',str(len(jobs)))
    launch=json.loads(remote_text('p25',code));receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
