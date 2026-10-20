"""Bisect geometry-labeled T09 windows using original seeded Genesis renderer."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

PROJECT=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
RENDERER=PROJECT/'scripts/render_sample.py'


def change(config,axis,theta):
    c=copy.deepcopy(config);old=c['experiment']['parameter']['parameter_value'];c['experiment']['parameter']['parameter_value']=theta
    if axis=='layer_friction':
        for obj in c['dynamic_objects']:
            if obj['name'].startswith('t09_book_'):
                obj['friction']=theta
                if 'friction' in obj.get('material_preset',{}):obj['material_preset']['friction']=theta
    elif axis=='pull_force':
        if old==0:raise ValueError('zero amplitude base is not an interpolation recipe')
        for f in c['runtime_forces']:
            if f['target']=='t09_book_03':f['force_world']=[x*theta/old for x in f['force_world']]
    else:raise ValueError('unsupported original axis')
    return c


def event(config,state,target_event='geometry_support_drop'):
    if len(state['frames'])!=210:raise ValueError('incomplete original simulation')
    if target_event=='upper_nonpulled_book_on_table_at_end':
        names=config['experiment']['supported_book_names'];frame=state['frames'][-1]
        if 'contacts' not in frame:raise ValueError('final contact telemetry missing')
        pairs={frozenset([c['entity_a'],c['entity_b']]) for c in frame['contacts']}
        affected=[n for n in names if frozenset(['frozen_tabletop_collision_slab',n]) in pairs]
        return dict(label=int(bool(affected)),upper_books_on_table=affected,target_event=target_event)
    if target_event!='geometry_support_drop':raise ValueError('unsupported event')
    names=config['experiment']['supported_book_names'];extracted=config['experiment']['extracted_book_name'];o=next(o for o in config['dynamic_objects'] if o['name']==extracted)
    h=o.get('collision_proxy_size',o['size'])[2]
    z=lambda f:{o['name']:o['position'][2] for o in f['objects'] if o['name'] in names}
    initial,final=z(state['frames'][0]),z(state['frames'][-1])
    drops={n:initial[n]-final[n] for n in names}
    if any(not math.isfinite(v) for v in drops.values()):raise ValueError('nonfinite simulated drop')
    return dict(label=int(max(drops.values())>=h*.5),drop_threshold_m=h*.5,upper_book_final_drops_m=drops)


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)


def main():
    import fcntl
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--root',required=True);parser.add_argument('--gpu',default='3');args=parser.parse_args()
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text(encoding='utf-8'));results=[]
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RENDERER,PROJECT/'scripts/render_t06_t10_physics_v2.py',PROJECT/'scripts/render_base_physical_v5.py']}
    for job in jobs:
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);receipt=folder/'result.json'
        if receipt.exists():results.append(json.loads(receipt.read_text()));save(root/'status.json',results);continue
        probes=[]
        try:
            base=job['base_config'];axis=job['family_id'];a,b=job['bracket'];labels=job['endpoint_labels']
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);rp=dest/'receipt.json'
                if rp.exists():return json.loads(rp.read_text())
                c=change(base,axis,theta);render=c['render'];render.update(resolution=[160,96],raytracing_spp=1,render_backend='raster')
                for key in ['save_video','save_first_rgb','save_last_rgb']:
                    if key in render:render[key]=str(dest/Path(render[key]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(dest/'physics.json')
                config_folder=PROJECT/'configs'/root.name/job['job_id'];config_folder.mkdir(parents=True,exist_ok=True)
                cp=config_folder/(format(theta,'.12g')+'.json');save(cp,c)
                begin=time.monotonic()
                with (dest/'run.log').open('w') as log:
                    run=subprocess.run([PYTHON,str(RENDERER),'--config',str(cp)],cwd=PROJECT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0'),stdout=log,stderr=subprocess.STDOUT,timeout=300)
                raw=(dest/'physics.json').read_bytes();state=json.loads(raw);measured=event(c,state,job.get('target_event','geometry_support_drop'))
                result=dict(theta=theta,**measured,renderer_returncode=run.returncode,elapsed_s=time.monotonic()-begin,config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(raw).hexdigest(),state_path=str(dest/'physics.json'),seed=c['seed'])
                # A visual post-check is independent of a complete numeric state.
                save(rp,result);return result
            for value,label in zip([a,b],labels):
                r=evaluate(value);probes.append(r);save(folder/'probes.json',probes)
                if r['label']!=label:raise ValueError('published endpoint outcome did not reproduce under fixed source seed')
            while b-a>.0005:
                middle=(a+b)/2;r=evaluate(middle);probes.append(r);save(folder/'probes.json',probes)
                if r['label']==labels[0]:a=middle
                else:b=middle
            row=dict(job_id=job['job_id'],family_id=axis,status='refined_local_interval',bracket=[a,b],source_bracket=job['bracket'],endpoint_labels=labels,
                fixed_context_sha256=job['fixed_context_sha256'],probes=probes,backend_sources=sources,target_event=job.get('target_event','geometry_support_drop'),
                seed=base['seed'],scope='conditional local interval for the explicitly recorded event at the source endpoint seed')
            save(receipt,row)
        except Exception as exc:row=dict(job_id=job['job_id'],status='failed',error=str(exc),probes=probes)
        results.append(row);save(root/'status.json',results);print(json.dumps(dict(done=len(results),status=row['status'],bracket=row.get('bracket'),error=row.get('error'))),flush=True)


if __name__=='__main__':main()
