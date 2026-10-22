"""Launch remaining T12 slices on two memory-guarded p25 queues."""
import json,subprocess
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t12_remaining_grid_launch_20261022.json'
    if marker.exists():raise RuntimeError('T12 remaining grid already launched')
    jobs=json.loads((ROOT/'t12_remaining_grid_plan_20261022.json').read_text());directory='/data_cached/wangzijun_p25/liyuhan/t12_remaining_grid_20261022'
    remote_text('p25',"import pathlib\npathlib.Path("+repr(directory)+").mkdir(exist_ok=False)")
    for i in range(2):
        plan=ROOT/('t12_remaining_grid_'+str(i)+'_plan_20261022.json');plan.write_text(json.dumps(jobs[i::2]));subprocess.run(['scp','-q',str(plan.resolve()),'p25:'+directory+'/plan_'+str(i)+'.json'],check=True,timeout=120)
    for n in ['t12_remaining_grid_worker.py','t12_original_boundary_worker.py']:subprocess.run(['scp','-q',str(Path('scripts',n).resolve()),'p25:'+directory+'/'+n],check=True,timeout=60)
    code=r'''
import pathlib,json,subprocess,hashlib
r=pathlib.Path(DIRECTORY);source=r.parent/'t12_original_backend_20261020/source';renderer=source/'12_render_motion_sequence.py'
if not renderer.exists():raise ValueError('original T12 backend copy missing')
out=[]
for i,gpu in enumerate([0,4]):
 run=r/('run_'+str(i));run.mkdir();plan=r/('plan_'+str(i)+'.json')
 with (run/'worker.log').open('w') as log:p=subprocess.Popen(['python3',str(r/'t12_remaining_grid_worker.py'),'--plan',str(plan),'--root',str(run),'--source',str(source),'--gpu',str(gpu)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 out.append(dict(host='p25',root=str(run),pid=p.pid,gpu=gpu,source=str(source),planned_contexts=len(json.loads(plan.read_text())),backend_sha256=hashlib.sha256(renderer.read_bytes()).hexdigest(),active_plan=str(plan),active_plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest()))
print(json.dumps(out))
'''.replace('DIRECTORY',repr(directory))
    launches=json.loads(remote_text('p25',code))
    for i,l in enumerate(launches):(ROOT/('t12_remaining_grid_'+str(i)+'_launch_20261022.json')).write_text(json.dumps(l,indent=2))
    marker.write_text(json.dumps(launches,indent=2));print(json.dumps(launches))


if __name__=='__main__':main()
