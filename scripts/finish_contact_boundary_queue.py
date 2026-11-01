"""Finite queue finalizer: collect every completed case while its workers run."""
import argparse
import json
from pathlib import Path
import time
from collect_contact_boundaries import collect


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True)
    p.add_argument('--maximum-hours',type=float,default=24);a=p.parse_args()
    root=Path(a.root);output=Path(a.output);deadline=time.monotonic()+a.maximum_hours*3600
    import fcntl
    lock=output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        result=collect(root);temp=output.with_suffix('.tmp')
        temp.write_text(json.dumps(result,ensure_ascii=False,indent=2));temp.replace(output)
        if result['completed']==5:return
        statuses=[json.loads(p.read_text()).get('status')for p in root.glob('worker*/resource_status.json')]
        if len(statuses)==2 and all(s=='finished'for s in statuses):
            raise RuntimeError('Workers stopped with unresolved cases; evidence retained')
        if time.monotonic()>=deadline:raise TimeoutError('Finite collector deadline reached; workers and evidence retained')
        time.sleep(30)


if __name__=='__main__':main()
