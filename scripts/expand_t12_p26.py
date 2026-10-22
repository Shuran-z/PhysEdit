"""Expand T12 to six disjoint queues after cross-host source-member checks."""
import json,subprocess
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def assign_remaining(jobs,completed,pinned):
    ids={j['job_id'] for j in jobs};owners={key:int(i) for i,values in pinned.items() for key in values};assigned=[k for values in pinned.values() for k in values if k not in completed]
    if len(ids)!=len(jobs) or not completed<=ids or len(assigned)!=len(set(assigned)) or not set(assigned)<=ids:raise ValueError('job identities or cached owners conflict')
    queues=[[] for _ in range(6)];loads=[0]*6
    for job in jobs:
        if job['job_id'] in completed:continue
        i=owners.get(job['job_id'])
        if i is not None:queues[i].append(job);loads[i]+=len(job['grid'])
    for job in jobs:
        if job['job_id'] in completed or job['job_id'] in owners:continue
        i=min(range(6),key=lambda k:loads[k]);queues[i].append(job);loads[i]+=len(job['grid'])
    return queues


def main():
    marker=ROOT/'t12_p26_expansion_20261022.json'
    if marker.exists():raise RuntimeError('expansion already recorded')
    canaries=json.loads((ROOT/'t12_p26_source_canary_launch_20261022.json').read_text())
    code=r'''
import pathlib,json,gzip,hashlib
out=[]
for l in CANARIES:
 root=pathlib.Path(l['root']);job=json.loads(pathlib.Path(l['active_plan']).read_text())[0];members={m['theta']:m for m in job['members']};checks=[]
 for p in root.glob('*/*/receipt.json'):
  v=json.loads(p.read_text());raw=pathlib.Path(v['state_path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=v['stored_state_sha256'] or hashlib.sha256(gzip.decompress(raw)).hexdigest()!=v['state_sha256'] or hashlib.sha256((p.parent/'config.json').read_bytes()).hexdigest()!=v['config_sha256']:raise ValueError('canary bytes changed')
  if members[v['theta']]['reference_label']!=v['label']:raise ValueError('source-member event not reproduced')
  checks.append(dict(theta=v['theta'],label=v['label'],state_sha256=v['state_sha256']))
 if not checks:raise ValueError('source-member canary pending')
 out.append(dict(axis=job['axis'],checks=checks))
print(json.dumps(out))
'''.replace('CANARIES',repr(canaries))
    checked=json.loads(remote_text('p26',code,timeout=60));old=json.loads((ROOT/'t12_remaining_grid_launch_20261022.json').read_text())
    if len(old)!=2 or any(l['host']!='p25' for l in old):raise ValueError('old queue layout changed')
    code=r'''
import pathlib,json,os,signal,subprocess,time
ls=LAUNCHES;parent=pathlib.Path(ls[0]['root']).parent;snapshot=parent/'p26_expansion_source_snapshot.json'
if snapshot.exists():print(snapshot.read_text());raise SystemExit
for l in ls:
 p=pathlib.Path('/proc')/str(l['pid'])
 if not p.exists() or l['root'].encode() not in (p/'cmdline').read_bytes() or os.getpgid(l['pid'])!=l['pid']:raise ValueError('owned T12 worker identity changed')
for l in ls:os.killpg(l['pid'],signal.SIGTERM)
for l in ls:
 for _ in range(100):
  if not subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout:break
  time.sleep(.1)
 else:raise RuntimeError('owned group did not exit')
completed=set();pinned={}
for i,l in enumerate(ls):
 root=pathlib.Path(l['root']);p=root/'status.json'
 if p.exists():(root/'status_before_p26_expansion_20261022.json').write_bytes(p.read_bytes())
 completed.update(p.parent.name for p in root.glob('*/result.json') if json.loads(p.read_text())['status']=='remaining_grid_completed')
 pinned[str(i)]=[p.name for p in root.iterdir() if p.is_dir() and list(p.glob('*/config.json'))]
result=dict(completed=sorted(completed),pinned=pinned,previous_launches=ls);snapshot.write_text(json.dumps(result));print(json.dumps(result))
'''.replace('LAUNCHES',repr(old))
    frozen=json.loads(remote_text('p25',code,timeout=60));jobs=json.loads((ROOT/'t12_remaining_grid_plan_20261022.json').read_text());queues=assign_remaining(jobs,set(frozen['completed']),frozen['pinned'])
    directory=str(Path(canaries[0]['root']).parent).replace('\\','/');old_directory=str(Path(old[0]['root']).parent).replace('\\','/')
    for i,queue in enumerate(queues):
        p=ROOT/f't12_expanded_{i}_plan_20261022.json';p.write_text(json.dumps(queue));host='p25' if i<2 else 'p26';dest=old_directory if i<2 else directory
        subprocess.run(['scp','-q',str(p.resolve()),host+':'+dest+f'/expanded_plan_{i}.json'],check=True,timeout=120)
    launches=[]
    for host,indices in [('p25',[0,1]),('p26',[2,3,4,5])]:
        code=r'''
import pathlib,json,subprocess,os,hashlib
out=[];host=HOST;old=OLD
for i in INDICES:
 if host=='p25':
  root=pathlib.Path(old[i]['root']);directory=root.parent;source=old[i]['source'];gpu=old[i]['gpu'];python='python3';env=dict(os.environ)
 else:
  directory=pathlib.Path(DIRECTORY);root=directory/('official_run_'+str(i));root.mkdir(exist_ok=False);source='/home/wangzijun_p25/t12_dualsim_v3_20261011/genesis_deploy/source';gpu={2:0,3:1,4:3,5:4}[i];runtime='/home/wangzijun_p25/miniconda3/envs/genesis';python=runtime+'/bin/python'
  env=dict(os.environ,GENESIS_DISABLE_CV2='1',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',LD_LIBRARY_PATH=runtime+'/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib')
  env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
 plan=directory/('expanded_plan_'+str(i)+'.json')
 with (root/'expanded_worker.log').open('w') as log:p=subprocess.Popen([python,str(directory/'t12_remaining_grid_worker.py'),'--plan',str(plan),'--root',str(root),'--source',source,'--gpu',str(gpu)],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 out.append(dict(host=host,root=str(root),pid=p.pid,gpu=gpu,source=source,planned_contexts=len(json.loads(plan.read_text())),backend_sha256=hashlib.sha256((pathlib.Path(source)/'12_render_motion_sequence.py').read_bytes()).hexdigest(),active_plan=str(plan),active_plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),worker_sha256=hashlib.sha256((directory/'t12_remaining_grid_worker.py').read_bytes()).hexdigest()))
print(json.dumps(out))
'''.replace('HOST',repr(host)).replace('OLD',repr(old)).replace('INDICES',repr(indices)).replace('DIRECTORY',repr(directory))
        launches.extend(json.loads(remote_text(host,code,timeout=60)))
    for i,l in enumerate(launches):
        name=f't12_remaining_grid_{i}_launch_20261022.json' if i<2 else f't12_remaining_grid_p26_{i-2}_launch_20261022.json';(ROOT/name).write_text(json.dumps(l,indent=2))
    (ROOT/'t12_remaining_grid_launch_20261022.json').write_text(json.dumps(launches,indent=2));marker.write_text(json.dumps(dict(launches=launches,source_snapshot=frozen,canary_checks=checked),indent=2))
    print(json.dumps(dict(completed_before_expansion=len(frozen['completed']),pending_assigned=sum(map(len,queues)),queue_counts=list(map(len,queues)))))


if __name__=='__main__':main()
