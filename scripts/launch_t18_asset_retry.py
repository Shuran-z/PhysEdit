"""Retry only identified missing-original-background failures after restoration."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t18_asset_retry_launch_20261020.json'
    if receipt.exists():raise RuntimeError('already launched; inspect existing task')
    restore=json.loads((ROOT/'t18_original_background_restore_20261020.json').read_text())
    wait=json.loads((ROOT/'t09_pull_refinement_launch_20261020.json').read_text())
    parent=json.loads((ROOT/'t18_table_contact_search_launch_20261020.json').read_text())
    base=str(Path(parent['root']).parent).replace('\\','/');root=base+'/asset_retry_run'
    subprocess.run(['ssh','p25','mkdir','-p',root],check=True)
    subprocess.run(['scp','-q',str(Path('scripts/t18_table_contact_boundary_worker.py').resolve()),'p25:'+root+'/worker.py'],check=True)
    code=r'''
import json,pathlib,subprocess,time
base=pathlib.Path(BASE_DIRECTORY);root=base/'asset_retry_run'
restore=RESTORE
for row in restore['links']:
 if pathlib.Path(row['destination']).resolve()!=pathlib.Path(row['source']).resolve():raise ValueError('restored paths changed')
status=json.loads((base/'run/status.json').read_text())
failed={r['job_id'] for r in status if r['status']=='failed' and 'original renderer failed' in r.get('error','') and any('physics_lab_bench_v4.json' in p.read_text(errors='replace') and 'FileNotFoundError' in p.read_text(errors='replace') for p in (base/'run'/r['job_id']).glob('*/run.log'))}
jobs=[j for j in json.loads((base/'inputs/plan_all567.json').read_text()) if j['job_id'] in failed]
(root/'plan.json').write_text(json.dumps(jobs))
pipeline="""import pathlib,subprocess,time,json
r=pathlib.Path(RUN_DIRECTORY)
while True:
 p=pathlib.Path('/proc')/str(WAIT_PID)/'cmdline'
 if not p.exists() or b't09_pull_event_refinement_20261020' not in p.read_bytes():break
 (r/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_owned_T09_GPU1_task')));time.sleep(20)
(r/'resource_status.json').write_text(json.dumps(dict(status='running',gpu=1)))
with (r/'worker.log').open('w') as log:subprocess.run(['python3',str(r/'worker.py'),'--root',str(r),'--plan',str(r/'plan.json'),'--gpu','1'],stdout=log,stderr=subprocess.STDOUT,check=True)
(r/'resource_status.json').write_text(json.dumps(dict(status='finished')))
""".replace('RUN_DIRECTORY',repr(str(root))).replace('WAIT_PID',str(WAIT_PID))
(root/'pipeline.py').write_text(pipeline)
with (root/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(root/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(pid=p.pid,planned_contexts=len(jobs),retry_job_ids=sorted(failed))))
'''.replace('BASE_DIRECTORY',repr(base)).replace('RESTORE',repr(restore)).replace('WAIT_PID',str(wait['pid']))
    p=subprocess.run(['ssh','p25','python3 -'],input=code.encode(),capture_output=True,timeout=40)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=dict(host='p25',root=root,gpu=1,wait_for_owned_pid=wait['pid'],**json.loads(p.stdout))
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
