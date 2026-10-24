"""Fixed-source conditional searches on original T03/T16/T17/T20 renderers."""
import argparse
import copy
import functools
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
try:
    from scripts.published_contact_vectors import PAIRS, vector
except ModuleNotFoundError:
    from published_contact_vectors import PAIRS, vector

PROJECT=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1')


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


@functools.lru_cache(maxsize=1)
def original_builder():
    build=module(PROJECT/'scripts/build_project.py','conditional_original_builder')
    return build,build.load_backgrounds()


def intervene(job,theta):
    config=copy.deepcopy(job['base_config'])
    if theta==job['theta']:
        return config
    if job.get('original_pair_job'):
        try:from scripts.five_scene_boundary_rules import intervene as original_intervene
        except ModuleNotFoundError:from five_scene_boundary_rules import intervene as original_intervene
        return original_intervene(job['original_pair_job'],theta)
    e=config['experiment'];objects={o['name']:o for o in config['dynamic_objects']}
    if job['scene_id']=='T03':
        p=e['parameter'];g=e['geometry_contract'];delta=theta-job['theta'];axis=job['family_id']
        if axis=='A':
            objects['t03v5_impulsed_book']['motion']['initial_velocity'][0]=theta
            p['book_initial_speed_mps']=theta
            p['declared_one_shot_impulse_vector_Ns'][0]=p['book_mass_kg']*theta
            p['declared_one_shot_impulse_magnitude_Ns']=p['book_mass_kg']*theta
        elif axis=='B':
            objects['t03v5_upper_edge_can']['pose']['position'][0]-=delta
            p['upper_can_com_edge_distance_m']=theta
            g['upper_can_center_m'][0]-=delta
            g['initial_can_phone_horizontal_gap_m']+=delta
            g['initial_book_can_surface_gap_m']-=delta
        elif axis=='C':
            rise=delta*math.tan(math.radians(p['lower_transfer_ramp_slope_deg']))
            objects['t03v5_lower_edge_phone']['pose']['position'][0]-=delta
            objects['t03v5_lower_edge_phone']['pose']['position'][2]+=rise
            p['lower_phone_com_edge_distance_m']=theta
            g['lower_phone_center_m'][0]-=delta;g['lower_phone_center_m'][2]+=rise
            g['initial_can_phone_horizontal_gap_m']-=delta
        else:raise ValueError('unknown T03 family')
    else:
        build,backgrounds=original_builder()
        original,_=build.scene_objects(job['scene_id'],job['family_id'],job['theta'],backgrounds[e['background_id']],e['trajectory_id'])
        if original!=job['base_config']['dynamic_objects']:
            raise ValueError('original recipe does not reproduce source geometry')
        config['dynamic_objects'],metadata=build.scene_objects(job['scene_id'],job['family_id'],theta,backgrounds[e['background_id']],e['trajectory_id'])
        e.update(metadata);e['parameter']['parameter_value']=theta
    return config


