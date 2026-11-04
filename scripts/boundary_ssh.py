"""Bounded SSH transport retries, separate from remote data-validation failures."""
import subprocess
import time
import json
from pathlib import Path


class SSHTransportError(RuntimeError):
    pass


def transport_options(host, *, route_path=None, connector=None):
    """Use a bounded per-workspace route; never change the user's SSH config."""
    route_path=Path(route_path or Path(__file__).resolve().parents[1]/
        'review/core100_continue_20261031/ssh_http_proxy.json')
    connector=Path(connector or 'C:/Program Files/Git/mingw64/bin/connect.exe')
    if not route_path.exists():return []
    route=json.loads(route_path.read_text(encoding='utf8'))
    if host not in route.get('hosts',[]) or time.time()>=route.get('expires_at',0):return []
    if route.get('transport')=='sg88_jump':
        if route.get('endpoint')!='yangkaiyuan@172.25.72.115:22':
            raise ValueError('unsupported_boundary_jump_endpoint')
        key=Path('C:/Users/24511/.ssh/id_ed25519_sg88n5')
        if not key.exists():raise ValueError('boundary_jump_key_unavailable')
        return ['-o','ProxyCommand=ssh -i '+key.as_posix()+
                ' -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -W %h:%p yangkaiyuan@172.25.72.115']
    if route.get('endpoint')!='127.0.0.1:7897':
        raise ValueError('unsupported_boundary_proxy_endpoint')
    if not connector.exists():return []
    return ['-o','ProxyCommand="'+connector.as_posix()+'" -H 127.0.0.1:7897 %h %p']


def remote_text(host,code,timeout=120,attempts=2,python='python3'):
    last=None
    for attempt in range(attempts):
        try:
            p=subprocess.run(['ssh',*transport_options(host),'-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',host,python+' -'],input=code.encode(),capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired as exc:last=SSHTransportError(host+': SSH execution timed out after '+str(timeout)+'s')
        else:
            if p.returncode==0:return p.stdout.decode()
            detail=p.stderr.decode(errors='replace')
            if p.returncode!=255:raise RuntimeError(host+': remote validation/execution failed: '+detail[-2000:])
            last=SSHTransportError(host+': '+detail[-1000:])
        if attempt+1<attempts:time.sleep(2)
    raise last
