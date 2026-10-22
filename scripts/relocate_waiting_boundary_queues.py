"""Move only owned, idle memory-waiting queues to GPUs with free headroom."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'waiting_queue_relocation_20261021.json'
    if receipt.exists():raise RuntimeError('relocation already performed')
    specs=[('t13_dense_seeded_scans_launch_20261021.json',0),('five_scene_timeout_retry_launch_20261021.json',0),('t18_legacy_search_launch_20261020.json',5)]
    launches={name:dict(json.loads((ROOT/name).read_text()),destination_gpu=gpu) for name,gpu in specs}
    code=r'''
import pathlib,json,os,signal,subprocess,time,hashlib
out={}
for name,l in LAUNCHES.items():
 r=pathlib.Path(l['root']);resource=json.loads((r/'resource_status.json').read_text());pid=l['pid'];proc=pathlib.Path('/proc')/str(pid);scope=l.get('pipeline_root',str(r.parent))
 event_file=r/'gpu_relocation_20261021.json'
 if event_file.exists():
  event=json.loads(event_file.read_text());active=pathlib.Path('/proc')/str(event['new_pid'])/'cmdline'
  if event['previous_pid']!=pid or not active.exists() or scope.encode() not in active.read_bytes():raise ValueError('prior relocation identity changed')
  result={k:v for k,v in l.items() if k!='destination_gpu'};result.update(pid=event['new_pid'],gpu=event['new_gpu'],gpu_relocations=l.get('gpu_relocations',[])+[event]);out[name]=result;continue
 if resource['status']!='waiting_for_memory':raise ValueError('queue is no longer idle: '+name)
 if not proc.exists() or scope.encode() not in (proc/'cmdline').read_bytes() or os.getpgid(pid)!=pid:raise ValueError('owned waiting queue identity changed')
 children=(proc/'task'/str(pid)/'children').read_text().split()
 if children:raise ValueError('waiting queue has active children; retry later: '+name)
 argv=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s];gpu=l['destination_gpu']
 free=float(subprocess.check_output(['nvidia-smi','-i',str(gpu),'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())
 minimum=18*1024 if 't13_dense' in name else 12*1024
 if free<minimum:raise ValueError('destination lacks required headroom: '+name)
 if '--gpu' in argv:argv[argv.index('--gpu')+1]=str(gpu)
 else:
  pipeline=pathlib.Path(scope)/'pipeline.py';text=pipeline.read_text();pattern="gpu='"+str(l['gpu'])+"'"
  if text.count(pattern)!=1:raise ValueError('unexpected GPU declaration')
  (pipeline.parent/'pipeline_before_gpu_relocation_20261021.py').write_text(text)
  pipeline.write_text(text.replace(pattern,"gpu='"+str(gpu)+"'"))
 os.killpg(pid,signal.SIGTERM)
 for _ in range(50):
  if not subprocess.run(['pgrep','-g',str(pid)],capture_output=True).stdout:break
  time.sleep(.2)
 else:raise ValueError('owned process group did not exit')
 with (r/'gpu_relocation_worker.log').open('w') as log:p=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 event=dict(previous_pid=pid,new_pid=p.pid,previous_gpu=l['gpu'],new_gpu=gpu,reason='idle GPU memory wait; source physics and completed receipts unchanged')
 result={k:v for k,v in l.items() if k!='destination_gpu'};result.update(pid=p.pid,gpu=gpu,gpu_relocations=l.get('gpu_relocations',[])+[event]);out[name]=result
 (r/'gpu_relocation_20261021.json').write_text(json.dumps(event))
 (r/'resource_status.json').write_text(json.dumps(dict(status='running_after_gpu_relocation',gpu=gpu,pid=p.pid)))
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches))
    relocated=json.loads(remote_text('p25',code,timeout=60))
    for name,l in relocated.items():(ROOT/name).write_text(json.dumps(l,indent=2))
    receipt.write_text(json.dumps(relocated,indent=2));print(json.dumps({name:dict(pid=l['pid'],gpu=l['gpu']) for name,l in relocated.items()}))


if __name__=='__main__':main()
