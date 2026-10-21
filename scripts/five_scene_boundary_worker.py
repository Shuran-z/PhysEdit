"""Fair original-backend refinement queue for T01/T04/T05/T08/T11."""
import argparse
import copy
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
    from scripts.five_scene_boundary_rules import intervene,event
except ModuleNotFoundError:
    from five_scene_boundary_rules import intervene,event

PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def isolate(value,folder):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ['save_video','save_first_rgb','save_last_rgb','save_path'] and isinstance(item,str):value[key]=str(folder/Path(item).name)
            else:isolate(item,folder)
    elif isinstance(value,list):
        for item in value:isolate(item,folder)


def numeric_render(config, backend):
    if backend not in ['raster','original']:raise ValueError('unsupported numeric rendering backend')
    config['render'].update(write_video=False,resolution=[160,96],raytracing_spp=1)
    if backend=='raster':
        config['render']['render_backend']='raster';config['scene_overrides']['raytracing']=False


def main():
    import fcntl
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--root',required=True);parser.add_argument('--gpu',default='0');parser.add_argument('--limit',type=int,default=0);parser.add_argument('--endpoints-only',action='store_true');parser.add_argument('--published-endpoint-replay',action='store_true');parser.add_argument('--python',default=PYTHON);parser.add_argument('--minimum-free-memory-mib',type=int,default=12288);parser.add_argument('--render-backend',choices=['raster','original'],default='raster');parser.add_argument('--renderer-bootstrap');args=parser.parse_args()
    if args.minimum_free_memory_mib<2048:parser.error('numeric execution requires at least 2048 MiB of free-memory headroom')
    if args.published_endpoint_replay and not args.endpoints_only:parser.error('published endpoint replay is diagnostic only; requires --endpoints-only')
    root=Path(args.root);root.mkdir(exist_ok=True,parents=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=json.loads(Path(args.plan).read_text());jobs=jobs[:args.limit or None];results=[]
    execution_sources={str(p):sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('five_scene_boundary_rules.py')]}
    if args.renderer_bootstrap:execution_sources[args.renderer_bootstrap]=sha(Path(args.renderer_bootstrap).read_bytes())
    for job in jobs:
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);rp=folder/'result.json';probes=[]
        try:
            sources={p:sha(Path(p).read_bytes()) for p in job['backend_sources']}
            if sources!=job['backend_sources']:raise ValueError('original backend sources changed')
            if any(sha(Path(p).read_bytes())!=v for p,v in execution_sources.items()):raise ValueError('measurement/intervention code changed during batch')
            if rp.exists():
                r=json.loads(rp.read_text())
                if r['backend_sources']!=sources or r.get('execution_sources')!=execution_sources:raise ValueError('cached backend or measurement code changed')
                results.append(r);save(root/'status.json',results);continue
            intervene(job,sum(job['bracket'])/2)
            auditor=None
            if job['scene_id']=='T01':
                path=job['auditor'];spec=importlib.util.spec_from_file_location('original_t01_rule',path);auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);receipt=dest/'receipt.json'
                if receipt.exists():
                    r=json.loads(receipt.read_text());stored=Path(r['state_path']).read_bytes()
                    if r.get('execution_sources')!=execution_sources:raise ValueError('cached measurement code changed')
                    if sha(stored)!=r['stored_state_sha256'] or sha(gzip.decompress(stored))!=r['state_sha256']:raise ValueError('cached numeric state changed')
                    if sha((dest/'config.json').read_bytes())!=r['config_sha256']:raise ValueError('cached numeric config changed')
                    return r
                while True:
                    if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('disk reserve below 20GiB')
                    free=float(subprocess.check_output(['nvidia-smi','-i',args.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode().strip())
                    if free>=args.minimum_free_memory_mib:break
                    save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=args.gpu,minimum_free_memory_mib=args.minimum_free_memory_mib));time.sleep(20)
                c=copy.deepcopy(next(e['config'] for e in job['endpoints'] if e['theta']==theta)) if args.published_endpoint_replay else intervene(job,theta)
                isolate(c['render'],dest);isolate(c['annotations'],dest)
                numeric_render(c,args.render_backend)
                sp=dest/'physics.json';c['annotations']['save_path']=str(sp);cp=dest/'config.json';save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0')
                lib='/home/wangzijun_p25/miniconda3/envs/genesis/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                command=[args.python]+([args.renderer_bootstrap] if args.renderer_bootstrap else [])+[job['renderer'],'--config',str(cp)]
                if job['scene_id']=='T11':command.append('--strict-live-physics')
                with (dest/'run.log').open('w') as log:run=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                if run.returncode:raise RuntimeError('original renderer failed (exit '+str(run.returncode)+'); '+str(dest/'run.log'))
                raw=sp.read_bytes();state=json.loads(raw)
                if len(state['frames'])!=210 or any(not math.isfinite(v) for f in state['frames'] for o in f['objects'] for v in o['position']):raise ValueError('incomplete/nonfinite state')
                specs={o['name']:o['spec'] for o in state['dynamic_objects']};expected={o['name']:o for o in c['dynamic_objects']}
                if specs!=expected:raise ValueError('renderer changes configured object specs')
                if auditor:
                    audit=auditor.analyze(sp);label=int(audit['outcome_label']=='full_chain') if job['family_id']=='C' else int(audit['stage_frames']['book_can_1' if job['family_id']=='A' else 'can_1_can_2'] is not None)
                else:label=event(c,state,job['target_event'])
                dest_state=dest/'physics.json.gz';compressed=gzip.compress(raw,compresslevel=3,mtime=0);dest_state.write_bytes(compressed)
                if sha(gzip.decompress(compressed))!=sha(raw):raise ValueError('state compression failed')
                if root.resolve() not in sp.resolve().parents:raise ValueError('generated output outside task root')
                sp.unlink()
                r=dict(theta=theta,label=label,state_path=str(dest_state),state_sha256=sha(raw),stored_state_sha256=sha(compressed),config_sha256=sha(cp.read_bytes()),backend_sources=sources,execution_sources=execution_sources)
                save(receipt,r);return r
            a,b=job['bracket'];ends=[evaluate(a),evaluate(b)];probes.extend(ends)
            save(folder/'endpoint_checks.json',[dict(theta=r['theta'],expected=e['label'],actual=r['label'],matches=r['label']==e['label']) for r,e in zip(ends,job['endpoints'])])
            if [r['label'] for r in ends]!=[e['label'] for e in job['endpoints']]:raise ValueError('published endpoint event not reproduced; both endpoint states retained')
            if ends[0]['label']==ends[1]['label']:raise ValueError('source endpoints do not bracket an event change')
            if args.endpoints_only:
                row=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],status='source_endpoints_checked',backend_sources=sources,execution_sources=execution_sources,probes=probes)
                results.append(row);save(root/'status.json',results);print(json.dumps(dict(scene=job['scene_id'],status=row['status'])),flush=True);continue
            while b-a>job['tolerance']:
                mid=(a+b)/2;r=evaluate(mid);probes.append(r)
                if r['label']==ends[0]['label']:a=mid
                else:b=mid
            row=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],target_event=job['target_event'],status='refined_local_interval',
                bracket=[a,b],source_bracket=job['bracket'],backend_sources=sources,endpoint_labels=[r['label'] for r in ends],
                source_state_sha256=[e['state_sha256'] for e in job['endpoints']],probes=probes,execution_sources=execution_sources,scope='named conditional local interval; original source labels retained separately')
            row['conditional_seed_endpoint']=job.get('seed_endpoint',0)
            save(rp,row)
        except Exception as exc:row=dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],status='failed',error=str(exc),probes=probes)
        results.append(row);save(root/'status.json',results);save(root/'resource_status.json',dict(status='running',planned=len(jobs),completed=len(results),scene_id=job['scene_id'],gpu=args.gpu))
        print(json.dumps(dict(done=len(results),scene=job['scene_id'],status=row['status'],error=row.get('error'))),flush=True)
    save(root/'resource_status.json',dict(status='completed',planned=len(jobs),failed=sum(r['status']=='failed' for r in results)))


if __name__=='__main__':main()
