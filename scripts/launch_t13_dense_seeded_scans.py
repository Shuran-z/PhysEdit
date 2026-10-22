"""Complete the published grid for the two sparse seed0 scans with no flip."""
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t13_dense_seeded_scans_launch_20261021.json'
    if receipt.exists():raise RuntimeError('dense seed scans already launched')
    prior=json.loads((ROOT/'t13_seeded_supplement_evidence_20261021.json').read_text())
    missing={e['result']['job_id'] for e in prior if not e['result']['local_intervals']}
    jobs=[j for j in json.loads((ROOT/'t13_remaining_seeded_scans_plan_20261021.json').read_text()) if j['job_id'] in missing]
    measured=json.loads((ROOT/'t13_current_measured_events_20261019.json').read_text());byid={r['sample_id']:r for r in measured};configs={}
    for line in (ROOT/'t13_latest_archive_records_20261019.jsonl').open():
        r=json.loads(line)
        if 'config' in r:configs[r['config']['sample_id']]=r
    for job in jobs:
        source=byid[job['endpoints'][0]['sample_id']]
        group=[r for r in measured if r['family']==source['family'] and r['fixed_context_sha256']==source['fixed_context_sha256']]
        job['supplemental_grid']=[dict(theta=r['theta'],sample_id=r['sample_id'],config=configs[r['sample_id']]['config'],source_config_sha256=configs[r['sample_id']]['sha256']) for r in sorted(group,key=lambda r:r['theta'])]
    if len(jobs)!=2:raise ValueError('sparse scan outcomes changed; inspect selection')
    plan=ROOT/'t13_dense_seeded_scans_plan_20261021.json';plan.write_text(json.dumps(jobs))
    directory='/data_cached/wangzijun_p25/liyuhan/t13_dense_seeded_scans_20261021'
    remote_text('p25',"import pathlib\npathlib.Path("+repr(directory)+").mkdir(exist_ok=False)")
    for path,name in [(plan,'plan.json'),(Path('scripts/t13_current_boundary_worker.py'),'worker.py'),(Path('scripts/genesis_seed_bootstrap.py'),'genesis_seed_bootstrap.py')]:
        subprocess.run(['scp','-q',str(path.resolve()),'p25:'+directory+'/'+name],check=True,timeout=120)
    code=r'''
import pathlib,json,subprocess,os,shutil,hashlib
r=pathlib.Path(DIRECTORY);run=r/'run';run.mkdir();old=r.parent/'t13_remaining_seeded_scans_20261021/run';jobs=json.loads((r/'plan.json').read_text());reused=0
for job in jobs:
 target=run/job['job_id'];target.mkdir()
 for folder in (old/job['job_id']).iterdir():
  if folder.is_dir() and (folder/'receipt.json').exists():shutil.copytree(folder,target/folder.name,copy_function=os.link);reused+=1
contract=dict(seed=0,seed_origin='new supplemental seed, not recovered original seed',diagnostic_only=True,formal_nearacc_eligible=False,reused_immutable_probe_folders=reused,full_published_grid=True,plan_sha256=hashlib.sha256((r/'plan.json').read_bytes()).hexdigest())
(run/'source_contract.json').write_text(json.dumps(contract))
pipeline="""import pathlib,subprocess,json,time
r=pathlib.Path(RUN_PARENT);run=r/'run';gpu='1'
while float(subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<18*1024:
 (run/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',gpu=gpu)));time.sleep(20)
(run/'resource_status.json').write_text(json.dumps(dict(status='running_full_published_grid',gpu=gpu)))
code=subprocess.call(['python3',str(r/'worker.py'),'--plan',str(r/'plan.json'),'--root',str(run),'--gpu',gpu,'--original-full-render','--init-seed','0','--seed-bootstrap',str(r/'genesis_seed_bootstrap.py'),'--supplemental-scan'])
(run/'resource_status.json').write_text(json.dumps(dict(status='worker_ended',returncode=code,gpu=gpu)))
""".replace('RUN_PARENT',repr(str(r)))
(r/'pipeline.py').write_text(pipeline)
with (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p25',root=str(run),pipeline_root=str(r),pid=p.pid,gpu=1,seed=0,planned_intervals=len(jobs),diagnostic_only=True,reused_probe_folders=reused)))
'''.replace('DIRECTORY',repr(directory))
    launch=json.loads(remote_text('p25',code,timeout=60));receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
