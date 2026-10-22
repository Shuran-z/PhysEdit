"""Scan remaining T12 slices without substituting new labels for published truth."""
import argparse,copy,gzip,hashlib,json,math,os,shutil,subprocess,time
from pathlib import Path
try:
    from scripts.t12_original_boundary_worker import set_parameter,PYTHON
except ModuleNotFoundError:
    from t12_original_boundary_worker import set_parameter,PYTHON


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value));tmp.replace(path)


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--root',required=True);p.add_argument('--source',required=True);p.add_argument('--gpu',required=True);args=p.parse_args()
    root=Path(args.root);root.mkdir(exist_ok=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    source=Path(args.source);renderer=source/'12_render_motion_sequence.py';backend_hash=hashlib.sha256(renderer.read_bytes()).hexdigest();results=[]
    for job in json.loads(Path(args.plan).read_text()):
        folder=root/job['job_id'];folder.mkdir(exist_ok=True);final=folder/'result.json'
        if final.exists():results.append(json.loads(final.read_text()));save(root/'status.json',results);continue
        probes={}
        try:
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);rp=dest/'receipt.json'
                if rp.exists():
                    v=json.loads(rp.read_text());stored=Path(v['state_path']).read_bytes()
                    if v['backend_sha256']!=backend_hash or hashlib.sha256((dest/'config.json').read_bytes()).hexdigest()!=v['config_sha256'] or hashlib.sha256(stored).hexdigest()!=v['stored_state_sha256'] or hashlib.sha256(gzip.decompress(stored)).hexdigest()!=v['state_sha256']:raise ValueError('cached probe changed')
                    probes[theta]=v;return v
                while True:
                    if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('disk reserve below 20GiB')
                    free=float(subprocess.check_output(['nvidia-smi','-i',args.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())
                    if free>=8192:break
                    save(root/'resource_status.json',dict(status='waiting_for_memory',gpu=args.gpu,minimum_free_memory_mib=8192));time.sleep(20)
                save(root/'resource_status.json',dict(status='running_original_grid',gpu=args.gpu,job_id=job['job_id'],theta=theta))
                c=set_parameter(job['base_config'],job['axis'],theta);render=c['render'];render.update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1,use_native_recording=False,camera_outputs=[])
                for k in ['save_video','save_first_rgb','save_last_rgb']:
                    if k in render:render[k]=str(dest/Path(render[k]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(dest/'physics.json');cp=dest/'config.json';save(cp,c)
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu,TI_OFFLINE_CACHE='0');lib=PYTHON.rsplit('/bin/python',1)[0]+'/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
                with (dest/'run.log').open('w') as log:run=subprocess.run([PYTHON,str(renderer),'--config',str(cp)],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                if run.returncode:raise RuntimeError('original renderer failed: '+str(dest/'run.log'))
                raw=(dest/'physics.json').read_bytes();state=json.loads(raw);positions=[next(o['position'] for o in f['objects'] if o['name']=='t12_tissue_box') for f in state['frames']]
                if len(positions)!=210 or any(not math.isfinite(x) for point in positions for x in point):raise ValueError('invalid trajectory')
                maximum=max(math.dist(positions[0],point) for point in positions);stored=gzip.compress(raw,compresslevel=3,mtime=0);sp=dest/'physics.json.gz';sp.write_bytes(stored)
                if gzip.decompress(stored)!=raw:raise ValueError('state compression changed bytes')
                (dest/'physics.json').unlink();v=dict(theta=theta,label=int(maximum>=.01),max_displacement_m=maximum,backend_sha256=backend_hash,config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),state_path=str(sp),stored_state_sha256=hashlib.sha256(stored).hexdigest(),state_sha256=hashlib.sha256(raw).hexdigest())
                save(rp,v);probes[theta]=v;return v
            for m in job['members']:
                if evaluate(m['theta'])['label']!=m['reference_label']:raise ValueError('published member event did not reproduce')
            observations=[evaluate(theta) for theta in job['grid']];intervals=[]
            for left,right in zip(observations,observations[1:]):
                if left['label']==right['label']:continue
                a,b=left['theta'],right['theta'];tol=.001 if job['axis']=='speed' else .0005
                while b-a>tol:
                    mid=(a+b)/2
                    if evaluate(mid)['label']==left['label']:a=mid
                    else:b=mid
                intervals.append(dict(bracket=[a,b],labels=[left['label'],right['label']]))
            row=dict(job_id=job['job_id'],status='remaining_grid_completed',axis=job['axis'],fixed_context_sha256=job['fixed_context_sha256'],intervals=intervals,probes=list(probes.values()),backend_sha256=backend_hash,member_reference_state_sha256=[m['state_sha256'] for m in job['members']],scope=job['reference_kind'])
            save(final,row)
        except Exception as exc:row=dict(job_id=job['job_id'],axis=job['axis'],status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results);print(json.dumps(dict(done=len(results),status=row['status'],error=row.get('error'))),flush=True)
    save(root/'resource_status.json',dict(status='finished',gpu=args.gpu))


if __name__=='__main__':main()
