"""Queue T11's remaining original-host intervals without disturbing resident jobs."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    receipt=ROOT/'t11_original_p29_boundary_launch_20261020.json'
    if receipt.exists():raise RuntimeError('original-host task already launched')
    candidates=json.loads((ROOT/'five_scene_boundary_candidates_20261020.json').read_text())
    jobs=[j for j in candidates if j['scene_id']=='T11' and all(e['source_host']=='p29' for e in j['endpoints'])]
    if len(jobs)!=19:raise ValueError('original-host interval set changed')
    source='/21231_data1/liyuhan_t11_genesis_20261016/importer';root='/21231_data1/liyuhan_t11_genesis_20261016/critical_boundaries_20261020'
    plan=ROOT/'t11_original_p29_boundary_input_20261020.json';plan.write_text(json.dumps(jobs))
    subprocess.run(['ssh','-o','BatchMode=yes','p29','mkdir','-p',root],check=True)
    for file,name in [(plan,'input.json'),(Path('scripts/five_scene_boundary_worker.py'),'five_scene_boundary_worker.py'),(Path('scripts/five_scene_boundary_rules.py'),'five_scene_boundary_rules.py'),(Path('scripts/egl_renderer_bootstrap.py'),'egl_renderer_bootstrap.py')]:subprocess.run(['scp','-q',str(file.resolve()),'p29:'+root+'/'+name],check=True)
    code=r'''
import pathlib,json,hashlib,subprocess,os
root=pathlib.Path(ROOT_DIRECTORY);source=pathlib.Path(SOURCE_DIRECTORY)
renderer=source/'scripts/render_t11_r010_slow_chain.py';py=pathlib.Path('/21231_data1/liyuhan_t03_20261008/envs/genesis/bin/python')
if not renderer.exists() or not py.exists():raise ValueError('original p29 runtime missing')
jobs=json.loads((root/'input.json').read_text());sources={str(renderer):hashlib.sha256(renderer.read_bytes()).hexdigest()}
for job in jobs:job['renderer']=str(renderer);job['backend_sources']=sources
(root/'plan.json').write_text(json.dumps(jobs))
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYOPENGL_PLATFORM='egl',PYTHONPATH=str(source)+':'+str(source/'scripts'))
cache=root/'cache';cache.mkdir(exist_ok=True);env.update(XDG_CACHE_HOME=str(cache),TMPDIR=str(cache),PYTHONFAULTHANDLER='1')
bootstrap=root/'egl_renderer_bootstrap.py'
with (root/'worker.log').open('w') as log:p=subprocess.Popen([str(py),str(root/'five_scene_boundary_worker.py'),'--plan',str(root/'plan.json'),'--root',str(root/'run'),'--gpu','3','--python',str(py),'--minimum-free-memory-mib','6144','--render-backend','original','--renderer-bootstrap',str(bootstrap)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p29',root=str(root/'run'),pipeline_root=str(root),pid=p.pid,gpu=3,planned_intervals=len(jobs),renderer=str(renderer),python=str(py),controller_python=str(py),minimum_free_memory_mib=6144,render_backend='original',renderer_bootstrap=str(bootstrap),graphics_environment={k:env[k] for k in ['PYOPENGL_PLATFORM','PYTHONPATH','XDG_CACHE_HOME','TMPDIR']},plan=jobs)))
'''.replace('ROOT_DIRECTORY',repr(root)).replace('SOURCE_DIRECTORY',repr(source))
    p=subprocess.run(['ssh','-o','BatchMode=yes','p29','python3 -'],input=code.encode(),capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    launch=json.loads(p.stdout);prepared=launch.pop('plan')
    (ROOT/'t11_original_p29_boundary_plan_20261020.json').write_text(json.dumps(prepared));receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
