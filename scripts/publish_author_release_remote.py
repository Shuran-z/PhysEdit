"""Keep SSH proxy forwarding alive and drain upload logs without pipe deadlocks."""
from pathlib import Path
import re
import subprocess
import threading

out = Path(__file__).resolve().parents[2] / 'release_72000_active'
process = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
    '-R', '127.0.0.1:0:127.0.0.1:7897', 'p25',
    '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
match = re.search(rb'Allocated port (\d+)', process.stderr.readline())
assert match, 'SSH proxy forwarding unavailable'
def drain_errors():
    with (out / 'upload_stderr_v2.log').open('ab') as stream:
        for chunk in iter(process.stderr.readline, b''):
            stream.write(re.sub(rb'https?://\S+', b'[URL_REDACTED]', chunk))
            stream.flush()
thread = threading.Thread(target=drain_errors, daemon=True)
thread.start()
code = ("import os,runpy\nos.environ['HTTPS_PROXY']='http://127.0.0.1:%d'\n"
        "os.environ['HTTP_PROXY']=os.environ['HTTPS_PROXY']\n"
        "runpy.run_path('/data_cached/wangzijun_p25/author_release_20261029/upload.py',run_name='__main__')\n") % int(match[1])
process.stdin.write(code.encode())
process.stdin.close()
with (out / 'upload_live.log').open('ab') as stream:
    for line in iter(process.stdout.readline, b''):
        stream.write(line)
        stream.flush()
        print(line.decode().strip(), flush=True)
code = process.wait()
thread.join(2)
raise SystemExit(code)
