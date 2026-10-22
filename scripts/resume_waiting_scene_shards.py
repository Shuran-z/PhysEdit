"""Resume owned idle shards with 8GiB headroom; never terminate resident jobs."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'scene_shard_memory_resume_20261021.json'
    if marker.exists():raise RuntimeError('shard memory adjustment already performed')
    launches={name:json.loads((ROOT/name).read_text()) for name in ['five_scene_parallel_'+str(i)+'_launch_20261021.json' for i in range(4)]}
    code=r'''
import pathlib,json,os,signal,subprocess,time
out={}
for name,l in LAUNCHES.items():
 r=pathlib.Path(l['root']);resource=json.loads((r/'resource_status.json').read_text()) if (r/'resource_status.json').exists() else {}
 if resource.get('status')!='waiting_for_memory':continue
 p=pathlib.Path('/proc')/str(l['pid']);scope=l['pipeline_root']
 if not p.exists() or scope.encode() not in (p/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned shard identity changed')
 if (p/'task'/str(l['pid'])/'children').read_text().strip():continue
 free=float(subprocess.check_output(['nvidia-smi','-i',str(l['gpu']),'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())
 if free<8192:continue
 args=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
 if '--minimum-free-memory-mib' in args:args[args.index('--minimum-free-memory-mib')+1]='8192'
 else:args+=['--minimum-free-memory-mib','8192']
 (r/'status_before_memory_resume_20261021.json').write_bytes((r/'status.json').read_bytes())
 os.killpg(l['pid'],signal.SIGTERM)
 for _ in range(50):
  if not subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout:break
  time.sleep(.2)
 else:raise ValueError('owned shard did not exit')
 with (r/'memory_resume_worker.log').open('w') as log:p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 result=dict(l,pid=p.pid,previous_pid=l['pid'],minimum_free_memory_mib=8192,resource_change='8GiB free headroom; physical configuration and cached probes unchanged')
 (r/'memory_resume_launch_20261021.json').write_text(json.dumps(result));out[name]=result
 (r/'resource_status.json').write_text(json.dumps(dict(status='running_after_memory_resume',gpu=l['gpu'],minimum_free_memory_mib=8192)))
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches))
    resumed=json.loads(remote_text('p25',code,timeout=60))
    for name,l in resumed.items():(ROOT/name).write_text(json.dumps(l,indent=2))
    marker.write_text(json.dumps(resumed,indent=2));print(json.dumps({n:dict(pid=l['pid'],gpu=l['gpu']) for n,l in resumed.items()}))


if __name__=='__main__':main()
