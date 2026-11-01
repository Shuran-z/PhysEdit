"""Maintain the existing loopback-only HF proxy tunnel without a 72-hour expiry."""
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    root=Path(__file__).resolve().parents[1]/'review/annotation_bugfix_20261028'
    root.mkdir(parents=True,exist_ok=True)
    delay=5
    while True:
        started=time.time()
        command=['ssh','-N','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=20',
                 '-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes',
                 '-R','127.0.0.1:50998:127.0.0.1:7897','tx173']
        with (root/'tunnel.log').open('ab') as log:
            p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            (root/'tunnel_status.json').write_text(json.dumps(dict(pid=os.getpid(),ssh_pid=p.pid,started_at=started,
                bind='127.0.0.1:50998',dependency='desktop local proxy 127.0.0.1:7897')))
            status=p.wait()
        delay=5 if time.time()-started>60 else min(delay*2,60)
        time.sleep(delay)


if __name__=='__main__':main()