def events(job,config,state,state_path=None):
    frames=state['frames']
    if len(frames)!=210 or any(not math.isfinite(v) for f in frames for o in f['objects'] for v in o['position']):
        raise ValueError('incomplete/nonfinite original simulation')
    if job.get('original_pair_job'):
        target=job['original_pair_job']['target_event']
        if job['scene_id']=='T01':
            audit=module(job['auditor'],'conditional_t01_auditor').analyze(Path(state_path))
            label=int(audit['outcome_label']=='full_chain') if job['family_id']=='C' else int(audit['stage_frames']['book_can_1' if job['family_id']=='A' else 'can_1_can_2'] is not None)
        else:
            try:from scripts.five_scene_boundary_rules import event
            except ModuleNotFoundError:from five_scene_boundary_rules import event
            label=event(config,state,target)
        return {target:label}
    if job['scene_id']=='T03':
        if state_path is None:raise ValueError('original T03 auditor requires state file')
        audit=module(job['auditor'],'conditional_t03_auditor').audit_one(Path(state_path))
        return dict(book_contacts_upper_can=int(audit['first_contact_frame']['book_can'] is not None),
                    upper_can_falls=int(audit['observed_outcome'].startswith(('B1_','C'))),
                    full_chain_phone_second_fall=int(audit['observed_outcome']=='C2_full_chain_phone_second_fall'))
    names={o['name'] for o in config['dynamic_objects']};contacts=[]
    for pair in PAIRS[job['scene_id']]:
        times=[(f['frame_index'],c.get('physics_step_index',-1)) for f in frames for c in f.get('contacts',[])
               if {c.get('entity_a'),c.get('entity_b')}==set(pair)]
        contacts.append(dict(pair=pair,applicable=set(pair)<=names,occurred=bool(times),
            present_at_end=any({c.get('entity_a'),c.get('entity_b')}==set(pair) for c in frames[-1].get('contacts',[])),
            first=list(min(times)) if times else None))
    return vector(dict(scene_id=job['scene_id'],actors=[dict(name=n) for n in names],
                       scene_overrides=config['scene_overrides'],contacts=contacts))


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data));temp.replace(path)


def restore_visual_manifest(config,job):
    restoration=job.get('visual_manifest_restoration')
    if not restoration:return
    manifest=Path(restoration['manifest_path'])
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=restoration['manifest_sha256']:
        raise ValueError('restored manifest changed')
    if restoration['geometry_sha256']!=restoration['recorded_geometry_sha256']:
        raise ValueError('restored visual geometry does not match original')
    data=json.loads(manifest.read_text())
    if data.get('background_metadata',{}).get('all_decor_visual_only') is not True:
        raise ValueError('restored manifest is not explicitly visual-only')
    for obj in data['objects']:
        if obj.get('decor_collision_policy')!='visual_only' or obj.get('collision_mesh_path') is not None:
            raise ValueError('restored manifest introduces a collision object')
        if hashlib.sha256(Path(obj['mesh_path']).read_bytes()).hexdigest()!=restoration['recorded_geometry_sha256']:
            raise ValueError('restored mesh changed')
    config['manifest']=str(manifest)


def acquire_gpu(root,preferred):
    import fcntl
    while True:
        if shutil.disk_usage(root).free<20*1024**3:
            save(root/'resource_status.json',dict(status='waiting_for_disk',minimum_free_GiB=20));time.sleep(20);continue
        csv=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits']).decode()
        cards=sorted((tuple(map(int,r.split(','))) for r in csv.splitlines() if r.strip()),key=lambda r:r[1],reverse=True)
        for gpu,free in cards:
            if free<8192 or preferred!='auto' and str(gpu)!=preferred:continue
            lease=Path('/tmp/physedit_conditional_gpu_'+str(gpu)+'.lock').open('a')
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:lease.close();continue
            return str(gpu),lease
        save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=preferred));time.sleep(20)


