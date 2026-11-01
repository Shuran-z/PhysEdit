"""Recover T12 contact labels under the author-approved new contact protocol."""
import argparse
import copy
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from t12_contact_readback import instrument, ORIGINAL_SHA256


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False))
    temp.replace(path)


def acquire(root):
    while True:
        policy_file = root/'resource_policy.json'
        if not policy_file.exists():policy_file = root.parent/'resource_policy.json'
        policy = json.loads(policy_file.read_text()) if policy_file.exists() else {}
        max_util = policy.get('maximum_utilization_percent', 30)
        if type(max_util) is not int or not 0 <= max_util <= 100:
            raise ValueError('invalid GPU sharing policy')
        minimum_free_mib = policy.get('minimum_gpu_free_mib', 12000)
        if type(minimum_free_mib) is not int or minimum_free_mib < 4096:
            raise ValueError('invalid GPU memory reserve policy')
        allowed_gpus = policy.get('allowed_gpu_indices')
        if allowed_gpus is not None and (not isinstance(allowed_gpus,list) or not allowed_gpus or any(type(i)is not int or i<0 for i in allowed_gpus)):
            raise ValueError('invalid explicit GPU selection policy')
        minimum_disk_gib = policy.get('minimum_disk_free_gib', 20)
        if type(minimum_disk_gib) not in (int, float) or minimum_disk_gib < 12:
            raise ValueError('invalid disk reserve policy')
        if shutil.disk_usage(root).free < minimum_disk_gib * 1024**3:
            save(root/'resource_status.json', {'status': 'waiting_for_disk', 'minimum_disk_free_gib': minimum_disk_gib})
            time.sleep(20)
            continue
        raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free,utilization.gpu', '--format=csv,noheader,nounits']).decode()
        for gpu, free, util in sorted([tuple(map(int, s.split(','))) for s in raw.splitlines()], key=lambda x: x[1], reverse=True):
            if allowed_gpus is not None and gpu not in allowed_gpus:continue
            if free < minimum_free_mib or util > max_util:
                continue
            lease = Path('/tmp/physedit_conditional_gpu_%s.lock' % gpu).open('a')
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lease.close()
                continue
            return str(gpu), lease
        save(root/'resource_status.json', {'status': 'waiting_for_gpu_capacity', 'minimum_free_mib': minimum_free_mib, 'maximum_utilization_percent': max_util})
        time.sleep(20)


def main():
    p = argparse.ArgumentParser()
    for name in ['plan', 'root', 'source', 'python']:
        p.add_argument('--'+name, required=True)
    a = p.parse_args()
    root = Path(a.root); root.mkdir(parents=True, exist_ok=True)
    lock = (root/'worker.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    source = Path(a.source)
    assert sha((source/'12_render_motion_sequence.py').read_bytes()) == ORIGINAL_SHA256
    renderer = source/'12_render_motion_sequence_contact_v1.py'
    patched = instrument((source/'12_render_motion_sequence.py').read_bytes())
    if renderer.exists() and renderer.read_bytes() != patched:
        raise ValueError('instrumented renderer changed')
    renderer.write_bytes(patched)
    results = []
    for job in json.loads(Path(a.plan).read_text()):
        folder = root/job['clip_id']; folder.mkdir(exist_ok=True)
        receipt = folder/'receipt.json'
        if receipt.exists():
            results.append(json.loads(receipt.read_text())); save(root/'status.json', results); continue
        lease = None
        try:
            original = Path(job['source_config_path']).read_bytes()
            assert sha(original) == job['source_config_sha256']
            config = json.loads(original)
            c = copy.deepcopy(config); render = c['render']
            render.update(write_video=False, render_backend='raster', resolution=[160,96], raytracing_spp=1, use_native_recording=False, camera_outputs=[])
            for key in ['save_video', 'save_first_rgb', 'save_last_rgb', 'save_rgb_frames_dir']:
                if render.get(key): render[key] = str(folder/Path(render[key]).name)
            c['scene_overrides']['raytracing'] = False
            c['annotations']['save_path'] = str(folder/'physics.json')
            save(folder/'config.json', c)
            gpu, lease = acquire(root)
            save(root/'resource_status.json', {'status':'running_source_contact_readback','clip_id':job['clip_id'],'gpu':gpu})
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, PYOPENGL_PLATFORM='egl', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
            lib = a.python.rsplit('/bin/',1)[0]+'/lib/python3.10/site-packages/nvidia/cu13/lib'
            env['LD_LIBRARY_PATH'] = lib + (':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
            with (folder/'run.log').open('wb') as log:
                run = subprocess.run([a.python,str(renderer),'--config',str(folder/'config.json')], cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            lease.close(); lease = None
            if run.returncode: raise RuntimeError('source replay failed; see run.log')
            raw = (folder/'physics.json').read_bytes(); state = json.loads(raw)
            assert len(state['frames']) == len(job['reference_positions']) == 210
            errors = []; first = None
            for frame, reference in zip(state['frames'],job['reference_positions']):
                assert frame['frame_index'] == reference['frame_index']
                actual = {o['name']:o['position'] for o in frame['objects']}
                assert set(actual) == set(reference['positions'])
                for name, point in reference['positions'].items():
                    error = math.dist(actual[name],point)
                    if not math.isfinite(error): raise ValueError('nonfinite trajectory')
                    errors.append(error)
                assert frame.get('contact_telemetry_complete') is True and isinstance(frame.get('contacts'),list)
                if frame['frame_index'] >= job['condition_frame_index']:
                    for contact in frame['contacts']:
                        key = [frame['frame_index'],contact['physics_step_index']]
                        if first is None or key < first: first = key
            maximum = max(errors)
            admitted = maximum <= job['inherited_position_tolerance_m']
            compressed = gzip.compress(raw,compresslevel=3,mtime=0)
            (folder/'physics.json.gz').write_bytes(compressed)
            row = dict(clip_id=job['clip_id'],status='contact_readback_trajectory_matched' if admitted else 'trajectory_mismatch',
                       original_state_sha256=job['original_state_sha256'], original_config_sha256=sha(original),
                       original_renderer_sha256=ORIGINAL_SHA256,instrumented_renderer_sha256=sha(patched),
                       replay_state_sha256=sha(raw),stored_state_sha256=sha(compressed),
                       maximum_position_difference_m=maximum,position_tolerance_m=job['inherited_position_tolerance_m'],
                       first_contact=first,contact_label=int(first is not None) if admitted else None,
                       scope='New-version native contact readback, not telemetry recovered from the historical state; RGB and boundary admission remain separate')
            save(receipt,row)
        except Exception as exc:
            row = dict(clip_id=job['clip_id'],status='failed',error=str(exc))
        finally:
            if lease is not None: lease.close()
        results.append(row); save(root/'status.json',results)
    save(root/'resource_status.json',{'status':'completed','registered':len(results)})


if __name__ == '__main__':
    main()
