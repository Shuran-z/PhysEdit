"""Source-only paired impact audit. Never edits released prompts or model videos.

Each original/repaired pair runs on the same leased GPU, with the same seed,
solver and render profile. Only the support-book x geometry is changed in B.
"""
import argparse
import copy
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


def layout(c):
    objects={o['name']:o for o in c['dynamic_objects']};a=objects['t16_folder'];b=objects['t16_support_book']
    span=math.cos(math.radians(abs(a['pose']['euler_xyz'][1])))*a['size'][0]
    return (b['pose']['position'][0]-b['size'][2]/2-.002-(a['pose']['position'][0]-span/2))/span


def measure(state):
    fs=[f for f in state['frames']if 4<=f['frame_index']<=154];assert len(fs)==151
    hits=[(f['frame_index'],c.get('physics_step_index',-1))for f in fs for c in f.get('contacts',[])if{c.get('entity_a'),c.get('entity_b')}=={'t16_folder','t16_downstream_box'}]
    start={o['name']:o['position']for o in fs[0]['objects']};end={o['name']:o['position']for o in fs[-1]['objects']}
    displacement={name:math.dist(start[name],end[name])for name in start}
    contacts=[c for f in state['frames']for c in f.get('contacts',[])];depths=[c['penetration_m']for c in contacts if 'penetration_m'in c]
    return dict(events=dict(folder_downstream_contact=int(bool(hits)),downstream_response_original=int(displacement['t16_downstream_box']>.015),folder_motion_original=int(displacement['t16_folder']>.08)),
                contact_first=min(hits)if hits else None,final_displacements_m=displacement,
                max_native_penetration_m=max(depths)if depths else None,penetration_field_contacts=len(depths),total_contacts=len(contacts))


def main():
    p=argparse.ArgumentParser()
    for name in ['plan','root','python']:p.add_argument('--'+name,required=True)
    a=p.parse_args();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(root/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=json.loads(Path(a.plan).read_text());raw=Path(job['config_path']).read_bytes();assert sha(raw)==job['config_sha256']
    original=json.loads(raw)
    assert original['render']['fps']==30 and original['render']['frames']==210
    for name,digest in job['backend_sources'].items():assert sha(Path(name).read_bytes())==digest
    repaired=copy.deepcopy(original);shift=0.
    while folder_support_clearance(repaired)['minimum_xz_sat_overlap_m']>-.0002:
        book=next(o for o in repaired['dynamic_objects']if o['name']=='t16_support_book')
        book['pose']['position'][0]+=.0001
        for key in book['motion']['keyframes']:key['position'][0]+=.0001
        shift+=.0001
        if shift>.03:raise ValueError('bounded geometry repair did not clear the overlap')
    repaired['experiment']['contact_position_normalized']=layout(repaired)
    source_stored=Path(job['source_state_path']).read_bytes();assert sha(source_stored)==job['source_state_blob_sha256'];source=json.loads(gzip.decompress(source_stored))
    assert all('contacts'in f for f in source['frames']if f['frame_index']>=original['render']['pre_static_frames'])
    results={};gpu,lease=acquire(root)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    lib=a.python.rsplit('/bin/',1)[0]+'/lib';env['LD_LIBRARY_PATH']=lib+'/python3.10/site-packages/nvidia/cu13/lib:'+lib+':'+env.get('LD_LIBRARY_PATH','')
    try:
        for arm,base in [('original',original),('geometry_only_repair',repaired)]:
            dest=root/arm;dest.mkdir(exist_ok=True);c=copy.deepcopy(base)
            c['show_viewer']=False;c['scene_overrides']['raytracing']=False
            c['render'].update(resolution=[424,240],render_backend='raster',write_video=True,
                               save_video=str(dest/'video.mp4'),save_first_rgb=str(dest/'first.png'),save_last_rgb=str(dest/'last.png'))
            c['annotations']={'enabled':True,'save_path':str(dest/'state.json')};save(dest/'config.json',c)
            save(root/'resource_status.json',dict(status='running_source_only_impact_audit',clip_id=job['clip_id'],arm=arm,gpu=gpu))
            with (dest/'run.log').open('wb')as log:
                run=subprocess.run([a.python,job['renderer'],'--config',str(dest/'config.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
            if run.returncode:raise RuntimeError('source audit renderer failed; no effect conclusion: '+str(dest/'run.log'))
            state_raw=(dest/'state.json').read_bytes();state=json.loads(state_raw);assert len(state['frames'])==210
            assert all('contacts'in f for f in state['frames']if f['frame_index']>=c['render']['pre_static_frames'])
            row=dict(**measure(state),state_sha256=sha(state_raw),config_sha256=sha((dest/'config.json').read_bytes()),
                     initial_geometry=folder_support_clearance(base),actual_layout=layout(base),seed=base.get('seed'),gpu=gpu)
            (dest/'state.json.gz').write_bytes(gzip.compress(state_raw,compresslevel=3,mtime=0));save(dest/'receipt.json',row);results[arm]=row
    finally:lease.close()
    expected=measure(source);baseline=results['original'];fixed=results['geometry_only_repair']
    changed=[key for key in baseline['events']if baseline['events'][key]!=fixed['events'][key]]
    result=dict(schema='t16-source-only-geometry-impact-v1',clip_id=job['clip_id'],horizon_s=5.,source_input_preserved=True,
                released_prompts_modified=False,model_videos_regenerated=False,official_input_version_change_authorized=False,
                same_gpu_for_both_arms=gpu,same_seed=original.get('seed'),support_x_repair_m=shift,
                original_layout=layout(original),audit_repaired_layout=layout(repaired),source_reference_events=expected['events'],
                baseline_events_reproduced=baseline['events']==expected['events'],arms=results,flipped_events=changed,
                effect_status='observed_event_change'if changed else'no_event_change_at_selected_point',
                critical_distance_bin_effect='not_yet_measured_do_not_infer_no_critical_point_effect',
                scientific_reference_quality_gate='Existing 1 mm native contact-depth gate remains separate from event stability.',
                note='Geometry-only A/B audit, not approval to replace frozen v6. Branch stability at one point does not establish unchanged critical boundaries.')
    save(root/'result.json',result);save(root/'resource_status.json',dict(status='finished',clip_id=job['clip_id'],effect_status=result['effect_status']))


if __name__=='__main__':main()
