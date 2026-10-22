"""Resume the memory-blocked shared-volume T11 queue on p26, with provenance."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t11_archive_queue_relocation_20261021.json'
    if marker.exists():raise RuntimeError('archive queue relocation already performed')
    name='t11_original_p29_boundary_launch_20261020.json';launch=json.loads((ROOT/name).read_text())
    destination_python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
    code=r'''
import pathlib,json,os,hashlib
l=LAUNCH;r=pathlib.Path(l['root']);p=pathlib.Path('/proc')/str(l['pid'])
if json.loads((r/'resource_status.json').read_text())['status']!='waiting_for_memory':raise ValueError('queue is not idle')
if not p.exists() or str(r).encode() not in (p/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned queue identity changed')
if (p/'task'/str(l['pid'])/'children').read_text().strip():raise ValueError('queue has active children')
argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x]
paths=[pathlib.Path(argv[0]),pathlib.Path(argv[1]),pathlib.Path(argv[argv.index('--plan')+1]),pathlib.Path(l['renderer_bootstrap'])]
print(json.dumps(dict(argv=argv,hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})))
'''.replace('LAUNCH',repr(launch))
    original=json.loads(remote_text(launch['host'],code,python=launch['python']))
    original['hashes'].pop(original['argv'][0])
    code=r'''
import pathlib,hashlib,subprocess
for name,h in HASHES.items():
 if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()!=h:raise ValueError('shared-volume source mismatch')
free=float(subprocess.check_output(['nvidia-smi','-i','2','--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())
if free<12*1024:raise ValueError('destination GPU2 has insufficient headroom')
print('destination verified')
'''.replace('HASHES',repr(original['hashes']))
    remote_text('p26',code,timeout=60,python=destination_python)
    stop="import pathlib,os,signal\np=pathlib.Path('/proc')/str("+str(launch['pid'])+")\nassert p.exists() and "+repr(launch['root'])+".encode() in (p/'cmdline').read_bytes() and os.getpgid("+str(launch['pid'])+")=="+str(launch['pid'])+"\nos.killpg("+str(launch['pid'])+",signal.SIGTERM)"
    code=r'''
import pathlib,json,subprocess,os
l=LAUNCH;args=ARGS;runtime=DESTINATION_RUNTIME;args[args.index('--gpu')+1]='2';args[0]=runtime;args[args.index('--python')+1]=runtime;r=pathlib.Path(l['root']);env=dict(os.environ,**l['graphics_environment'])
env.update(PYTHONUNBUFFERED='1',PYTHONFAULTHANDLER='1')
env['LD_LIBRARY_PATH']=runtime.rsplit('/bin/python',1)[0]+'/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib'
env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+name for name in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
with (r/'p26_relocation_worker.log').open('w') as log:p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
result=dict(l,host='p26',pid=p.pid,gpu=2,python=runtime,controller_python=runtime,previous_python=l['python'],previous_execution_host=l['host'],previous_pid=l['pid'],relocation_scope='same shared-volume code, plan and cached probes; explicitly changed host and interpreter to verified p26 runtime')
(r/'p26_relocation_receipt_20261021.json').write_text(json.dumps(result));(r/'resource_status.json').write_text(json.dumps(dict(status='running_after_host_relocation',gpu=2)))
print(json.dumps(result))
'''.replace('LAUNCH',repr(launch)).replace('ARGS',repr(original['argv'])).replace('DESTINATION_RUNTIME',repr(destination_python))
    compile(code,'destination_launch','exec')
    remote_text(launch['host'],stop,python=launch['python'])
    result=json.loads(remote_text('p26',code,timeout=60,python=destination_python));(ROOT/name).write_text(json.dumps(result,indent=2));marker.write_text(json.dumps(dict(before=launch,after=result),indent=2));print(json.dumps(dict(host='p26',pid=result['pid'],gpu=2)))


if __name__=='__main__':main()
