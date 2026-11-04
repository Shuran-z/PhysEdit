"""Bounded recovery of this run's completed references, without launching probes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_continue_20261031'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--polls',type=int,default=90)
    parser.add_argument('--interval',type=int,default=120)
    parser.add_argument('--stage-runtime',action='store_true',
        help='Deliver each changed, verified registry to the isolated p25 scoring runtime.')
    args=parser.parse_args()
    WORK.mkdir(exist_ok=True)
    lock=(WORK/'collection_follow.lock').open('a+b');lock.seek(0)
    if os.name=='nt':
        import msvcrt
        if lock.read(1)==b'':lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    pointer=ROOT/'catalog/active_core100_conditions.json'
    frozen_pointer=hashlib.sha256(pointer.read_bytes()).hexdigest()
    state=dict(pid=os.getpid(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        polls=args.polls,interval_s=args.interval,no_simulations_launched=True)
    receipt=WORK/'collection_follow_status.json'
    for iteration in range(args.polls):
        if hashlib.sha256(pointer.read_bytes()).hexdigest()!=frozen_pointer:
            raise RuntimeError('Frozen release pointer changed; collector stopped without changing inputs')
        command=[sys.executable,'-X','utf8','-m','scripts.collect_core100_original_continuation','--completed-probes','--pending-original-only']
        process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=420)
        state.update(iteration=iteration+1,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            collector_exit=process.returncode)
        if process.returncode:
            state.update(status='collection_failed',error=process.stderr[-2500:]);receipt.write_text(json.dumps(state,indent=2),encoding='utf8')
            print(json.dumps(state),flush=True)
        else:
            state.pop('error',None)
            collected=json.loads(process.stdout)
            if collected['changed']:
                result=subprocess.run([sys.executable,'-X','utf8','-m','scripts.build_core100_distance_bindings'],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=180)
                if result.returncode:raise RuntimeError(result.stderr[-2500:])
            from physedit.core100_bindings import load
            registry=load(verify_evidence=True)
            registry_sha=hashlib.sha256((ROOT/'annotation_site/resources/core100_distance_bindings.json').read_bytes()).hexdigest()
            if args.stage_runtime and state.get('delivered_registry_sha256')!=registry_sha:
                try:
                    delivery=subprocess.run([sys.executable,'-X','utf8','-m','scripts.stage_core100_distance_runtime'],
                        cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=1100)
                except subprocess.TimeoutExpired:
                    state['runtime_delivery']=dict(status='delivery_timed_out_retry_next_poll')
                else:
                    state['runtime_delivery']=dict(exit_code=delivery.returncode,
                        status='delivered'if delivery.returncode==0 else'delivery_failed_retry_next_poll')
                    if delivery.returncode:
                        state['runtime_delivery']['error']=delivery.stderr[-1500:]
                    else:
                        state['delivered_registry_sha256']=json.loads(delivery.stdout)['registry_sha256']
            state.update(status='collecting_completed_results',summary=registry['summary'],
                pending=registry.get('original_family_pending',[r['clip_id']for r in registry['cases']if r['status']=='incomplete']),
                numerical_reference_pending=[r['clip_id']for r in registry['cases']if r['status']=='incomplete'],
                original_family_pending=registry.get('original_family_pending',[]),
                blocked=[r for r in collected['outcomes']if 'blocked'in r])
            receipt.write_text(json.dumps(state,indent=2),encoding='utf8');print(json.dumps(state),flush=True)
            if (registry['summary'].get('original_family_incomplete',registry['summary']['incomplete'])==0
                    and(not args.stage_runtime or state.get('delivered_registry_sha256')==registry_sha)):
                state['status']='numerical_reference_bindings_complete';receipt.write_text(json.dumps(state,indent=2),encoding='utf8');return
        if iteration+1<args.polls:time.sleep(max(10,args.interval))
    state['status']='bounded_followup_finished_with_unresolved_cases';receipt.write_text(json.dumps(state,indent=2),encoding='utf8')


if __name__=='__main__':main()
