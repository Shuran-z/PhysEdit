"""Render a new, explicitly versioned T16 reference with synchronous native truth."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from t12_contact_replay_worker import acquire,save
from t16_reference_geometry import folder_support_clearance


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser()
    for n in ['plan','root','python']:p.add_argument('--'+n,required=True)
    a=p.parse_args();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(root/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=json.loads(Path(a.plan).read_text());raw=Path(job['config_path']).read_bytes();assert sha(raw)==job['config_sha256']
    for path,digest in job['backend_sources'].items():assert sha(Path(path).read_bytes())==digest
    c=json.loads(raw);assert c['seed']==job['simulation_seed'] and not folder_support_clearance(c)['intersects']
    c['render']['save_video']=str(root/'video.mp4');c['render']['save_first_rgb']=str(root/'initial.png');c['render']['save_last_rgb']=str(root/'last.png')
    c['annotations']['save_path']=str(root/'state.json');save(root/'render_input_config.json',c)
    gpu,lease=acquire(root);env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    lib=a.python.rsplit('/bin/',1)[0]+'/lib';env['LD_LIBRARY_PATH']=lib+'/python3.10/site-packages/nvidia/cu13/lib:'+lib+':'+env.get('LD_LIBRARY_PATH','')
    save(root/'resource_status.json',dict(status='rendering_new_v4_reference',clip_id=job['clip_id'],gpu=gpu))
    with (root/'run.log').open('wb')as log:
        try:run=subprocess.run([a.python,job['renderer'],'--config',str(root/'render_input_config.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
        finally:lease.close()
    if run.returncode:raise RuntimeError('Reference render failed; no admission: '+str(root/'run.log'))
    state_raw=(root/'state.json').read_bytes();state=json.loads(state_raw);fs=state['frames'];assert len(fs)==210
    assert all('contacts'in f for f in fs if f['frame_index']>=c['render']['pre_static_frames'])
    selected=[f for f in fs if 4<=f['frame_index']<=154];assert len(selected)==151
    hits=[(f['frame_index'],k.get('physics_step_index',-1))for f in selected for k in f.get('contacts',[])if {k.get('entity_a'),k.get('entity_b')}=={'t16_folder','t16_downstream_box'}]
    start={o['name']:o['position']for o in selected[0]['objects']};end={o['name']:o['position']for o in selected[-1]['objects']};disp={n:math.dist(start[n],end[n])for n in start}
    ffmpeg='/usr/local/bin/ffmpeg'
    subprocess.run([ffmpeg,'-v','error','-i',str(root/'video.mp4'),'-vf',r'select=eq(n\,4)','-vsync','0','-frames:v','1','-y',str(root/'condition.png')],check=True)
    video_raw=(root/'video.mp4').read_bytes();condition_raw=(root/'condition.png').read_bytes()
    contacts=[k for f in fs for k in f.get('contacts',[])];depths=[k['penetration_m']for k in contacts if 'penetration_m'in k]
    finite=all(math.isfinite(v)for f in fs for o in f['objects']for v in o['position'])
    free={o['name']for o in c['dynamic_objects']if not o.get('fixed',False)}
    manual=sum(bool(o.get('motion',{}).get('manual_pose'))for f in fs if f['frame_index']>=c['render']['pre_static_frames']for o in f['objects']if o['name']in free)
    physical_pass=finite and manual==0 and bool(depths)and len(depths)==len(contacts)and max(depths)<=.001
    receipt=dict(schema='t16-reference-repair-candidate-v1',clip_id=job['clip_id'],reference_simulation_seed=c['seed'],gpu=gpu,
                 frozen_v6_files_unchanged=True,official_input_replacement_applied=False,
                 draft_input_changes=job.get('declared_parameter_changes'),old_reference_retained=True,repair_geometry=job['geometry'],
                 state_sha256=sha(state_raw),video_sha256=sha(video_raw),condition_image_sha256=sha(condition_raw),
                 render_input_config_sha256=sha((root/'render_input_config.json').read_bytes()),
                 native_frames=210,native_fps=30.,condition_frame_index=4,horizon_s=5.,reference_end_frame=154,
                 source_event_labels=dict(folder_downstream_contact=int(bool(hits)),downstream_response_original=int(disp['t16_downstream_box']>.015),folder_motion_original=int(disp['t16_folder']>.08)),
                 contact_first=min(hits)if hits else None,source_final_displacements_m=disp,
                 source_truth_origin='RGB, poses and native contacts recorded in this same simulation, not transferred from the old video',
                 physical_QA=dict(passed=physical_pass,max_native_penetration_m=max(depths)if depths else None,gate_m=.001,states_finite=finite,free_body_manual_pose_steps=manual),
                 reference_admitted=False,pair_admitted=False,status='rendered_candidate_requires_release_binding_and_generation_rerun'if physical_pass else'rendered_candidate_physical_QA_failed',backend_sources=job['backend_sources'])
    (root/'state.json.gz').write_bytes(gzip.compress(state_raw,compresslevel=3,mtime=0));save(root/'receipt.json',receipt)
    save(root/'resource_status.json',dict(status='finished',clip_id=job['clip_id'],video_sha256=receipt['video_sha256']))


if __name__=='__main__':main()