def main():
    import fcntl
    parser=argparse.ArgumentParser()
    for name in ['plan','root','gpu','python']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--source-only',action='store_true')
    args=parser.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    results=[]
    for job in json.loads(Path(args.plan).read_text()):
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);final=folder/'result.json';probes={}
        if final.exists():results.append(json.loads(final.read_text()));save(root/'status.json',results);continue
        try:
            if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha for p,sha in job['backend_sources'].items()):
                raise ValueError('original source changed')
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);receipt=dest/'receipt.json'
                if receipt.exists():
                    r=json.loads(receipt.read_text());stored=Path(r['state_path']).read_bytes()
                    if hashlib.sha256(stored).hexdigest()!=r['stored_state_sha256'] or hashlib.sha256(gzip.decompress(stored)).hexdigest()!=r['state_sha256'] or hashlib.sha256((dest/'config.json').read_bytes()).hexdigest()!=r['config_sha256']:
                        raise ValueError('cached original probe changed')
                    probes[theta]=r;return r
                config=intervene(job,theta);restore_visual_manifest(config,job)
                render=config['render'];render.update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1,use_native_recording=False,save_rgb_frames=False,camera_outputs=[])
                for key in ['save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir']:
                    if render.get(key):render[key]=str(dest/Path(render[key]).name)
                config['scene_overrides']['raytracing']=False
                config.setdefault('annotations',{}).update(enabled=True,save_path=str(dest/'physics.json'))
                cp=dest/'config.json';save(cp,config)
                probe_gpu,lease=acquire_gpu(root,args.gpu)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=probe_gpu,TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
                save(root/'resource_status.json',dict(status='running_original_search',scene=job['scene_id'],family=job['family_id'],job_id=job['job_id'],theta=theta,gpu=probe_gpu))
                with (dest/'run.log').open('w') as log:
                    command=[args.python]
                    if job.get('renderer_bootstrap'):command.append(job['renderer_bootstrap'])
                    command += [job['renderer'],'--config',str(cp)]
                    if job['scene_id']=='T11':command.append('--strict-live-physics')
                    try:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=job.get('probe_timeout_seconds',1800))
                    finally:lease.close()
                if run.returncode:raise RuntimeError('original renderer failed: '+str(dest/'run.log'))
                sp=dest/'physics.json';raw=sp.read_bytes();labels=events(job,config,json.loads(raw),sp)
                stored=gzip.compress(raw,compresslevel=3,mtime=0);gz=dest/'physics.json.gz';gz.write_bytes(stored);sp.unlink()
                r=dict(theta=theta,labels=labels,state_path=str(gz),state_sha256=hashlib.sha256(raw).hexdigest(),
                       stored_state_sha256=hashlib.sha256(stored).hexdigest(),config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest())
                save(receipt,r);probes[theta]=r;return r
            source=evaluate(job['theta']);eligible=[k for k,v in job['expected'].items() if source['labels'].get(k)==v]
            rejected=[k for k in job['expected'] if k not in eligible]
            check=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],sample_id=job['sample_id'],
                       status='source_events_checked',eligible_events=eligible,source_event_mismatches=rejected,
                       expected=job['expected'],actual=source['labels'],source_config_sha256=job['source_config_sha256'],
                       source_state_sha256=job['source_state_sha256'],backend_sources=job['backend_sources'])
            save(folder/'source_check.json',check)
            if args.source_only:
                results.append(check);save(root/'status.json',results);continue
            if not eligible:raise ValueError('no requested source event reproduced')
            grid=sorted(set(job['grid']+[job['theta']]));observed=[evaluate(t) for t in grid];intervals=[]
            for event in eligible:
                for left,right in zip(observed,observed[1:]):
                    if left['labels'][event]==right['labels'][event]:continue
                    a,b=left['theta'],right['theta'];labels=[left['labels'][event],right['labels'][event]]
                    while b-a>job['tolerance']:
                        mid=(a+b)/2
                        if evaluate(mid)['labels'][event]==labels[0]:a=mid
                        else:b=mid
                    intervals.append(dict(target_event=event,bracket=[a,b],labels=labels))
            row=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],sample_id=job['sample_id'],
                     status='conditional_family_search_completed',source_state_sha256=job['source_state_sha256'],
                     source_config_sha256=job['source_config_sha256'],backend_sources=job['backend_sources'],
                     source_seed=job['base_config'].get('seed',job['base_config'].get('random_seed')),
                     eligible_events=eligible,source_event_mismatches=rejected,intervals=intervals,probes=list(probes.values()),
                     scope='fixed published source configuration/seed; first scan grid then refine observed changes; no claim of hidden-root exclusion')
            save(final,row)
        except Exception as exc:
            row=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],sample_id=job['sample_id'],status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results);print(json.dumps({k:row[k] for k in ['job_id','scene_id','status']}),flush=True)
    save(root/'resource_status.json',dict(status='completed',gpu=args.gpu))


if __name__=='__main__':main()
