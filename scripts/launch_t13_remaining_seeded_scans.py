"""Bounded supplemental scans; never overwrite unreproduced published labels."""
import json
from pathlib import Path
import subprocess
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def build_plan():
    completed={r['result']['job_id'] for r in json.loads((ROOT/'t13_current_solver_evidence_20261019.json').read_text())}
    jobs=[j for j in json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()) if j['job_id'] not in completed]
    measured=json.loads((ROOT/'t13_current_measured_events_20261019.json').read_text());by_id={r['sample_id']:r for r in measured}
    configs={}
    for line in (ROOT/'t13_latest_archive_records_20261019.jsonl').open():
        row=json.loads(line)
        if 'config' in row:configs[row['config']['sample_id']]=row
    for job in jobs:
        source=by_id[job['endpoints'][0]['sample_id']]
        group=sorted([r for r in measured if r['family']==source['family'] and r['fixed_context_sha256']==source['fixed_context_sha256']],key=lambda r:r['theta'])
        selected={group[0]['theta'],group[-1]['theta'],group[len(group)//2]['theta'],*job['bracket']}
        points={r['theta']:r for r in group}
        job['supplemental_grid']=[dict(theta=t,sample_id=points[t]['sample_id'],config=configs[points[t]['sample_id']]['config'],source_config_sha256=configs[points[t]['sample_id']]['sha256']) for t in sorted(selected)]
    return jobs


def main():
    receipt=ROOT/'t13_remaining_seeded_scans_launch_20261021.json'
    if receipt.exists():raise RuntimeError('supplemental scans already launched')
    jobs=build_plan()
    if len(jobs)!=8:raise ValueError('remaining published refinement task count changed; inspect before launch')
    local=ROOT/'t13_remaining_seeded_scans_plan_20261021.json';local.write_text(json.dumps(jobs))
    directory='/data_cached/wangzijun_p25/liyuhan/t13_remaining_seeded_scans_20261021'
    remote_text('p25',"import pathlib\npathlib.Path("+repr(directory)+").mkdir(exist_ok=False)")
    for path,name in [(local,'plan.json'),(Path('scripts/t13_current_boundary_worker.py'),'worker.py'),(Path('scripts/genesis_seed_bootstrap.py'),'genesis_seed_bootstrap.py')]:
        subprocess.run(['scp','-q',str(path.resolve()),'p25:'+directory+'/'+name],check=True,timeout=120)
    pipeline=r'''
import pathlib,json,subprocess,time,hashlib
r=pathlib.Path(DIRECTORY);run=r/'run';run.mkdir();gpu='4'
contract=dict(seed=0,seed_origin='new supplemental seed; original seed not recovered',plan_sha256=hashlib.sha256((r/'plan.json').read_bytes()).hexdigest(),diagnostic_only=True,formal_nearacc_eligible=False,scope='published same-context parameter domain, original full renderer')
(run/'source_contract.json').write_text(json.dumps(contract))
while float(subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<18*1024:
 (run/'resource_status.json').write_text(json.dumps(dict(status='waiting_for_memory',gpu=gpu)));time.sleep(20)
(run/'resource_status.json').write_text(json.dumps(dict(status='running',gpu=gpu)))
result=subprocess.run(['python3',str(r/'worker.py'),'--plan',str(r/'plan.json'),'--root',str(run),'--gpu',gpu,'--original-full-render','--init-seed','0','--seed-bootstrap',str(r/'genesis_seed_bootstrap.py'),'--supplemental-scan'])
(run/'resource_status.json').write_text(json.dumps(dict(status='worker_ended',returncode=result.returncode,gpu=gpu)))
'''.replace('DIRECTORY',repr(directory))
    compile(pipeline,'pipeline.py','exec')
    code="import pathlib,subprocess,json\nr=pathlib.Path("+repr(directory)+")\n(r/'pipeline.py').write_text("+repr(pipeline)+")\nwith (r/'pipeline.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'pipeline.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)\nprint(json.dumps(dict(pid=p.pid)))"
    launch=dict(host='p25',root=directory+'/run',pipeline_root=directory,gpu=4,seed=0,planned_intervals=len(jobs),diagnostic_only=True,**json.loads(remote_text('p25',code)))
    receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
