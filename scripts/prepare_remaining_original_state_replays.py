"""Queue T06/T10 missing-state recovery after this task's T09 GPU4 job.

Preserves continuous state measurements; does not invent collapse/propagation
thresholds or declare a source video visually verified from its replay.
"""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    target=ROOT/'t06_t10_missing_state_replay_launch_20261020.json'
    if target.exists():raise RuntimeError('existing launch receipt; inspect before resuming')
    evidence=json.loads((ROOT/'t06_t09_surviving_original_state_evidence.json').read_text())+json.loads((ROOT/'t10_surviving_original_state_evidence_20261020.json').read_text())
    missing={r['sample_id'] for r in evidence if r['scene_id'] in ['T06','T10'] and r['status']=='original_annotation_path_missing'}
    published={r['sample_id']:r for f in ROOT.glob('published_batch_*.json') for r in json.loads(f.read_text()) if r['sample_id'] in missing}
    jobs=[published[sid] for sid in sorted(missing)];plan=ROOT/'t06_t10_missing_state_replay_plan_20261020.json';plan.write_text(json.dumps(jobs))
    parent_path=ROOT/'t09_missing_state_replay_v2_launch_20261020.json'
    if not parent_path.exists():parent_path=ROOT/'t09_missing_state_replay_launch_20261020.json'
    parent=json.loads(parent_path.read_text(encoding='utf-8-sig'))
    root='/data_cached/wangzijun_p25/liyuhan/t06_t10_missing_states_20261020'
    subprocess.run(['ssh','-o','BatchMode=yes','p25','mkdir','-p',root],check=True)
    for file,name in [(plan,'plan.json'),(Path('scripts/t09_missing_state_worker.py'),'worker.py')]:subprocess.run(['scp','-q',str(file.resolve()),'p25:'+root+'/'+name],check=True)
    pipeline="""import pathlib,json,subprocess,time
root=pathlib.Path(ROOT_DIRECTORY)
pid=WAIT_PID
while True:
 p=pathlib.Path('/proc')/str(pid)/'cmdline'
 if not p.exists() or b't09_missing_state_replay' not in p.read_bytes():break
 (root/'queue_status.json').write_text(json.dumps(dict(status='waiting_for_owned_T09_job',pid=pid,planned=1480)))
 time.sleep(20)
command=['python3',str(root/'worker.py'),'--plan',str(root/'plan.json'),'--root',str(root/'run'),'--gpu','4']
with (root/'canary.log').open('w') as log:subprocess.run(command+['--limit','1'],stdout=log,stderr=subprocess.STDOUT,check=True)
rows=json.loads((root/'run/status.json').read_text())
if not rows or rows[0]['status']!='supplemental_original_backend_state':raise RuntimeError('original-backend canary failed')
(root/'queue_status.json').write_text(json.dumps(dict(status='running',planned=1480)))
with (root/'worker.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
(root/'queue_status.json').write_text(json.dumps(dict(status='completed')))
""".replace('ROOT_DIRECTORY',repr(root)).replace('WAIT_PID',str(parent['pid']))
    compile(pipeline,'pipeline.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(root)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))\n"
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root+'/run',pipeline_root=root,gpu=4,wait_for_owned_pid=parent['pid'],planned_states=len(jobs),
        scene_counts={s:sum(r['scene_id']==s for r in jobs) for s in ['T06','T10']},**json.loads(p.stdout))
    target.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
