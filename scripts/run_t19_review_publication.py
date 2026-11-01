"""Ephemeral SSH proxy forwarding for the authorized T19 incremental publication."""
from pathlib import Path
import re
import subprocess
import threading

ROOT=Path(__file__).resolve().parents[2]/'release_72000_active/t19_review_20261029'


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--remote-script',default='publish_t19_review_remote.py');args=parser.parse_args()
    assert re.fullmatch(r'[a-z0-9_]+\.py',args.remote_script)
    p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
        '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',
        '-R','127.0.0.1:0:127.0.0.1:7897','p25',
        '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    match=re.search(rb'Allocated port (\d+)',p.stderr.readline());assert match,'SSH proxy forwarding unavailable'
    def drain():
        with (ROOT/'publish_stderr.log').open('ab') as out:
            for line in iter(p.stderr.readline,b''):out.write(re.sub(rb'https?://\S+',b'[URL]',line));out.flush()
    t=threading.Thread(target=drain,daemon=True);t.start()
    code=("import os,runpy\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\nos.environ['HTTP_PROXY']=os.environ['HTTPS_PROXY']\nrunpy.run_path('/data_cached/wangzijun_p25/t19_review_20261029/%s',run_name='__main__')\n")%(int(match[1]),args.remote_script)
    p.stdin.write(code.encode());p.stdin.close()
    with (ROOT/'publish_live.log').open('ab') as out:
        for line in iter(p.stdout.readline,b''):out.write(line);out.flush();print(line.decode().strip(),flush=True)
    status=p.wait();t.join(2);return status


if __name__=='__main__':raise SystemExit(main())
