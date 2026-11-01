"""Solve local T12 contact brackets for exact Core100 contexts, without new videos."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
from t12_contact_replay_worker import acquire, save, sha
from t12_contact_readback import instrument, ORIGINAL_SHA256


def main():
    p=argparse.ArgumentParser()
    for name in ['plan','root','source','python']:p.add_argument('--'+name,required=True)
    a=p.parse_args();root=Path(a.root);root.mkdir(exist_ok=True,parents=True)
    import fcntl
    lock=(root/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    renderer=Path(a.source)/'12_render_motion_sequence_contact_v1.py'
    original=(Path(a.source)/'12_render_motion_sequence.py').read_bytes()
    assert sha(original)==ORIGINAL_SHA256 and renderer.read_bytes()==instrument(original)
    results=[]
    for job in json.loads(Path(a.plan).read_text()):
        folder=root/job['clip_id'];folder.mkdir(exist_ok=True);final=folder/'result.json'
        if final.exists():results.append(json.loads(final.read_text()));save(root/'status.json',results);continue
        try:
            raw=Path(job['source_config_path']).read_bytes();assert sha(raw)==job['source_config_sha256'];base=json.loads(raw)
            anchor_raw=gzip.decompress(Path(job['anchor_state']).read_bytes());assert sha(anchor_raw)==job['anchor_state_sha256']
            probes={}
            def labels(state):
                fs=state['frames'];assert len(fs)==210 and all(f.get('contact_telemetry_complete')is True for f in fs)
                return int(any(f.get('contacts') for f in fs if 4<=f['frame_index']<=154))
            anchor=labels(json.loads(anchor_raw));assert anchor==job['reference_label']
            def evaluate(theta):
                if theta==job['theta']:
                    return {'theta':theta,'label':anchor,'state_sha256':job['anchor_state_sha256'],'source':'hash-checked anchor replay; source-reference witness separately verified'}
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);receipt=dest/'receipt.json'
                if receipt.exists():
                    v=json.loads(receipt.read_text());b=gzip.decompress(Path(v['state_path']).read_bytes());assert sha(b)==v['state_sha256'];assert sha((dest/'config.json').read_bytes())==v['config_sha256'];probes[theta]=v;return v
                c=copy.deepcopy(base);actors={o['name']:o for o in c['dynamic_objects']};actors['t12_stapler']['motion']['initial_velocity'][0]=theta
                c['t12_parameters']['stapler_initial_velocity_mps'][0]=theta
                c['experiment']['controlled_physics']['stapler']['initial_velocity_mps'][0]=theta
                render=c['render'];render.update(write_video=False,render_backend='raster',resolution=[160,96],raytracing_spp=1,use_native_recording=False,camera_outputs=[])
                for k in ['save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir']:
                    if render.get(k):render[k]=str(dest/Path(render[k]).name)
                c['scene_overrides']['raytracing']=False;c['annotations']['save_path']=str(dest/'physics.json');save(dest/'config.json',c)
                gpu,lease=acquire(root);env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
                lib=a.python.rsplit('/bin/',1)[0]+'/lib/python3.10/site-packages/nvidia/cu13/lib';env['LD_LIBRARY_PATH']=lib+(':'+env['LD_LIBRARY_PATH']if env.get('LD_LIBRARY_PATH')else'')
                save(root/'resource_status.json',{'status':'running_contact_boundary_probe','clip_id':job['clip_id'],'theta':theta,'gpu':gpu})
                with(dest/'run.log').open('wb')as log:
                    try:run=subprocess.run([a.python,str(renderer),'--config',str(dest/'config.json')],cwd=a.source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                    finally:lease.close()
                if run.returncode:raise RuntimeError('probe failed: '+str(dest/'run.log'))
                b=(dest/'physics.json').read_bytes();label=labels(json.loads(b));statepath=dest/'physics.json.gz';statepath.write_bytes(gzip.compress(b,compresslevel=3,mtime=0))
                v={'theta':theta,'label':label,'state_path':str(statepath),'state_sha256':sha(b),'config_sha256':sha((dest/'config.json').read_bytes()),'renderer_sha256':sha(renderer.read_bytes())};save(receipt,v);probes[theta]=v;return v
            # One opposite-label local bracket, not a claim of global monotonicity.
            lo=0.0 if anchor else job['theta'];hi=job['theta']if anchor else 2.35
            left=evaluate(lo);right=evaluate(hi)
            if left['label']==right['label']:
                row={'clip_id':job['clip_id'],'status':'no_opposite_endpoints_in_registered_search_range','range':[lo,hi],'labels':[left['label'],right['label']]}
            else:
                while hi-lo>.001:
                    mid=(lo+hi)/2;probe=evaluate(mid)
                    if probe['label']==left['label']:lo=mid
                    else:hi=mid
                row={'clip_id':job['clip_id'],'status':'local_contact_bracket_completed','target_event':'stapler_contacts_tissue_box','horizon_s':5.,'parameter':'stapler_initial_speed_mps','bracket':[lo,hi],'labels':[left['label'],right['label']],'source_theta':job['theta'],'source_config_sha256':job['source_config_sha256'],'fixed_context_sha256':job['fixed_context_sha256'],'normalization_domain':[.85,2.35],'normalization_span':1.5,'search_may_extend_below_published_domain':True,'scope':'Exact source-seed conditional speed slice; one observed local interval, no global uniqueness assertion; no cross-case PairAcc admission'}
            row['probes']=list(probes.values());save(final,row)
        except Exception as exc:row={'clip_id':job['clip_id'],'status':'failed','error':str(exc)}
        results.append(row);save(root/'status.json',results)
    save(root/'resource_status.json',{'status':'finished','registered':len(results)})


if __name__=='__main__':main()
