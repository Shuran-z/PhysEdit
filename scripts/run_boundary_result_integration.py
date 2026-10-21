"""One bounded execution pipeline: collect completed jobs and refresh distances.

This process exits when its explicitly listed compute jobs end (or after the
bounded timeout). It does not schedule future tasks or mark all 20 scenes done.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from scripts.export_original_boundary_distances import ROOT

TARGETS={
 't11_p26_full_contract_control_repeat2_launch_20261021.json':'scripts.collect_boundary_replay_diagnostics',
 't11_p26_full_contract_control_launch_20261021.json':'scripts.collect_boundary_replay_diagnostics',
 't13_fixed_seed_control_launch_20261021.json':'scripts.collect_boundary_replay_diagnostics',
 't11_verified_p26_producer_launch_20261020.json':'scripts.register_five_scene_refinements',
 't10_parallel_state_replay_launch_20261020.json':'scripts.collect_supplemental_scan_states',
 't13_remaining_repetitions_launch_20261020.json':'scripts.register_t13_current_searches',
 'five_scene_alternate_seed_launch_20261020.json':'scripts.register_five_scene_refinements',
 't11_production_contract_control_launch_20261020.json':'scripts.collect_boundary_replay_diagnostics',
 't13_unreproduced_control_launch_20261020.json':'scripts.collect_boundary_replay_diagnostics',
 'five_scene_source_replay_launch_20261020.json':'scripts.collect_boundary_replay_diagnostics',
 't18_asset_retry_launch_20261020.json':'scripts.register_t18_table_contact_distances',
 't09_pull_refinement_launch_20261020.json':'scripts.register_t09_pull_refinement',
 'five_scene_boundary_launch_20261020.json':'scripts.register_five_scene_refinements',
 't11_original_p29_boundary_launch_20261020.json':'scripts.register_five_scene_refinements',
 't15_event_tail_refinement_launch_20261020.json':'scripts.register_t15_all_context_distances',
 't14_formal_search_launch_20261019.json':'scripts.register_t14_all_context_distances',
 't12_supplemental_refinement_launch.json':'scripts.register_t12_refined_distances',
 't13_full_search_launch_20261019.json':'scripts.register_t13_current_searches',
 't13_original_full_retry_launch_20261020.json':'scripts.register_t13_current_searches',
 't13_remaining_full_retry_launch_20261020.json':'scripts.register_t13_current_searches',
 't18_table_contact_search_launch_20261020.json':'scripts.register_t18_table_contact_distances',
 't18_legacy_search_launch_20261020.json':'scripts.register_t18_table_contact_distances',
 't09_missing_state_replay_v2_launch_20261020.json':'scripts.collect_supplemental_scan_states',
 't09_missing_state_replay_launch_20261020.json':'scripts.collect_supplemental_scan_states',
 't06_t10_missing_state_replay_launch_20261020.json':'scripts.collect_supplemental_scan_states',
}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');parser.add_argument('--hours',type=float,default=72);args=parser.parse_args()
    root=ROOT/'result_integration_20261020';root.mkdir(exist_ok=True)
    lock=(root/'process.lock').open('a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cache={};errors=[];deadline=time.monotonic()+args.hours*3600
    while True:
        launches={name:json.loads((ROOT/name).read_text(encoding='utf-8-sig')) for name in TARGETS if (ROOT/name).exists() and not (name=='t09_missing_state_replay_launch_20261020.json' and (ROOT/'t09_missing_state_replay_v2_launch_20261020.json').exists())}
        remote=r'''
import pathlib,json,hashlib
rows=[]
for name,launch in LAUNCHES.items():
 root=pathlib.Path(launch['root']);pid=pathlib.Path('/proc')/str(launch['pid'])/'cmdline'
 scope=launch.get('pipeline_root',str(root))
 if 'pipeline_root' not in launch and root.name in ['run','legacy_run','run_v2']:scope=str(root.parent)
 running=pid.exists() and scope.encode() in pid.read_bytes()
 files=[root/'status.json',root/'resource_status.json',pathlib.Path(scope)/'queue_status.json']
 if launch.get('canary_root'):files.append(pathlib.Path(launch['canary_root'])/'status.json')
 for repetition in launch.get('repeat_roots',[]):files.append(pathlib.Path(repetition)/'status.json')
 fingerprint=hashlib.sha256(b''.join(p.read_bytes() for p in files if p.exists())).hexdigest()
 rows.append(dict(name=name,running=running,fingerprint=fingerprint))
print(json.dumps(rows))
'''.replace('LAUNCHES',repr(launches))
        try:
            statuses=[]
            for host in sorted({v.get('host','p25') for v in launches.values()}):
                subset={k:v for k,v in launches.items() if v.get('host','p25')==host}
                code=remote.replace(repr(launches),repr(subset))
                p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',host,'python3 -'],input=code.encode(),capture_output=True,timeout=45)
                if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
                statuses.extend(json.loads(p.stdout))
            changed=[r for r in statuses if cache.get(r['name'])!=r['fingerprint']]
            modules=sorted({TARGETS[r['name']] for r in changed})
            succeeded=set()
            def run(module):
                with (root/(module.split('.')[-1]+'.log')).open('a',encoding='utf-8') as log:
                    result=subprocess.run([sys.executable,'-X','utf8','-m',module],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                if result.returncode:raise RuntimeError(module+' failed; retained previous output, inspect its log')
            for module in modules:
                try:run(module);succeeded.add(module)
                except Exception as exc:errors.append(dict(module=module,error=str(exc),time=time.time()))
            if succeeded:
                for module in ['scripts.combine_recovered_boundary_distances','scripts.snapshot_boundary_completion','scripts.write_all20_boundary_progress']:run(module)
            for r in changed:
                if TARGETS[r['name']] in succeeded:cache[r['name']]=r['fingerprint']
            running=any(r['running'] for r in statuses)
            report=dict(status='running' if running else 'listed_jobs_ended_review_results',jobs=statuses,errors=errors[-30:],all20_completed=False,updated_at=time.time())
            (root/'status.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(status=report['status'],changed_jobs=len(changed),errors=len(errors))),flush=True)
            if not args.watch or not running:break
        except Exception as exc:
            errors.append(dict(error=str(exc),time=time.time()));(root/'status.json').write_text(json.dumps(dict(status='integration_error_retry_pending',errors=errors[-30:],all20_completed=False),indent=2))
            if not args.watch:raise
        if time.monotonic()>deadline:
            (root/'timeout.json').write_text(json.dumps(dict(status='bounded_runtime_expired',all20_completed=False,errors=errors[-30:]),indent=2));break
        time.sleep(60)


if __name__=='__main__':main()
