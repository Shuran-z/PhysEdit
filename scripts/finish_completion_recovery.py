"""One-shot continuation after an existing downloader; never auto-admit references.

Waits for the specified Windows process, retries incomplete transport batches,
then runs the implemented state audits and refreshes the progress ledger.
This is a bounded job, not a recurring scheduler.
"""
import argparse,ctypes,json,subprocess,sys,time
from ctypes import wintypes
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wait-pid',type=int,required=True);args=parser.parse_args()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x00100000,False,args.wait_pid)
    if not handle:raise OSError('producer process unavailable; verify it before restarting recovery')
    try:
        deadline=time.monotonic()+6*3600
        while kernel.WaitForSingleObject(handle,0)==258:
            if time.monotonic()>deadline:raise TimeoutError('producer still running after six hours; not interrupted')
            time.sleep(20)
    finally:kernel.CloseHandle(handle)
    def run(module):
        print('Running '+module,flush=True)
        subprocess.run([sys.executable,'-X','utf8','-m',module],check=True)
    # Resume verifies compressed-state hashes and retries failed/missing batches.
    run('scripts.collect_completion_states')
    run('scripts.bind_t04_t05_original_profiles')
    for module in ['scripts.audit_t04_completion_states','scripts.audit_t05_completion_states','scripts.audit_t07_t08_completion_states','scripts.extract_t04_transition_candidates','scripts.extract_t05_transition_candidates','scripts.recover_t12_parameter_slices','scripts.audit_nearacc_readiness','scripts.write_all20_boundary_progress']:
        run(module)
    summary={}
    for scene in ['T04','T05','T01','T07','T08','T11','T12']:
        rows=[r for path in (ROOT/'completion_states').glob(scene+'_*.json') for r in json.loads(path.read_text())]
        summary[scene]=dict(receipt_rows=len(rows),recovered=sum(bool(r.get('local_path')) for r in rows),failed=sum(bool(r.get('error')) for r in rows))
    (ROOT/'completion_recovery_job_summary.json').write_text(json.dumps(dict(scenes=summary,all_scene_boundaries_completed=False,scope='state recovery and implemented event audits only'),indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
