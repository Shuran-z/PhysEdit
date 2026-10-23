"""Launch prepared source-check/search stages without duplicating existing queues."""
import argparse
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host');parser.add_argument('--runtime-root');parser.add_argument('--kind',choices=['contacts','t03'])
    parser.add_argument('--local-plan');parser.add_argument('--receipt-name')
    args=parser.parse_args()
    if any([args.host,args.runtime_root,args.kind]) and not all([args.host,args.runtime_root,args.kind]):parser.error('host, runtime-root and kind are required together')
    targets=[(args.host,args.runtime_root,args.kind)] if args.host else [
        ('p25','/data_cached/wangzijun_p25/liyuhan/remaining_family_scans_20261023/runtime_v1','contacts'),
        ('p26','/21231_data1/liyuhan_conditional_families_20261023/runtime_v1','t03')]
    launches=[]
    for host,base,kind in targets:
        code=r'''
import pathlib,json,subprocess,os,hashlib,time
b=pathlib.Path(BASE);kind=KIND;root=b/('run_'+kind);root.mkdir(exist_ok=True);plan=b/(kind+'_jobs.json');python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
prior=b/'launch_manifest.json'
if prior.exists():
 old=json.loads(prior.read_text());proc=pathlib.Path('/proc')/str(old['pid'])
 if proc.exists() and str(b).encode() in (proc/'cmdline').read_bytes():print(json.dumps(old));raise SystemExit
 raise ValueError('previous queue ended; inspect before relaunch')
manifest=dict(root=str(root),hours=336,minimum_free_memory_mib=8192,argv=[python,str(b/'conditional_family_pipeline.py'),'--plan',str(plan),'--root',str(root),'--gpu','{GPU}','--python',python,'--worker',str(b/'conditional_family_search.py')],source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [plan,b/'conditional_family_pipeline.py',b/'conditional_family_search.py',b/'published_contact_vectors.py']})
mp=b/(kind+'_manifest.json');mp.write_text(json.dumps(manifest));env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
runtime='/home/wangzijun_p25/miniconda3/envs/genesis';lib=runtime+'/lib/python3.10/site-packages/nvidia/'+('cuda_nvrtc/lib' if HOST=='p26' else 'cu13/lib')
if pathlib.Path(lib).exists():env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
if HOST=='p26':
 env['GENESIS_DISABLE_CV2']='1';env['__EGL_VENDOR_LIBRARY_FILENAMES']='/usr/share/glvnd/egl_vendor.d/10_nvidia.json';env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
with (root/'supervisor.log').open('w') as log:p=subprocess.Popen([python,str(b/'gpu_wait_queue.py'),'--manifest',str(mp)],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
time.sleep(2)
if p.poll() is not None:raise RuntimeError('scheduler exited')
out=dict(host=HOST,root=str(root),pipeline_root=str(b),pid=p.pid,gpu='auto',kind=kind,planned_jobs=len(json.loads(plan.read_text())),plan=str(plan),plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),source_check_stage=True,minimum_free_memory_mib=8192)
(b/'launch_manifest.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''.replace('BASE',repr(base)).replace('KIND',repr(kind)).replace('HOST',repr(host))
        launch=json.loads(remote_text(host,code,timeout=45,python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))
        if args.local_plan:launch['local_plan']=args.local_plan
        (ROOT/(args.receipt_name or 'conditional_'+kind+'_launch_20261023.json')).write_text(json.dumps(launch,indent=2))
        launches.append(launch)
    marker=ROOT/'conditional_family_launches_20261023.json'
    previous=json.loads(marker.read_text()) if marker.exists() else []
    previous=[p for p in previous if (p['host'],p['root']) not in {(r['host'],r['root']) for r in launches}]
    marker.write_text(json.dumps(previous+launches,indent=2))
    print(json.dumps(launches))


if __name__=='__main__':main()
