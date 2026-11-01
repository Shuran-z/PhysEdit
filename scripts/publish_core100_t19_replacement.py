"""Publish through the existing local proxy; credentials remain on p25."""
import json
from pathlib import Path
import re
import subprocess
import threading


def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'review/core100_t19_replacement_20261031'
    remote='/data2/liyuhan/core100_t19_replacement_20261031'
    subprocess.run(['scp','-q',str(root/'scripts/publish_core100_t19_replacement_remote.py'),'p25:'+remote+'/'],check=True)
    p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
        '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',
        '-R','127.0.0.1:0:127.0.0.1:7897','p25',
        '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    line=p.stderr.readline();match=re.search(rb'Allocated port (\d+)',line)
    if not match:
        p.terminate()
        raise RuntimeError('proxy_forward_failed')
    def drain():
        with(folder/'publication_transport.log').open('ab')as log:
            for line in iter(p.stderr.readline,b''):
                log.write(re.sub(rb'https?://\S+',b'[URL_REDACTED]',line));log.flush()
    thread=threading.Thread(target=drain,daemon=True);thread.start()
    code=("import os,runpy,sys\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n"
          "os.environ['HTTP_PROXY']=os.environ['HTTPS_PROXY']\n"
          "sys.argv=['publish.py','--root',%r]\nrunpy.run_path(%r,run_name='__main__')\n") % (
          int(match[1]),remote,remote+'/publish_core100_t19_replacement_remote.py')
    p.stdin.write(code.encode());p.stdin.close()
    with(folder/'publication.log').open('ab')as log:
        for line in iter(p.stdout.readline,b''):
            log.write(line);log.flush();print(line.decode().strip(),flush=True)
    result=p.wait();thread.join(2)
    if result:raise SystemExit(result)
    subprocess.run(['scp','-q','p25:'+remote+'/PUBLISHED.json',str(folder/'PUBLISHED.json')],check=True)


if __name__=='__main__':main()
