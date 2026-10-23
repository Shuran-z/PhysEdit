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
from concurrent.futures import ThreadPoolExecutor, as_completed
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT

TARGETS={
 't11_p29_original_runtime_retry_launch_20261022.json':'scripts.register_five_scene_refinements',
 't07_B_E4_search_launch_20261022.json':'scripts.register_t07_position_contact',
 't13_dense_seeded_scans_launch_20261021.json':'scripts.collect_boundary_replay_diagnostics',
 'five_scene_timeout_retry_launch_20261021.json':'scripts.register_five_scene_refinements',
 't13_remaining_seeded_scans_launch_20261021.json':'scripts.collect_boundary_replay_diagnostics',
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
TARGETS.update({'five_scene_parallel_'+str(i)+'_launch_20261021.json':'scripts.register_five_scene_refinements' for i in range(4)})
TARGETS.update({'t18_parallel_'+str(i)+'_launch_20261022.json':'scripts.register_t18_table_contact_distances' for i in range(4)})
TARGETS.update({'t12_remaining_grid_'+str(i)+'_launch_20261022.json':'scripts.register_t12_remaining_grid' for i in range(2)})
TARGETS.update({'t12_remaining_grid_p26_'+str(i)+'_launch_20261022.json':'scripts.register_t12_remaining_grid' for i in range(4)})


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
    cache={};errors=[];last_statuses={};post_pending=False;deadline=time.monotonic()+args.hours*3600
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
 files=[root/'status.json',root/'results.json',root/'resource_status.json',pathlib.Path(scope)/'queue_status.json']
 if launch.get('canary_root'):files.append(pathlib.Path(launch['canary_root'])/'status.json')
 for repetition in launch.get('repeat_roots',[]):files.append(pathlib.Path(repetition)/'status.json')
 fingerprint=hashlib.sha256(b''.join(p.read_bytes() for p in files if p.exists())).hexdigest()
 rows.append(dict(name=name,running=running,fingerprint=fingerprint))
print(json.dumps(rows))
'''.replace('LAUNCHES',repr(launches))
        try:
            statuses=[];unreachable=[]
            for host in sorted({v.get('host','p25') for v in launches.values()}):
                subset={k:v for k,v in launches.items() if v.get('host','p25')==host}
                code=remote.replace(repr(launches),repr(subset))
                try:
                    rows=json.loads(remote_text(host,code,timeout=60))
                    statuses.extend(rows)
                    last_statuses.update({r['name']:r for r in rows})
                except Exception as exc:
                    unreachable.append(host);errors.append(dict(host=host,error=str(exc),time=time.time()))
                    statuses.extend(dict(last_statuses.get(name,dict(name=name,fingerprint=None)),running=None,unreachable=True) for name in subset)
            changed=[r for r in statuses if not r.get('unreachable') and cache.get(r['name'])!=r['fingerprint']]
            modules=sorted({TARGETS[r['name']] for r in changed})
            succeeded=set()
            def run(module):
                with (root/(module.split('.')[-1]+'.log')).open('a',encoding='utf-8') as log:
                    result=subprocess.run([sys.executable,'-X','utf8','-m',module],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                if result.returncode:raise RuntimeError(module+' failed; retained previous output, inspect its log')
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures={executor.submit(run,module):module for module in modules}
                for future in as_completed(futures):
                    module=futures[future]
                    try:future.result();succeeded.add(module)
                    except Exception as exc:errors.append(dict(module=module,error=str(exc),time=time.time()))
            post_failed=False
            if succeeded or post_pending:
                for module in ['scripts.combine_recovered_boundary_distances','scripts.snapshot_boundary_completion','scripts.write_all20_boundary_progress']:
                    try:run(module)
                    except Exception as exc:
                        post_failed=True;errors.append(dict(module=module,error=str(exc),time=time.time()))
            post_pending=post_failed
            for r in changed:
                if TARGETS[r['name']] in succeeded:cache[r['name']]=r['fingerprint']
            running=any(r['running'] for r in statuses) or bool(unreachable)
            retry_needed=bool(unreachable) or len(succeeded)<len(modules) or post_failed
            report=dict(status='running' if running else 'binding_retry_pending' if retry_needed else 'listed_jobs_ended_review_results',jobs=statuses,unreachable_hosts=unreachable,errors=errors[-30:],all20_completed=False,updated_at=time.time())
            (root/'status.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(status=report['status'],changed_jobs=len(changed),errors=len(errors))),flush=True)
            if not args.watch or (not running and not retry_needed):break
        except Exception as exc:
            errors.append(dict(error=str(exc),time=time.time()));(root/'status.json').write_text(json.dumps(dict(status='integration_error_retry_pending',errors=errors[-30:],all20_completed=False,updated_at=time.time()),indent=2))
            if not args.watch:raise
        if time.monotonic()>deadline:
            (root/'timeout.json').write_text(json.dumps(dict(status='bounded_runtime_expired',all20_completed=False,errors=errors[-30:]),indent=2));break
        time.sleep(60)


if __name__=='__main__':main()
