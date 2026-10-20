"""Refine T12 conditional brackets on the original p26 Genesis deployment.

Wait for an unused GPU; never interrupt an existing GPU process. Isolate every
output path, retain original physics and one-dimensional intervention semantics.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
SOURCE=Path('/home/wangzijun_p25/t12_dualsim_v3_20261011/genesis_deploy/source')
RENDERER=SOURCE/'12_render_motion_sequence.py'
PATHS={'speed':('t12_stapler','motion','initial_velocity',0),'friction':('t12_stapler','friction'),'target_mass':('t12_tissue_box','mass')}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p,value):
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(p)


def find_free_gpu():
    gpu_lines=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits']).decode().splitlines()
    busy={x.strip() for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid','--format=csv,noheader,nounits']).decode().splitlines() if x.strip()}
    return next((index.strip() for line in gpu_lines for index,uuid in [line.split(',',1)] if uuid.strip() not in busy),None)


def set_parameter(config,axis,theta):
    c=copy.deepcopy(config);byname={o['name']:o for o in c['dynamic_objects']};path=PATHS[axis];value=byname
    for k in path[:-1]:value=value[k]
    value[path[-1]]=theta
    params=c['t12_parameters']
    if axis=='speed':params['stapler_initial_velocity_mps'][0]=theta;c['experiment']['controlled_physics']['stapler']['initial_velocity_mps'][0]=theta
    elif axis=='friction':params['stapler_friction']=theta;c['experiment']['controlled_physics']['stapler']['friction']=theta
    else:params['tissue_mass_kg']=theta;c['experiment']['controlled_physics']['tissue_box']['mass_kg']=theta
    return c


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--plan',required=True);p.add_argument('--wait-hours',type=float,default=12);args=p.parse_args()
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text(encoding='utf-8'));deadline=time.monotonic()+args.wait_hours*3600;gpu=None
    save(root/'resource_status.json',dict(status='waiting_for_unused_gpu',planned=len(jobs),backend_sha256=sha(RENDERER)))
    while gpu is None:
        gpu=find_free_gpu()
        if gpu is not None:break
        if time.monotonic()>deadline:raise RuntimeError('no unused GPU before bounded wait deadline')
        time.sleep(30)
    save(root/'resource_status.json',dict(status='running',gpu=gpu,planned=len(jobs),backend_sha256=sha(RENDERER)))
    results=[]
    for job in jobs:
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);receipt=folder/'receipt.json'
        if receipt.exists():results.append(json.loads(receipt.read_text(encoding='utf-8')));save(root/'status.json',results);continue
        try:
            axis=job['axis'];base=job['endpoints'][0]['config'];a,b=job['window']['bracket'];labels=job['window']['labels']
            probes=[]
            def evaluate(theta):
                if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('disk below 20GiB')
                out=folder/format(theta,'.12g');out.mkdir(exist_ok=True);rp=out/'receipt.json';sp=out/'physics.json';cp=out/'config.json'
                if rp.exists():return json.loads(rp.read_text(encoding='utf-8'))
                c=set_parameter(base,axis,theta);render=c['render']
                render.update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1,use_native_recording=False,camera_outputs=[])
                for k in ['save_video','save_first_rgb','save_last_rgb']:
                    if k in render:render[k]=str(out/Path(render[k]).name)
                c['annotations']['save_path']=str(sp);c['scene_overrides']['raytracing']=False;save(cp,c)
                with (out/'run.log').open('w') as log:
                    run=subprocess.run([PYTHON,str(RENDERER),'--config',str(cp)],cwd=SOURCE,env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu),stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                if run.returncode:raise RuntimeError('original renderer failed; '+str(out/'run.log'))
                state=json.loads(sp.read_text(encoding='utf-8'));positions=[next(o['position'] for o in f['objects'] if o['name']=='t12_tissue_box') for f in state['frames']]
                if len(positions)!=210 or any(not math.isfinite(x) for p in positions for x in p):raise ValueError('incomplete or nonfinite trajectory')
                maximum=max(math.dist(positions[0],p) for p in positions);r=dict(theta=theta,label=int(maximum>=job['threshold_m']),max_displacement_m=maximum,config_sha256=sha(cp),state_sha256=sha(sp),backend_sha256=sha(RENDERER))
                save(rp,r);return r
            for endpoint,label in zip([a,b],labels):
                r=evaluate(endpoint);probes.append(r)
                if r['label']!=label:raise ValueError('endpoint does not reproduce published event')
            tolerance={'speed':.001,'friction':.0005,'target_mass':.0005}[axis]
            while b-a>tolerance:
                middle=(a+b)/2;r=evaluate(middle);probes.append(r)
                if r['label']==labels[0]:a=middle
                else:b=middle
            row=dict(job_id=job['job_id'],axis=axis,fixed_context_sha256=job['fixed_context_sha256'],status='refined_local_interval',source_bracket=job['window']['bracket'],bracket=[a,b],endpoint_sample_ids=job['window']['endpoint_sample_ids'],probes=probes,backend_sha256=sha(RENDERER),target_event=job['target_event'],threshold_m=job['threshold_m'])
            save(receipt,row)
        except Exception as exc:row=dict(job_id=job['job_id'],axis=job['axis'],status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results);print(json.dumps(dict(done=len(results),refined=sum(r['status']=='refined_local_interval' for r in results),failed=sum(r['status']=='failed' for r in results))),flush=True)
    save(root/'resource_status.json',dict(status='finished',gpu=gpu,planned=len(jobs)))


if __name__=='__main__':main()
