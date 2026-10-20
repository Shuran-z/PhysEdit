"""Replay the selected old T14 release with its own renderer and event analyzer.

The formal solver profile is preserved. All three original branches are measured
before refining each observed adjacent flip; no monotonicity is assumed. This is
numerical recovery, not automatic visual admission or generated-video scoring.
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


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def physical(config):
    return dict(objects=config['dynamic_objects'],scene={k:v for k,v in config['scene_overrides'].items() if not k.startswith('raytracing') and k!='use_raytracing'},
        manifest=config['manifest'],forces=config.get('runtime_forces',[]),seed=config['experiment'].get('random_seed'),
        timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})


def canonical(config,family):
    c=copy.deepcopy(config)
    theta=c['experiment']['parameter'][family]
    for o in c['dynamic_objects']:
        if family=='channel_throat_width_m' and o['name'] in ['t14v2_corridor_book_left','t14v2_corridor_book_right']:
            o['pose']['position'][1]+=theta/2 if o['name'].endswith('left') else -theta/2
        if o['name']=='t14v2_marker':
            if family=='marker_initial_yaw_deg':o['pose']['euler_xyz'][2]-=theta
            if family=='trigger_impulse_magnitude_Ns':o['motion']['initial_velocity'][0]-=theta/c['experiment']['parameter']['marker_mass_kg']
    def stable(x):
        if isinstance(x,float):return round(x,10)
        if isinstance(x,list):return [stable(v) for v in x]
        if isinstance(x,dict):return {k:stable(v) for k,v in x.items()}
        return x
    return stable(physical(c))


def intervene(config,family,theta):
    c=copy.deepcopy(config);p=c['experiment']['parameter'];old=p[family]
    p[family]=theta
    for o in c['dynamic_objects']:
        if family=='channel_throat_width_m' and o['name'] in ['t14v2_corridor_book_left','t14v2_corridor_book_right']:
            o['pose']['position'][1]+=(old-theta)/2 if o['name'].endswith('left') else (theta-old)/2
        if o['name']=='t14v2_marker':
            if family=='marker_initial_yaw_deg':o['pose']['euler_xyz'][2]+=theta-old
            if family=='trigger_impulse_magnitude_Ns':
                speed=theta/p['marker_mass_kg'];o['motion']['initial_velocity'][0]=speed
                p['marker_initial_speed_mps']=speed;p['marker_initial_velocity_mps'][0]=speed
                p['trigger_impulse_vector_Ns'][0]=theta
    if canonical(c,family)!=canonical(config,family):raise ValueError('intervention changed fixed physics')
    return c


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--root',required=True);p.add_argument('--gpu',default='2');p.add_argument('--wait-for-pid',type=int)
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.wait_for_pid:
        deadline=time.monotonic()+8*3600
        while (Path('/proc')/str(args.wait_for_pid)).exists():
            if time.monotonic()>deadline:raise RuntimeError('dependency wait exceeded eight hours')
            time.sleep(15)
    payload=json.loads(Path(args.plan).read_text());renderer=Path(payload['renderer']['path']);analyzer=root/'analyzer.py'
    analyzer.write_text(payload['analyzer']['text'])
    if sha(renderer)!=payload['renderer']['sha256'] or sha(analyzer)!=payload['analyzer']['sha256']:raise ValueError('original source hash mismatch')
    results=[]
    for job in payload['jobs']:
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);output=folder/'result.json'
        if output.exists():results.append(json.loads(output.read_text()));save(root/'status.json',results);continue
        try:
            family=job['family'];anchors=sorted(job['anchors'],key=lambda r:r['theta']);base=anchors[0]['config']
            if any(canonical(r['config'],family)!=canonical(base,family) for r in anchors):raise ValueError('published triplet changes fixed physics')
            def evaluate(theta):
                if shutil.disk_usage(root).free<30*1024**3:raise RuntimeError('disk below 30GiB free')
                out=folder/format(theta,'.12g');out.mkdir(exist_ok=True);receipt=out/'receipt.json'
                cp=out/'config.json';sp=out/'physics.json';op=out/'outcome.json'
                if receipt.exists():
                    r=json.loads(receipt.read_text())
                    if r['state_sha256']!=sha(sp) or r['config_sha256']!=sha(cp):raise ValueError('cached result hash mismatch')
                    return r
                c=intervene(base,family,theta)
                render=c['render'];render.update(resolution=[160,96],raytracing_spp=1,write_video=False,render_backend='raster')
                for k in ['save_video','save_first_rgb','save_last_rgb']:
                    if k in render:render[k]=str(out/Path(render[k]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(sp);save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0')
                lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'
                env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                with (out/'run.log').open('w') as log:
                    run=subprocess.run([PYTHON,str(renderer),'--config',str(cp)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
                    if run.returncode:raise RuntimeError('renderer failed; '+str(out/'run.log'))
                    subprocess.run([PYTHON,str(analyzer),str(sp),'--config',str(cp),'--output',str(op)],stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True)
                state=json.loads(sp.read_text());expected=c['render']['frames']
                if len(state['frames'])!=expected or any(not math.isfinite(x) for f in state['frames'] for o in f['objects'] for x in o['position']):raise ValueError('incomplete or nonfinite state')
                outcome=json.loads(op.read_text());r=dict(theta=theta,events={k:int(outcome[k]) for k in ['passed_channel','contacted_eraser','complete_terminal_chain']},outcome=outcome,
                    config_sha256=sha(cp),state_sha256=sha(sp),renderer_sha256=sha(renderer),analyzer_sha256=sha(analyzer))
                save(receipt,r);print(json.dumps(dict(job=job['job_id'],theta=theta,events=r['events'])),flush=True);return r
            measured=[evaluate(r['theta']) for r in anchors];intervals=[]
            tolerance={'channel_throat_width_m':.0001,'marker_initial_yaw_deg':.02,'trigger_impulse_magnitude_Ns':.00005}[family]
            for event in ['passed_channel','complete_terminal_chain']:
                for left,right in zip(measured,measured[1:]):
                    if left['events'][event]==right['events'][event]:continue
                    a,b=left['theta'],right['theta'];label=left['events'][event]
                    while b-a>tolerance:
                        mid=(a+b)/2;new=evaluate(mid)
                        if new['events'][event]==label:a=mid
                        else:b=mid
                    intervals.append(dict(target_event=event,bracket=[a,b],endpoint_labels=[label,1-label],source_bracket=[left['theta'],right['theta']]))
            result=dict(job_id=job['job_id'],family=family,status='scanned_original_triplet',anchors=[dict(sample_id=a['sample_id'],theta=a['theta'],original_config_sha256=a['sha256'],events=m['events']) for a,m in zip(anchors,measured)],intervals=intervals,
                renderer_sha256=sha(renderer),analyzer_sha256=sha(analyzer),remaining=['published_state_event_comparison','repeatability','rgb_observability'],formal_nearacc_eligible=False)
            save(output,result)
        except Exception as exc:result=dict(job_id=job['job_id'],status='failed',error=str(exc))
        results.append(result);save(root/'status.json',results)


if __name__=='__main__':main()
