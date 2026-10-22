"""Restart legacy shards using their supported CLI and unchanged hashed code."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'legacy_scene_queue_repair_20261022.json'
    if marker.exists():raise RuntimeError('queue repair already recorded')
    launches={f'five_scene_parallel_{i}_launch_20261021.json':json.loads((ROOT/f'five_scene_parallel_{i}_launch_20261021.json').read_text()) for i in [2,3]}
    code=r'''
import pathlib,json,hashlib,os,signal,time,subprocess
out={};requests=[]
for name,l in LAUNCHES.items():
 root=pathlib.Path(l['root']);worker=root.parent/'five_scene_boundary_worker.py';plan=root.parent/'plan.json';proc=pathlib.Path('/proc')/str(l['pid'])
 help_result=subprocess.run(['python3',str(worker),'--help'],capture_output=True)
 if help_result.returncode:raise ValueError('legacy worker preflight failed')
 if '--minimum-free-memory-mib' in help_result.stdout.decode():raise ValueError('worker version changed; inspect supported runtime options')
 samples=list(root.glob('*/*/receipt.json'))
 if not samples:raise ValueError('missing cached execution provenance')
 sources=json.loads(samples[0].read_text())['execution_sources']
 if any(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=v for p,v in sources.items()):raise ValueError('hashed legacy source changed')
 alive=proc.exists()
 if alive:
  if str(root.parent).encode() not in (proc/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned legacy worker identity changed')
  if (proc/'task'/str(l['pid'])/'children').read_text().strip():raise ValueError('legacy worker is active; do not interrupt')
  resource=json.loads((root/'resource_status.json').read_text())
  if resource.get('status')!='waiting_for_memory':raise ValueError('legacy worker is no longer idle')
 free=float(subprocess.check_output(['nvidia-smi','-i','5','--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())
 if free<12288:raise ValueError('GPU5 lacks legacy 12GiB headroom')
 requests.append((name,l,root,worker,plan,alive))
for name,l,root,worker,plan,alive in requests:
 (root/'status_before_queue_repair_20261022.json').write_bytes((root/'status.json').read_bytes())
 if alive:
  os.killpg(l['pid'],signal.SIGTERM)
  for _ in range(100):
   if not subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout:break
   time.sleep(.1)
  else:raise RuntimeError('owned idle legacy group did not stop')
 argv=['python3',str(worker),'--plan',str(plan),'--root',str(root),'--gpu','5']
 with (root/'supported_cli_resume_20261022.log').open('w') as log:p=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 result=dict(l,previous_pid=l['pid'],pid=p.pid,previous_gpu=l['gpu'],gpu=5,minimum_free_memory_mib=12288,actual_command=argv,
  repair='unchanged legacy code and cached provenance; unsupported option removed; GPU5 headroom',worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest())
 out[name]=result
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches))
    result=json.loads(remote_text('p25',code,timeout=60))
    for name,l in result.items():(ROOT/name).write_text(json.dumps(l,indent=2))
    marker.write_text(json.dumps(result,indent=2));print(json.dumps({n:dict(pid=l['pid'],gpu=l['gpu']) for n,l in result.items()}))


if __name__=='__main__':main()
