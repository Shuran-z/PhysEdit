"""Replay missing T09 states with the original seeded backend, preserving provenance.

These are supplemental simulations, never recovered original annotations.
Only isolated render/output fields change; source physics and seed stay fixed.
"""
import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

PROJECT=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
EVENT='upper_nonpulled_book_on_table_at_end'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)


def validate_state(config,state):
    frames=state.get('frames',[])
    if len(frames)!=210:raise ValueError('incomplete original-backend state')
    actual={o['name']:o['spec'] for o in state['dynamic_objects']}
    expected={o['name']:o for o in config['dynamic_objects']}
    if actual!=expected:raise ValueError('simulated objects differ from published config')
    if state.get('experiment',{}).get('parameter')!=config['experiment']['parameter']:
        raise ValueError('simulated intervention differs from published config')
    def pairs(frame,required=True):
        if 'contacts' not in frame and required:raise ValueError('native contact telemetry missing')
        return sorted({tuple(sorted([c['entity_a'],c['entity_b']])) for c in frame.get('contacts',[])})
    # Original renderer's pre_static_frames contain poses without contact telemetry.
    # That missing field is not evidence of no contact; final physics frame is required.
    initial_available='contacts' in frames[9]
    if not initial_available and config['render'].get('pre_static_frames',0)<=9:raise ValueError('initial physics frame lacks contacts')
    initial,final=pairs(frames[9],required=initial_available),pairs(frames[-1]);initial_set={frozenset(p) for p in initial};final_set={frozenset(p) for p in final}
    template=config['experiment'].get('template_id','T09')
    if template!='T09':
        metrics={}
        for name in config['experiment']['tracked_objects']:
            track=[next(o for o in f['objects'] if o['name']==name) for f in frames];initial_pose=track[0]
            positions=[o['position'] for o in track]
            if any(not math.isfinite(x) for p in positions for x in p):raise ValueError('nonfinite simulated position')
            q=initial_pose['quaternion_xyzw']
            def angle(o):
                other=o['quaternion_xyzw'];den=math.sqrt(sum(x*x for x in q)*sum(x*x for x in other))
                return math.degrees(2*math.acos(min(1.,abs(sum(a*b for a,b in zip(q,other)))/den)))
            metrics[name]=dict(initial_position=positions[0],final_position=positions[-1],max_displacement_m=max(math.dist(positions[0],p) for p in positions),max_rotation_deg=max(angle(o) for o in track))
        return dict(initial_pairs=initial,initial_contact_telemetry_available=initial_available,final_pairs=final,tracked_metrics=metrics,
            target_event=None,event_status='continuous_measurements_only_no_new_event_threshold')
    names=config['experiment']['supported_book_names']
    if any(frozenset(['frozen_tabletop_collision_slab',n]) in initial_set for n in names):
        raise ValueError('upper book touches table before intervention')
    affected=[n for n in names if frozenset(['frozen_tabletop_collision_slab',n]) in final_set]
    return dict(initial_pairs=initial,initial_contact_telemetry_available=initial_available,final_pairs=final,target_event=EVENT,label=int(bool(affected)),upper_books_on_table=affected)


def main():
    import fcntl
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--root',required=True);parser.add_argument('--gpu',default='4');parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text());jobs=jobs[:args.limit or None]
    renderer=PROJECT/'scripts/render_sample.py'
    sources={str(p):sha(p.read_bytes()) for p in [renderer,PROJECT/'scripts/render_t06_t10_physics_v2.py',PROJECT/'scripts/render_base_physical_v5.py']}
    config_root=PROJECT/'configs'/root.name;config_root.mkdir(exist_ok=True);results=[]
    for job in jobs:
        sid=job['sample_id'];folder=root/sid;folder.mkdir(exist_ok=True);receipt=folder/'result.json'
        try:
            if any(sha(Path(path).read_bytes())!=value for path,value in sources.items()):raise ValueError('original backend changed during batch')
            if receipt.exists():
                row=json.loads(receipt.read_text())
                if row['backend_sources']!=sources or row['source_config_sha256']!=job['sha256']:raise ValueError('replay source changed')
                raw=gzip.decompress(Path(row['state_path']).read_bytes())
                if sha(raw)!=row['state_sha256']:raise ValueError('cached state changed')
                if sha((config_root/(sid+'.json')).read_bytes())!=row['replay_config_sha256']:raise ValueError('cached replay config changed')
            else:
                while True:
                    if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('disk reserve below 20GiB')
                    free=float(subprocess.check_output(['nvidia-smi','-i',args.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode().strip())
                    if free>=12*1024:break
                    save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=args.gpu,planned=len(jobs)));time.sleep(20)
                c=copy.deepcopy(job['config']);r=c['render'];r.update(resolution=[160,96],raytracing_spp=1,render_backend='raster')
                for key in ['save_video','save_first_rgb','save_last_rgb']:
                    if r.get(key):r[key]=str(folder/Path(r[key]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(folder/'physics.json')
                cp=config_root/(sid+'.json');save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0')
                lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib'
                env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                save(root/'resource_status.json',dict(status='running',gpu=args.gpu,planned=len(jobs),sample_id=sid))
                with (folder/'run.log').open('w') as log:run=subprocess.run([PYTHON,str(renderer),'--config',str(cp)],cwd=PROJECT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
                raw=(folder/'physics.json').read_bytes();state=json.loads(raw);measured=validate_state(job['config'],state)
                log_text=(folder/'run.log').read_text(errors='replace')
                if run.returncode and 'validate_rendered_video' not in log_text:raise RuntimeError('renderer failed before independent visual post-check')
                compressed=gzip.compress(raw,compresslevel=3,mtime=0);dest=folder/'physics.json.gz';dest.write_bytes(compressed)
                if sha(gzip.decompress(dest.read_bytes()))!=sha(raw):raise ValueError('lossless compression failed')
                if root.resolve() not in (folder/'physics.json').resolve().parents:raise ValueError('state outside task root')
                (folder/'physics.json').unlink()
                row=dict(sample_id=sid,scene_id=job['scene_id'],status='supplemental_original_backend_state',reference_origin='supplemental_replay_not_original_annotation',
                    source_revision=job['revision'],source_config_sha256=job['sha256'],replay_config_sha256=sha(cp.read_bytes()),seed=c['seed'],
                    state_path=str(dest),state_sha256=sha(raw),stored_state_sha256=sha(compressed),backend_sources=sources,renderer_returncode=run.returncode,
                    visual_postcheck_independent=bool(run.returncode),**measured)
                save(receipt,row)
        except Exception as exc:row=dict(sample_id=sid,status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results);print(json.dumps(dict(done=len(results),sample_id=sid,status=row['status'],error=row.get('error'))),flush=True)
    save(root/'resource_status.json',dict(status='completed',planned=len(jobs),completed=sum(r['status']=='supplemental_original_backend_state' for r in results),failed=sum(r['status']=='failed' for r in results)))


if __name__=='__main__':main()
