"""Bounded SSH transport retries, separate from remote data-validation failures."""
import subprocess
import time


class SSHTransportError(RuntimeError):
    pass


def remote_text(host,code,timeout=120,attempts=2,python='python3'):
    last=None
    for attempt in range(attempts):
        try:
            p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',host,python+' -'],input=code.encode(),capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired as exc:last=SSHTransportError(host+': SSH execution timed out after '+str(timeout)+'s')
        else:
            if p.returncode==0:return p.stdout.decode()
            detail=p.stderr.decode(errors='replace')
            if p.returncode!=255:raise RuntimeError(host+': remote validation/execution failed: '+detail[-2000:])
            last=SSHTransportError(host+': '+detail[-1000:])
        if attempt+1<attempts:time.sleep(2)
    raise last
