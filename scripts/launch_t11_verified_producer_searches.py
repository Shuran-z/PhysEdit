"""Replay T11 pairs with verified p26 production receipts on p26 itself."""
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT


def producer_pairs(jobs,audit,host):
    by_id={r['sample_id']:r for r in audit}
    return [j for j in jobs if all(by_id[e['sample_id']]['production_host']==host for e in j['endpoints'])]


def main():
    receipt=ROOT/'t11_verified_p26_producer_launch_20261020.json'
    if receipt.exists():raise RuntimeError('verified producer queue already launched')
    audit=json.loads((ROOT/'t11_production_host_audit_20261020.json').read_text())
    jobs=producer_pairs(json.loads((ROOT/'t11_original_p29_boundary_plan_20261020.json').read_text()),audit,'p26')
    if len(jobs)!=8:raise ValueError('verified production set changed')
    by_id={r['sample_id']:r for r in audit}
    for job in jobs:
        job['production_host']='p26'
        job['production_completion_receipts']=[by_id[e['sample_id']] for e in job['endpoints']]
    plan=ROOT/'t11_verified_p26_producer_plan_20261020.json';plan.write_text(json.dumps(jobs))
    root='/21231_data1/liyuhan_t11_genesis_20261016/critical_boundaries_p26_verified_20261020'
    subprocess.run(['ssh','p26','mkdir','-p',root],check=True)
    for p,name in [(plan,'plan.json'),(Path('scripts/five_scene_boundary_worker.py'),'five_scene_boundary_worker.py'),(Path('scripts/five_scene_boundary_rules.py'),'five_scene_boundary_rules.py')]:subprocess.run(['scp','-q',str(p.resolve()),'p26:'+root+'/'+name],check=True)
    code=r'''
import pathlib,json,subprocess,os
r=pathlib.Path(DIRECTORY);source=pathlib.Path('/21231_data1/liyuhan_t11_genesis_20261016/importer');e='/home/wangzijun_p25/miniconda3/envs/genesis';py=e+'/bin/python'
jobs=json.loads((r/'plan.json').read_text())
for job in jobs:
 for completion in job['production_completion_receipts']:
  import hashlib
  if hashlib.sha256(pathlib.Path(completion['completion_receipt']).read_bytes()).hexdigest()!=completion['completion_sha256']:raise ValueError('producer receipt changed')
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONUNBUFFERED='1',PYTHONFAULTHANDLER='1',T11_FFMPEG_WRITER='1',PYTHONPATH=str(source)+':'+str(source/'scripts'),PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json')
env['LD_LIBRARY_PATH']=e+'/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib'
env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
cache=r/'cache';cache.mkdir(exist_ok=True);env.update(XDG_CACHE_HOME=str(cache),TMPDIR=str(cache))
with (r/'worker.log').open('w') as log:p=subprocess.Popen([py,str(r/'five_scene_boundary_worker.py'),'--plan',str(r/'plan.json'),'--root',str(r/'run'),'--gpu','3','--python',py,'--render-backend','original'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(host='p26',production_host='p26',root=str(r/'run'),pipeline_root=str(r),pid=p.pid,gpu=3,planned_intervals=len(jobs),python=py,graphics_environment={k:env[k] for k in ['T11_FFMPEG_WRITER','LD_PRELOAD','PYOPENGL_PLATFORM','__EGL_VENDOR_LIBRARY_FILENAMES']},scope='both endpoint completion workers verified as p26; numerical camera capture differs from full production and is recorded explicitly')))
'''.replace('DIRECTORY',repr(root))
    result=subprocess.run(['ssh','p26','python3 -'],input=code.encode(),capture_output=True,timeout=45)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    launch=json.loads(result.stdout);receipt.write_text(json.dumps(launch,indent=2));print(json.dumps(launch))


if __name__=='__main__':main()
