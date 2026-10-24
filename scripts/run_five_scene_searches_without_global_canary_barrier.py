"""Use the same worker's per-job source checks without a batch-wide barrier."""
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    names=['five_scene_own_seed_'+str(i)+'_launch_20261023.json' for i in range(2)]
    launches={n:json.loads((ROOT/n).read_text()) for n in names}
    code=r'''
import pathlib,json,os,signal,subprocess,time,hashlib
out={};python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
for name,l in LAUNCHES.items():
 b=pathlib.Path(l['pipeline_root']);root=pathlib.Path(l['root']);marker=root/'per_job_validation_launch_20261024.json'
 if marker.exists():out[name]=json.loads(marker.read_text());continue
 proc=pathlib.Path('/proc')/str(l['pid'])
 if not proc.exists() or str(b/'conditional_family_pipeline.py').encode() not in (proc/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned pipeline identity changed')
 if hashlib.sha256(pathlib.Path(l['plan']).read_bytes()).hexdigest()!=l['plan_sha256']:raise ValueError('original plan changed')
 for j in json.loads(pathlib.Path(l['plan']).read_text()):
  for p,d in j['backend_sources'].items():
   if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=d:raise ValueError('frozen source changed')
 env=dict(v.decode().split('=',1) for v in (proc/'environ').read_bytes().split(b'\0') if v)
 os.killpg(l['pid'],signal.SIGTERM)
 for _ in range(100):
  lines=subprocess.check_output(['ps','-eo','pgid=,stat=']).decode().splitlines()
  if not any(int(v.split()[0])==l['pid'] and not v.split()[1].startswith('Z') for v in lines if v.strip()):break
  time.sleep(.1)
 else:raise ValueError('owned compute group did not exit')
 with (b/'per_job_validation_worker.log').open('a') as log:p=subprocess.Popen([python,str(b/'conditional_family_search.py'),'--plan',l['plan'],'--root',str(root),'--gpu','auto','--python',python],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 result=dict(l,pid=p.pid,previous_pipeline_pid=l['pid'],validation='each job must reproduce its own source event before scanning; no batch-wide barrier')
 marker.write_text(json.dumps(result));(root/'pipeline_phase.json').write_text(json.dumps(dict(status='conditional_searches',active_jobs=l['planned_jobs'],blocked_families=[],validation='per-job source event check')));out[name]=result
print(json.dumps(out))
'''.replace('LAUNCHES',repr(launches))
    result=json.loads(remote_text('p25',code,timeout=90,python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))
    for n,l in result.items():(ROOT/n).write_text(json.dumps(l,indent=2))
    marker=ROOT/'conditional_family_launches_20261023.json';old=json.loads(marker.read_text());updates={l['root']:l for l in result.values()};marker.write_text(json.dumps([updates.get(l['root'],l) for l in old],indent=2))
    print(json.dumps({n:l['pid'] for n,l in result.items()}))


if __name__=='__main__':main()
