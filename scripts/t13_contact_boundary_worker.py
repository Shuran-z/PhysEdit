"""F5 contact/order boundaries on five exact Core100 source contexts.

Uses the released v7 contact renderer (also used by the original F5 production
queue). Never transfers the historical drink-motion or fall thresholds.
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
from t12_contact_replay_worker import acquire, save


def digest(raw):return hashlib.sha256(raw).hexdigest()


def observations(state):
    frames=[f for f in state['frames'] if 4<=f['frame_index']<=124]
    assert len(frames)==121 and all('contacts' in f for f in frames)
    pairs=[{'t13_driver_book','t13_falling_book'},{'t13_falling_book','t13_drink_box'}]
    first=[]
    for pair in pairs:
        hits=[(f['frame_index'],c.get('physics_step_index',-1))for f in frames for c in f['contacts']
              if {c.get('entity_a'),c.get('entity_b')}==pair]
        first.append(min(hits)if hits else None)
    labels=[int(t is not None)for t in first]
    return dict(first_contact=labels[0],second_contact=labels[1],
                ordered_chain=int(all(first) and first[0]<first[1])),first


def main():
    p=argparse.ArgumentParser()
    for n in ['plan','root','python']:p.add_argument('--'+n,required=True)
    p.add_argument('--full-render',action='store_true',help='Use original full RGB profile for source/profile retries')
    a=p.parse_args();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(root/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    results=[]
    for job in json.loads(Path(a.plan).read_text()):
        folder=root/job['clip_id'];folder.mkdir(exist_ok=True);final=folder/'result.json'
        if final.exists():results.append(json.loads(final.read_text()));continue
        try:
            raw=Path(job['config_path']).read_bytes();assert digest(raw)==job['config_sha256'];base=json.loads(raw)
            original_raw=Path(job['state_path']).read_bytes();assert digest(original_raw)==job['state_sha256']
            original=json.loads(original_raw);expected,expected_first=observations(original)
            assert expected==dict(first_contact=1,second_contact=1,ordered_chain=1)
            assert digest(Path(job['renderer']).read_bytes())==job['renderer_sha256']
            probes={}
            def evaluate(theta):
                dest=folder/format(theta,'.12g');dest.mkdir(exist_ok=True);receipt=dest/'receipt.json'
                if receipt.exists():
                    row=json.loads(receipt.read_text());b=gzip.decompress(Path(row['state_path']).read_bytes())
                    assert digest(b)==row['state_sha256'] and digest((dest/'config.json').read_bytes())==row['config_sha256']
                    assert observations(json.loads(b))[0]==row['labels']
                    assert row.get('render_profile','physics_only')==('original_full_rgb'if a.full_render else'physics_only')
                    if theta==job['theta']:
                        assert row['source_prefix_max_position_error_m']<=.001
                        assert row['labels']==expected
                        assert all(a[0]==b[0]for a,b in zip(row['first_contacts'],expected_first))
                    probes[theta]=row;return row
                c=copy.deepcopy(base);actors={o['name']:o for o in c['dynamic_objects']}
                # Original F5 edge-distance family: increasing edge margin moves
                # the drink inward, keeping both books and their controller fixed.
                actors['t13_drink_box']['pose']['position'][0]-=theta-job['theta']
                c['sample_metadata']['drink_edge_distance_m']=theta
                if 'drink_edge_distance' in c['experiment']:c['experiment']['drink_edge_distance']=theta
                c['annotations']['save_path']=str(dest/'physics.json');save(dest/'config.json',c)
                if a.full_render:
                    for key in ['save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir','save_depth_frames_dir','save_seg_frames_dir']:
                        if c['render'].get(key):c['render'][key]=str(dest/Path(c['render'][key]).name)
                    save(dest/'config.json',c)
                gpu,lease=acquire(root);env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,TI_OFFLINE_CACHE='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
                lib=a.python.rsplit('/bin/',1)[0]+'/lib';env['LD_LIBRARY_PATH']=lib+'/python3.10/site-packages/nvidia/cu13/lib:'+lib+':'+env.get('LD_LIBRARY_PATH','')
                save(root/'resource_status.json',dict(status='running_contact_probe',clip_id=job['clip_id'],theta=theta,gpu=gpu))
                with (dest/'run.log').open('wb')as log:
                    try:
                        command=[a.python,job['renderer'],'--config',str(dest/'config.json')]
                        if not a.full_render:command+=['--physics-only','--annotation-output',str(dest/'physics.json')]
                        run=subprocess.run(command,
                                           env=env,cwd=job['source_root'],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                    finally:lease.close()
                if run.returncode:raise RuntimeError('renderer failed: '+str(dest/'run.log'))
                b=(dest/'physics.json').read_bytes();state=json.loads(b);labels,first=observations(state)
                row=dict(theta=theta,labels=labels,first_contacts=first,state_path=str(dest/'physics.json.gz'),state_sha256=digest(b),config_sha256=digest((dest/'config.json').read_bytes()),render_profile='original_full_rgb'if a.full_render else'physics_only')
                if theta==job['theta']:
                    # Positive ever-events require a source-matching witness up
                    # to both events, not an invented terminal-state match.
                    stop=max(t[0]for t in expected_first);reference={f['frame_index']:{o['name']:o['position']for o in f['objects']}for f in original['frames']}
                    errors=[math.dist(o['position'],reference[f['frame_index']][o['name']])for f in state['frames'] if f['frame_index']<=stop for o in f['objects']]
                    row['source_prefix_max_position_error_m']=max(errors);row['source_prefix_last_frame']=stop
                    row['source_first_native_contacts']=expected_first
                    row['native_contact_substep_differences']=[a[1]-b[1]for a,b in zip(first,expected_first)] if all(first) else None
                    save(dest/'source_witness_check.json',dict(**row,expected_labels=expected,expected_first_contacts=expected_first,position_tolerance_m=.001))
                    # The registered target is occurrence and order. Preserve
                    # exact substep differences; equality of a solver substep
                    # is not a scoring requirement. Keep the original native
                    # frame and 1 mm positive-witness checks unchanged.
                    frame_match=all(a is not None and b is not None and a[0]==b[0]for a,b in zip(first,expected_first))
                    if labels!=expected or not frame_match or max(errors)>.001:raise ValueError('F5 source contact/trajectory replay mismatch; no boundary admission')
                (dest/'physics.json.gz').write_bytes(gzip.compress(b,compresslevel=3,mtime=0));save(receipt,row);probes[theta]=row;return row
            evaluate(job['theta'])
            grid=sorted(set(job['grid']+[job['theta']]));observed=[evaluate(t)for t in grid];intervals=[]
            for event in ['first_contact','second_contact','ordered_chain']:
                for left,right in zip(observed,observed[1:]):
                    if left['labels'][event]==right['labels'][event]:continue
                    lo,hi=left['theta'],right['theta']
                    while hi-lo>.0005:
                        mid=(lo+hi)/2
                        if evaluate(mid)['labels'][event]==left['labels'][event]:lo=mid
                        else:hi=mid
                    intervals.append(dict(event=event,bracket=[lo,hi],labels=[left['labels'][event],right['labels'][event]]))
            row=dict(clip_id=job['clip_id'],status='contact_domain_scan_completed',horizon_s=5.,condition_frame_index=4,
                     source_config_sha256=job['config_sha256'],source_state_sha256=job['state_sha256'],renderer_sha256=job['renderer_sha256'],
                     source_theta=job['theta'],domain=job['domain'],intervals=intervals,probes=list(probes.values()),
                     reference_admitted=False,pair_admitted=False,scope='One fixed original F5 context. A no-flip grid is not proof of no hidden boundary.')
            row['render_profile']='original_full_rgb'if a.full_render else'physics_only'
            save(final,row)
        except Exception as exc:row=dict(clip_id=job['clip_id'],status='failed',error=str(exc))
        results.append(row);save(root/'status.json',results)
    save(root/'resource_status.json',dict(status='finished',registered=len(results)))


if __name__=='__main__':main()
