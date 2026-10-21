"""Replay and refine T13 current-release local event brackets on p25.

The released renderer's existing --physics-only mode records contact telemetry.
Published endpoint labels and original 5mm precontact consistency check are
required. Contact, motion, vertical drop and floor arrival remain distinct.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess

BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
RENDERER=BASE/'scripts/12_render_motion_sequence_t13_realasset_v7_contact_replay.py'
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
ACTORS=['t13_driver_book','t13_falling_book','t13_drink_box']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def job_identity(job):
    """A source interval alone is not an identity across backgrounds/gravity."""
    payload=dict(family=job['family'],target_event=job['target_event'],bracket=job['bracket'],
        endpoints=[dict(sample_id=r['sample_id'],state_sha256=r['state_sha256'],config=r['config']) for r in job['endpoints']])
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]


def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def get(value,path):
    for k in path:value=value[k]
    return value


def put(value,path,new):
    for k in path[:-1]:value=value[k]
    value[path[-1]]=new


def differences(a,b,path=()):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return [path]
        return [p for k in a for p in differences(a[k],b[k],path+(k,))]
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return [path]
        return [p for i in range(len(a)) for p in differences(a[i],b[i],path+(i,))]
    return [] if a==b else [path]


def metrics(state):
    tracks={n:[next(o['position'] for o in f['objects'] if o['name']==n) for f in state['frames']] for n in ACTORS}
    if any(len(t)!=168 or any(not math.isfinite(x) for p in t for x in p) for t in tracks.values()):raise ValueError('incomplete or nonfinite state')
    positions=tracks['t13_drink_box'];peak=max(math.dist(positions[18],p) for p in positions[18:]);drop=positions[18][2]-min(p[2] for p in positions[18:])
    return dict(t13_drink_box_motion_ge_1cm=int(peak>=.01),drink_drop_ge_5cm=int(drop>=.05)),tracks


def precontact_indices(state):
    """Exclude the first collision frame, including upstream book-book impact."""
    hits=[f['frame_index'] for f in state['frames'] if any(
        c.get('entity_a') in ACTORS and c.get('entity_b') in ACTORS
        and c.get('entity_a')!=c.get('entity_b') for c in f.get('contacts',[]))]
    return range(min(hits)) if hits else range(18)


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--root',required=True);p.add_argument('--gpu',default='4');p.add_argument('--limit',type=int,default=0)
    p.add_argument('--original-full-render',action='store_true',help='Replay original v6 renderer including original camera capture')
    p.add_argument('--init-seed',type=int);p.add_argument('--seed-bootstrap');p.add_argument('--supplemental-scan',action='store_true')
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    if (args.init_seed is None)!=(args.seed_bootstrap is None):p.error('seed control requires both seed and bootstrap')
    if args.supplemental_scan and args.init_seed is None:p.error('supplemental scan requires a declared seed')
    global RENDERER
    if args.original_full_render:RENDERER=BASE/'scripts/12_render_motion_sequence_t13_realasset_v6_sync3cam.py'
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text());jobs=jobs[:args.limit or None];results=[]
    if len({j['job_id'] for j in jobs})!=len(jobs):raise ValueError('duplicate search job IDs')
    if any(j['job_id']!=job_identity(j) for j in jobs):raise ValueError('job ID does not bind exact reference context')
    for job in jobs:
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);receipt=folder/'receipt.json'
        if receipt.exists():
            row=json.loads(receipt.read_text())
            if row['backend_sha256']!=sha(RENDERER):raise ValueError('backend changed')
            if row.get('supplemental_init_seed')!=args.init_seed:raise ValueError('cached result seed contract changed')
            if row['reference_sample_ids']!=[e['sample_id'] for e in job['endpoints']] or row['source_state_sha256']!=[e['state_sha256'] for e in job['endpoints']]:raise ValueError('cached result belongs to another reference context')
            results.append(row);save(root/'status.json',results);continue
        try:
            if shutil.disk_usage(root).free<30*1024**3:raise RuntimeError('stop below 30GiB free')
            left,right=job['endpoints'];a,b=job['bracket'];event=job['target_event']
            objects=[{o['name']:o for o in endpoint['config']['dynamic_objects']} for endpoint in [left,right]]
            allowed={'drink_edge_distance':{('t13_drink_box','pose','position',0)},
                'book_cluster_shift_toward_drink':{('t13_falling_book','pose','position',0),('t13_driver_book','pose','position',0),('t13_driver_book','motion','pivot_world',0)},
                'driver_pivot_gap':{('t13_driver_book','pose','position',0),('t13_driver_book','motion','pivot_world',0)}}[job['family']]
            changed=differences(*objects)
            if not changed or set(changed)-allowed:raise ValueError('unexpected physical intervention')
            def evaluate(theta):
                out=folder/format(theta,'.12g');out.mkdir(exist_ok=True)
                c=copy.deepcopy(left['config']);mapped={o['name']:o for o in c['dynamic_objects']}
                for path in changed:put(mapped,path,get(objects[0],path)+(theta-job['bracket'][0])/(job['bracket'][1]-job['bracket'][0])*(get(objects[1],path)-get(objects[0],path)))
                if args.supplemental_scan:
                    exact=next((r['config'] for r in job['supplemental_grid'] if r['theta']==theta),None)
                    if exact is not None:
                        actual={o['name']:o for o in exact['dynamic_objects']}
                        if any(abs(get(actual,path)-get(mapped,path))>1e-8 for path in changed):raise ValueError('recovered intervention differs from actual published grid')
                        c=copy.deepcopy(exact)
                c['sample_metadata']['main_parameter_value']=theta
                c['sample_metadata']['calibration_only']=True
                cp=out/'config.json';sp=out/'physics.json';rp=out/'receipt.json'
                if rp.exists():
                    row=json.loads(rp.read_text())
                    if row.get('supplemental_init_seed')!=args.init_seed:raise ValueError('cached probe seed contract changed')
                    if row['config_sha256']==sha(cp) and row['state_sha256']==sha(sp) and row['backend_sha256']==sha(RENDERER):return row
                    raise ValueError('replay receipt drift')
                if args.original_full_render:
                    for key in ['save_video','save_first_rgb','save_last_rgb']:
                        if c['render'].get(key):c['render'][key]=str(out/Path(c['render'][key]).name)
                    for camera in c['render'].get('camera_outputs',[]):
                        for key in ['save_video','save_first_rgb','save_last_rgb']:
                            if camera.get(key):camera[key]=str(out/Path(camera[key]).name)
                    c['annotations']['save_path']=str(sp)
                save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0')
                lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'
                env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                with (out/'run.log').open('w') as log:
                    command=[PYTHON]+([args.seed_bootstrap,'--seed',str(args.init_seed)] if args.init_seed is not None else [])+[str(RENDERER),'--config',str(cp)]
                    if not args.original_full_render:command+=['--physics-only','--annotation-output',str(sp)]
                    result=subprocess.run(command,cwd=BASE,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                if result.returncode:raise RuntimeError('renderer failed: '+str(out/'run.log'))
                if args.init_seed is not None:
                    text=re.sub(r'\x1b\[[0-9;]*m','',(out/'run.log').read_text(errors='replace'))
                    if not re.search(r'seed:\s*'+str(args.init_seed)+r'\b',text):raise ValueError('actual Genesis seed not confirmed')
                state=json.loads(sp.read_text());events,tracks=metrics(state)
                row=dict(theta=theta,events=events,config_sha256=sha(cp),state_sha256=sha(sp),backend_sha256=sha(RENDERER))
                if args.init_seed is not None:
                    row.update(supplemental_init_seed=args.init_seed,seed_origin='new declared supplemental control, not recovered original seed',seed_bootstrap_sha256=sha(Path(args.seed_bootstrap)))
                if theta in job['bracket']:
                    original=left if theta==job['bracket'][0] else right
                    indices=list(precontact_indices(state))
                    row['position_check_frame_indices']=indices
                    row['position_check_scope']='strictly_before_first_dynamic_contact' if any('contacts' in f for f in state['frames']) else 'pre_intervention_only_original_v6_has_no_contacts'
                    row['precontact_max_position_error_m']=max(math.dist(original['tracks'][name][i]['position'],tracks[name][i]) for name in ACTORS for i in indices)
                    row['published_label']=original['label'];row['label_matches']=events[event]==original['label']
                    if not args.supplemental_scan and (row['precontact_max_position_error_m']>.005 or not row['label_matches']):raise ValueError('published endpoint not reproduced: '+str(out))
                save(rp,row);print(json.dumps(dict(job_id=job['job_id'],theta=theta,events=events)),flush=True);return row
            if args.supplemental_scan:
                grid=sorted({r['theta'] for r in job['supplemental_grid']});observed=[evaluate(t) for t in grid];intervals=[]
                for low,high in zip(observed,observed[1:]):
                    if low['events'][event]==high['events'][event]:continue
                    lo,hi=low['theta'],high['theta']
                    while hi-lo>.0005:
                        mid=(lo+hi)/2;probe=evaluate(mid)
                        if probe['events'][event]==low['events'][event]:lo=mid
                        else:hi=mid
                    intervals.append(dict(bracket=[lo,hi],endpoint_labels=[low['events'][event],high['events'][event]]))
                row=dict(job_id=job['job_id'],status='supplemental_grid_completed',family=job['family'],target_event=event,supplemental_init_seed=args.init_seed,seed_origin='new control, original seed not recovered',source_state_sha256=[e['state_sha256'] for e in job['endpoints']],grid_observations=observed,local_intervals=intervals,backend_sha256=sha(RENDERER),seed_bootstrap_sha256=sha(Path(args.seed_bootstrap)),scope='conditional observed scan; no unique original-release boundary claim',formal_nearacc_eligible=False)
                row['reference_sample_ids']=[e['sample_id'] for e in job['endpoints']]
                save(receipt,row);results.append(row);save(root/'status.json',results);continue
            ends=[evaluate(t) for t in [a,b]]
            if ends[0]['events'][event]==ends[1]['events'][event]:raise ValueError('same-label endpoints')
            while b-a>.0005:
                mid=(a+b)/2;row=evaluate(mid)
                if row['events'][event]==ends[0]['events'][event]:a=mid
                else:b=mid
            row=dict(job_id=job['job_id'],family=job['family'],target_event=event,status='local_transition_bracket',interval=[a,b],source_bracket=job['bracket'],reference_sample_ids=[x['sample_id'] for x in job['endpoints']],backend_sha256=sha(RENDERER),source_state_sha256=[x['state_sha256'] for x in job['endpoints']],replay_profile='original_v6_full_render' if args.original_full_render else 'v7_physics_only',scope='current release endpoint replay and local interval; repeats and RGB review pending')
            save(receipt,row)
        except Exception as exc:row=dict(job_id=job['job_id'],status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results)


if __name__=='__main__':main()
