"""Task-scoped, localhost-only HF transport; credentials stay on p25."""
import contextlib
import json
from pathlib import Path
import socket
import subprocess
import time

from scripts.boundary_ssh import transport_options

PROXY=r'''
import select,socket,socketserver,threading
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  header=b'';self.request.settimeout(20)
  while b'\r\n\r\n'not in header and len(header)<16384:
   part=self.request.recv(4096)
   if not part:return
   header+=part
  method,target,_=header.split(b'\r\n',1)[0].decode().split()
  host,port=target.rsplit(':',1)
  allowed=host=='huggingface.co'or host.endswith('.huggingface.co')or host.endswith('.hf.co')or host=='hf-hub-lfs-us-east-1.s3-accelerate.amazonaws.com'
  if method!='CONNECT'or port!='443'or not allowed:
   self.request.sendall(b'HTTP/1.1 403 Forbidden\r\n\r\n');return
  upstream=socket.create_connection((host,int(port)),timeout=20)
  try:
   self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
   self.request.settimeout(None);upstream.settimeout(None)
   while True:
    ready,_,_=select.select([self.request,upstream],[],[],90)
    if not ready:return
    for source in ready:
     raw=source.recv(65536)
     if not raw:return
     (upstream if source is self.request else self.request).sendall(raw)
  finally:upstream.close()
class Server(socketserver.ThreadingTCPServer):
 daemon_threads=True
 allow_reuse_address=True
server=Server(('127.0.0.1',17976),Handler)
timer=threading.Timer(1200,server.shutdown);timer.daemon=True;timer.start()
print('HF transport listening',flush=True)
server.serve_forever(poll_interval=.5)
'''


@contextlib.contextmanager
def hf_transport(work, ports=(17976,17977,17978)):
    work=Path(work);log=(work/'hf_transport.log').open('ab');processes=[]
    gateway_port,local_port,reverse_port=ports
    try:
        sg=['ssh','-i','C:/Users/24511/.ssh/id_ed25519_sg88n5','-o','IdentitiesOnly=yes',
            '-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes',
            '-L',f'127.0.0.1:{local_port}:127.0.0.1:{gateway_port}','yangkaiyuan@172.25.72.115','python3 -']
        process=subprocess.Popen(sg,stdin=subprocess.PIPE,stdout=log,stderr=log)
        processes.append(process);process.stdin.write(PROXY.replace('17976',str(gateway_port)).encode());process.stdin.close()
        for _ in range(40):
            if process.poll()is not None:raise RuntimeError('HF_gateway_start_failed')
            try:
                with socket.create_connection(('127.0.0.1',local_port),timeout=.2):break
            except OSError:time.sleep(.25)
        else:raise RuntimeError('HF_gateway_listener_timeout')
        command=['ssh',*transport_options('p25'),'-o','BatchMode=yes','-o','ConnectTimeout=10',
            '-o','ExitOnForwardFailure=yes','-R',f'127.0.0.1:{reverse_port}:127.0.0.1:{local_port}','-N','p25']
        reverse=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log);processes.append(reverse)
        time.sleep(2)
        if reverse.poll()is not None:raise RuntimeError('HF_reverse_forward_failed')
        yield f'http://127.0.0.1:{reverse_port}'
    finally:
        for process in reversed(processes):
            if process.poll()is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
        (work/'HF_TRANSPORT_RECEIPT.json').write_text(json.dumps(dict(
            task_processes=[p.pid for p in processes],all_local_ssh_helpers_exited=all(p.poll()is not None for p in processes),
            remote_proxy_maximum_lifetime_s=1200,credentials_remained_on_p25=True,TLS_verification_disabled=False),indent=2))
