"""Replay an immutable canonical reference before any conditional intervention.

This runs a real simulation, then compares all recorded actor positions in the
declared observation window. A mismatch stops admission; no old truth is copied.
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


def main():
    p = argparse.ArgumentParser()
    for key in ['plan', 'root', 'python']:p.add_argument('--'+key, required=True)
    a = p.parse_args();root = Path(a.root);root.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock=(root/'worker.lock').open('a');fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    job=json.loads(Path(a.plan).read_text());raw=Path(job['config_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==job['config_sha256']
    reference_raw=gzip.decompress(Path(job['reference_state_path']).read_bytes())
    assert hashlib.sha256(reference_raw).hexdigest()==job['reference_state_sha256']
    for name, digest in job['backend_sources'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    config=copy.deepcopy(json.loads(raw));render=config['render']
    if not job.get('preserve_original_render'):
        render.update(write_video=False, render_backend='raster', resolution=[160,96], raytracing_spp=1,
                      use_native_recording=False, save_rgb_frames=False, camera_outputs=[])
    if job.get('force_write_video'):render['write_video']=True
    for key in ['save_video','save_first_rgb','save_last_rgb','save_rgb_frames_dir']:
        if render.get(key):render[key]=str(root/Path(render[key]).name)
    if not job.get('preserve_original_render'):config['scene_overrides']['raytracing']=False
    config.setdefault('annotations',{}).update(enabled=True, save_path=str(root/'physics.json'))
    save(root/'config.json',config);gpu,lease=acquire(root)
    env=dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, TI_OFFLINE_CACHE='0', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    save(root/'resource_status.json',{'status':'running_canonical_source_replay','gpu':gpu})
    with (root/'run.log').open('wb') as log:
        try:
            run=subprocess.run([a.python,job['renderer'],'--config',str(root/'config.json')],
                               stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1800)
        finally:lease.close()
    if run.returncode:raise RuntimeError('canonical replay failed; inspect '+str(root/'run.log'))
    result_raw=(root/'physics.json').read_bytes();state=json.loads(result_raw);reference=json.loads(reference_raw)
    start=job['condition_frame_index'];last=start+round(job['horizon_s']*job['fps'])
    expected={f['frame_index']:f for f in reference['frames'] if start<=f['frame_index']<=last}
    actual={f['frame_index']:f for f in state['frames'] if start<=f['frame_index']<=last}
    assert set(expected)==set(actual) and start in expected and last in expected
    maximum=0.
    for i, frame in actual.items():
        ref={o['name']:o['position'] for o in expected[i]['objects']}
        observed={o['name']:o['position'] for o in frame['objects']};assert ref.keys()==observed.keys()
        maximum=max(maximum,max(math.dist(ref[n],observed[n])for n in ref))
    contacts_complete=all('contacts' in f for f in actual.values())
    pairs={frozenset(x):[] for x in job['pairs']}
    for i,f in actual.items():
        for c in f.get('contacts',[]):
            key=frozenset([c.get('entity_a'),c.get('entity_b')])
            if key in pairs:pairs[key].append([i,c.get('physics_step_index',-1)])
    receipt=dict(schema='canonical-source-replay-v1',clip_id=job['clip_id'],
                 gpu=gpu,reference_simulation_seed=job.get('reference_simulation_seed'),
                 position_tolerance_m=job['position_tolerance_m'],maximum_position_difference_m=maximum,
                 trajectory_reproduced=maximum<=job['position_tolerance_m'],contact_telemetry_complete=contacts_complete,
                 dynamic_contact_telemetry_complete=all('contacts'in f for f in actual.values()if f['frame_index']>=config['render']['pre_static_frames']),
                 contact_firsts=[dict(pair=sorted(pair),first=min(times)if times else None)for pair,times in pairs.items()],
                 state_sha256=hashlib.sha256(result_raw).hexdigest(),source_config_sha256=job['config_sha256'],
                 source_reference_state_sha256=job['reference_state_sha256'],horizon_s=job['horizon_s'],
                 pair_admitted=False,reference_admitted=False)
    (root/'physics.json.gz').write_bytes(gzip.compress(result_raw,compresslevel=3,mtime=0))
    save(root/'receipt.json',receipt);save(root/'resource_status.json',{'status':'finished',**receipt})


if __name__=='__main__':main()
