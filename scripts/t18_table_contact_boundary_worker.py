"""Conditional T18 searches using published configurations and original renderer.

Table contact is measured from native contacts on the declared support plane,
not from center-height loss. It is a named endpoint event, not a universal
collapse classifier (a coherently resettled stack must be described separately).
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import functools
import types
import gzip
import time

PROJECT=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1')
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
EVENT='upper_nonpulled_book_on_table_at_end'


def table_event(config,frame):
    if 'contacts' not in frame:raise ValueError('native final contact telemetry absent')
    e=config['experiment'];supported=set(e['supported_book_names']);actors={o['name'] for o in config['dynamic_objects']}
    evidence=[]
    for c in frame['contacts']:
        names={c['entity_a'],c['entity_b']};upper=names&supported
        if len(upper)!=1 or not names-actors:continue
        # Numerical tolerance classifies an existing collision's surface. It
        # never creates a collision from a small object-height displacement.
        tol=abs(c.get('penetration_m',0))+.0001
        if abs(c['position'][2]-e['surface_z'])<=tol:
            evidence.append(dict(book=next(iter(upper)),surface_entity=next(iter(names-actors)),
                                 position=c['position'],penetration_m=c.get('penetration_m'),surface_tolerance_m=tol))
    books=sorted({c['book'] for c in evidence})
    return dict(label=int(bool(books)),upper_books_on_table=books,contact_evidence=evidence,
                event_scope='specified upper-book table contact; coherent resettling versus scattering is not inferred from contact alone')


@functools.lru_cache(maxsize=3)
def builder(version='v5'):
    paths={'v5':PROJECT/'scripts/build_project.py',
        'v3':PROJECT/'backups/expansive_motion_v4_20260823_174934/scripts/build_project.py',
        'v4':PROJECT/'backups/grounded_multibody_v5_20260823_1930/scripts/build_project.py'}
    path=paths[version]
    if version=='v5':
        spec=importlib.util.spec_from_file_location('t18_original_builder',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    else:
        # Archived source moved deeper in the tree. Relocate only its project
        # root; preserve the archived geometry/variant formulas byte-for-byte.
        source=path.read_text();old='PROJECT = Path(__file__).resolve().parents[1]'
        if source.count(old)!=1:raise ValueError('unknown archived builder root declaration')
        source=source.replace(old,'PROJECT = Path('+repr(str(PROJECT))+')',1)
        module=types.ModuleType('t18_original_'+version);module.__file__=str(path)
        exec(compile(source,str(path),'exec'),module.__dict__)
    module.original_source_path=path
    return module,module.load_backgrounds()


def change(config,theta,build=None,backgrounds=None):
    c=copy.deepcopy(config);e=c['experiment'];axis=e['parameter']['parameter_name']
    if axis=='contact_friction':
        for obj in c['dynamic_objects']:
            if obj['name'].startswith('t18_book_'):
                obj['friction']=theta
                if 'friction' in obj.get('material_preset',{}):obj['material_preset']['friction']=theta
        e['static_friction']=e['dynamic_friction']=theta
    elif axis=='overlap_length':
        version=e.get('event_variant_version','')
        if 'v3_' in version:build,backgrounds=builder('v3')
        elif 'v4_' in version:build,backgrounds=builder('v4')
        elif 'grounded_multibody' in version:
            if build is None:build,backgrounds=builder()
        else:raise ValueError('original overlap recipe for this version not recovered')
        objects,meta=build.scene_objects('T18',axis,theta,backgrounds[e['background_id']],c['sample_id'])
        if meta['event_variant_id']!=e['event_variant_id']:raise ValueError('builder changes fixed topology')
        c['dynamic_objects']=objects;e.update(meta)
    else:raise ValueError('original overlap recipe for this version not recovered')
    e['parameter']['parameter_value']=theta
    return c


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)


def wait_for_resources(root,gpu):
    while True:
        if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('disk reserve below 20GiB')
        free=float(subprocess.check_output(['nvidia-smi','-i',str(gpu),'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode().strip())
        if free>=12*1024:return
        save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=gpu,free_memory_mib=free,minimum_free_memory_mib=12288))
        time.sleep(20)


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--root',required=True);p.add_argument('--gpu',default='2');p.add_argument('--limit',type=int,default=0);p.add_argument('--source-only',action='store_true')
    p.add_argument('--renderer-timeout-seconds',type=int,default=600)
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    if not 600<=args.renderer_timeout_seconds<=7200:p.error('renderer timeout must be between 600 and 7200 seconds')
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text());jobs=jobs[:args.limit or None];results=[];build,bgs=builder()
    backend=PROJECT/'scripts/render_sample.py';baseline_hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [backend,PROJECT/'scripts/build_project.py',PROJECT.parent/'scripts/render_t16_t20_physical_v5_20260816.py']}
    for job in jobs:
        source_hashes=dict(baseline_hashes)
        exp=job['base_config']['experiment'];version=exp.get('event_variant_version','')
        if exp['parameter']['parameter_name']=='overlap_length' and ('v3_' in version or 'v4_' in version):
            legacy,_=builder('v3' if 'v3_' in version else 'v4');path=legacy.original_source_path
            source_hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);rp=folder/'result.json'
        if rp.exists():
            cached=json.loads(rp.read_text())
            if cached['backend_sources']!=source_hashes or cached['reference_state_sha256']!=job['reference_state_sha256']:raise ValueError('cached job source changed')
            results.append(cached);save(root/'status.json',results);continue
        probes=[]
        try:
            base=job['base_config'];axis=base['experiment']['parameter']['parameter_name'];original_theta=base['experiment']['parameter']['parameter_value']
            if change(base,original_theta,build,bgs)['dynamic_objects']!=base['dynamic_objects']:raise ValueError('original parameter does not reconstruct actual objects')
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);receipt=dest/'receipt.json'
                if receipt.exists():
                    cached=json.loads(receipt.read_text())
                    if cached['backend_sources']!=source_hashes:raise ValueError('cached probe backend changed')
                    if hashlib.sha256((dest/'config.json').read_bytes()).hexdigest()!=cached['config_sha256']:raise ValueError('cached config bytes changed')
                    state_path=Path(cached['state_path']);stored=state_path.read_bytes()
                    raw=gzip.decompress(stored) if state_path.suffix=='.gz' else stored
                    if hashlib.sha256(raw).hexdigest()!=cached['state_sha256']:raise ValueError('cached state bytes changed')
                    return cached
                wait_for_resources(root,args.gpu)
                c=change(base,theta,build,bgs);render=c['render'];render.update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1,use_native_recording=False)
                for key in ['save_video','save_first_rgb','save_last_rgb']:
                    if render.get(key):render[key]=str(dest/Path(render[key]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(dest/'physics.json');cp=dest/'config.json';save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0');lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                with (dest/'run.log').open('w') as log:run=subprocess.run([PYTHON,str(backend),'--config',str(cp)],cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=args.renderer_timeout_seconds)
                if run.returncode:raise RuntimeError('original renderer failed: '+str(dest/'run.log'))
                raw=(dest/'physics.json').read_bytes();state=json.loads(raw)
                if len(state['frames'])!=210:raise ValueError('incomplete state')
                compressed=gzip.compress(raw,compresslevel=3,mtime=0);stored=dest/'physics.json.gz';stored.write_bytes(compressed)
                if hashlib.sha256(gzip.decompress(stored.read_bytes())).digest()!=hashlib.sha256(raw).digest():raise ValueError('lossless state compression failed')
                if root.resolve() not in (dest/'physics.json').resolve().parents:raise ValueError('generated state outside task root')
                (dest/'physics.json').unlink()
                result=dict(theta=theta,**table_event(c,state['frames'][-1]),config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(raw).hexdigest(),stored_state_sha256=hashlib.sha256(compressed).hexdigest(),state_path=str(stored),backend_sources=source_hashes)
                save(receipt,result);return result
            source=evaluate(original_theta);probes.append(source)
            if source['label']!=job['reference_label']:raise ValueError('published source event did not reproduce')
            if args.source_only:
                row=dict(job_id=job['job_id'],sample_id=job['sample_id'],status='source_event_reproduced',probe=source)
                results.append(row);save(root/'status.json',results);print(json.dumps(dict(sample_id=job['sample_id'],status=row['status'])),flush=True);continue
            grid=job['original_grid'];neighbors=[]
            for direction in [-1,1]:
                values=sorted([x for x in grid if (x-original_theta)*direction>0],reverse=direction<0);previous=source
                for theta in values:
                    trial=evaluate(theta);probes.append(trial)
                    if trial['label']!=source['label']:
                        a,b=sorted([previous['theta'],theta]);left=evaluate(a);right=evaluate(b)
                        while b-a>.0005:
                            mid=(a+b)/2;r=evaluate(mid);probes.append(r)
                            if r['label']==left['label']:a=mid
                            else:b=mid
                        neighbors.append(dict(bracket=[a,b],labels=[left['label'],right['label']],direction=direction));break
                    previous=trial
            row=dict(job_id=job['job_id'],sample_id=job['sample_id'],status='conditional_event_search_completed',target_event=EVENT,
                     local_intervals=neighbors,probes=probes,backend_sources=source_hashes,source_seed=base['seed'],reference_state_sha256=job['reference_state_sha256'],
                     scope='first observed transition on either side along original grid, refined at fixed published topology and seed; hidden between-grid transitions not ruled out')
            save(rp,row)
        except Exception as exc:row=dict(job_id=job['job_id'],sample_id=job['sample_id'],status='failed',error=str(exc),probes=probes)
        results.append(row);save(root/'status.json',results);print(json.dumps(dict(done=len(results),status=row['status'],sample_id=job['sample_id'],error=row.get('error'))),flush=True)


if __name__=='__main__':main()
