"""T07 friction boundary replay on p25; original solver, isolated output paths.

Run with the server's system Python. Renderer children use the original Genesis
environment. Endpoint reproduction is required before any local bisection.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import time

BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
PROJECT=BASE/'everyday_bifurcation_T07_T08_v2_independent'
RENDERER=BASE/'everyday_bifurcation_T01_v2_7s/scripts/render_t01_t05_production_v3_multicam.py'
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)


def motion(state):
    positions=[next(o['position'] for o in f['objects'] if o['name']=='t07_smartphone') for f in state['frames']]
    if not positions or any(not math.isfinite(v) for p in positions for v in p):raise ValueError('missing or nonfinite phone trajectory')
    maximum=max(math.dist(positions[0],p) for p in positions)
    return int(maximum>=.01),maximum


def table_contact(state):
    start=int(state['render'].get('pre_static_frames',0));frames=state['frames'][start:]
    if not frames or (not state.get('scene_overrides',{}).get('record_contacts') and any('contacts' not in f for f in frames)):raise ValueError('post-release native contact telemetry incomplete')
    hits=[f['frame_index'] for f in frames if any({c.get('entity_a'),c.get('entity_b')}=={'t07_smartphone','frozen_tabletop_collision_slab'} for c in f.get('contacts',[]))]
    return dict(label=int(bool(hits)),first_table_contact_frame=hits[0] if hits else None,table_contact_frames=hits)


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--root',required=True)
    p.add_argument('--gpu',default='0');p.add_argument('--limit',type=int,default=0);p.add_argument('--tolerance',type=float,default=.0005)
    p.add_argument('--minimum-free-memory-mib',type=int,default=8192)
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text());jobs=jobs[:args.limit or None]
    builder_path=PROJECT/'scripts/build_independent_v2.py'
    spec=importlib.util.spec_from_file_location('t07_original_builder',builder_path)
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    assets=builder.load_assets();backgrounds=builder.load_backgrounds()
    results=[]
    for job in jobs:
        folder=root/job['sample_id'];folder.mkdir(exist_ok=True)
        config_path=PROJECT/'configs/formal_v2_balanced_480p'/job['sample_id']/'cam01.json'
        original=json.loads(config_path.read_text())
        family=job.get('family','A_surface_friction')
        if original['dynamic_objects']!=job['objects']:raise ValueError('published object contract mismatch')
        # Only lighting additions in recorded metadata may differ from original config.
        lighting={'raytracing_env_map','raytracing_env_encoding','raytracing_env_map_required','raytracing_env_euler','raytracing_lights'}
        if {k:v for k,v in original['scene_overrides'].items() if k not in lighting}!={k:v for k,v in job['scene_overrides'].items() if k not in lighting}:
            raise ValueError('published solver contract mismatch')
        def evaluate(theta):
            out=folder/format(theta,'.12g');out.mkdir(exist_ok=True)
            c=copy.deepcopy(original)
            if family=='A_surface_friction':
                next(o for o in c['dynamic_objects'] if o['name']=='t07_smartphone')['friction']=theta
            elif family in ['C_ramp_angle_deg','B_initial_longitudinal_position_m']:
                slab=next(o for o in c['dynamic_objects'] if o['name']=='frozen_tabletop_collision_slab')
                top=float(backgrounds[original['experiment']['background_id']]['support_surface']['top_z'])
                baseline,_=builder.scene_t07(assets,top,family,original['experiment']['controlled_value'])
                if baseline!=[o for o in original['dynamic_objects'] if o['name']!=slab['name']]:raise ValueError('original builder does not reproduce published objects')
                objects,extra=builder.scene_t07(assets,top,family,theta)
                c['dynamic_objects']=[slab]+objects;c['experiment'].update(extra)
            else:raise ValueError('no authenticated intervention adapter for '+family)
            c['experiment']['controlled_value']=theta
            c['render'].update(write_video=False,render_backend='raster',resolution=[160,96],save_first_rgb=None,save_last_rgb=None)
            c['render']['save_video']=str(out/'unused.mp4');c['scene_overrides']['raytracing']=False
            c['annotations']['save_path']=str(out/'physics.json')
            path=out/'config.json';receipt=out/'receipt.json'
            if receipt.exists():
                r=json.loads(receipt.read_text())
                if r['renderer_sha256']==sha(RENDERER) and r['config']==c and sha(out/'physics.json')==r['state_sha256']:return r
                raise ValueError('existing replay provenance mismatch')
            while float(subprocess.check_output(['nvidia-smi','-i',args.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<args.minimum_free_memory_mib:
                save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=args.gpu));time.sleep(20)
            save(path,c);env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0')
            lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'
            env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
            with (out/'run.log').open('w') as log:
                r=subprocess.run([PYTHON,str(RENDERER),'--config',str(path)],cwd=BASE,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
            if r.returncode:raise RuntimeError('renderer failed: '+str(out/'run.log'))
            state=json.loads((out/'physics.json').read_text())
            if len(state['frames'])!=210:raise ValueError('incomplete state')
            label,maximum=motion(state)
            contact=table_contact(state) if job.get('target_event')=='phone_table_contact_after_release' else None
            if contact is not None:label=contact['label']
            r=dict(theta=theta,label=label,max_displacement_m=maximum,config=c,config_sha256=sha(path),renderer_sha256=sha(RENDERER),builder_sha256=sha(builder_path),state_sha256=sha(out/'physics.json'))
            if contact is not None:r.update(target_event=job['target_event'],contact_evidence=contact)
            save(receipt,r);print(json.dumps(dict(sample_id=job['sample_id'],theta=theta,label=label)),flush=True);return r
        try:
            lower,upper=job.get('endpoints',[.24,.28])
            endpoints=[evaluate(t) for t in [lower,upper]]
            if [r['label'] for r in endpoints]!=job['endpoint_labels']:raise ValueError('published endpoint reproduction failed')
            if endpoints[0]['label']==endpoints[1]['label']:raise ValueError('endpoint observations do not bracket a transition')
            a,b=lower,upper;probes=[]
            while b-a>args.tolerance:
                mid=(a+b)/2;r=evaluate(mid);probes.append(r['theta'])
                if r['label']==endpoints[0]['label']:a=mid
                else:b=mid
            result=dict(sample_id=job['sample_id'],family=family,status='local_transition_bracket',interval=[a,b],endpoint_labels=job['endpoint_labels'],target_event=job.get('target_event','motion_ge_1cm'),source_state_sha256=job['state_sha256'],original_config_sha256=sha(config_path),probes=probes,scope='local bracket; global monotonicity and visual admission not certified')
        except Exception as exc:
            result=dict(sample_id=job['sample_id'],status='failed',error=str(exc))
            results.append(result);save(root/'results.json',results);continue
        results.append(result);save(root/'results.json',results)


if __name__=='__main__':main()
