"""Search the frozen T06_C04 intervention using its Isaac producer, not Genesis.

Executed on p25. Inputs/results live under a new task directory. The producer,
frozen reference, prompts and existing outputs are never edited.
"""
import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2))
    temp.replace(path)


def label(state, required, end=209):
    frames = state['trajectory']
    assert len(frames) == 210
    pairs = {frozenset(a.rsplit('/', 1)[-1] for a in c['actors'])
             for f in frames[5:end+1] for c in f.get('contacts', [])}
    return int(all(frozenset(p) in pairs for p in required))


def run(root, gpu):
    root.mkdir(exist_ok=True, parents=True)
    lock = (root/'worker.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    source = json.loads((root/'source.json').read_text())['physics']['source_config']
    producer = Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/repro_20260909')
    python = '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
    base_theta = source['experiment']['parameter']['parameter_value']
    required = source['experiment']['required_contact_pairs']
    signatures = {str(producer/n): sha(producer/n) for n in ['run_one.py', 'render_repro.py', 'repro_contract.py']}
    points = {}

    def evaluate(theta):
        key = ('%.12f' % theta).rstrip('0').rstrip('.')
        receipt = root/(key+'.json')
        if receipt.exists():
            row = json.loads(receipt.read_text())
            assert row['producer_sha256'] == signatures
            assert sha(row['state_path']) == row['state_sha256']
            points[theta] = row
            return row['label']
        config = copy.deepcopy(source)
        if theta != base_theta:
            config['experiment']['parameter']['parameter_value'] = theta
            for force in config['runtime_forces']:
                force['force_world'] = [v*theta/base_theta for v in force['force_world']]
        # Distinct input filenames; source sample_id, seed and fixed context stay intact.
        name = 'core100T06C04_' + root.name + '_' + key.replace('.', 'p')
        config_path = producer/'inputs'/(name+'.json')
        if config_path.exists():
            assert json.loads(config_path.read_text()) == config
        else:
            config_path.write_text(json.dumps(config, indent=2))
        save(root/'status.json', dict(state='running_original_isaac_probe', theta=theta,
                                     gpu=gpu, completed=len(points), formal_admission=False))
        command = [python, str(producer/'run_one.py'), '--config', str(config_path),
                   '--gpu', str(gpu), '--physics-only', '--label', 'core100oct31']
        started = time.time()
        with (root/(key+'.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=2400)
        output = Path('/data_cached/wangzijun_p25/isaac_out/repro_20260909')/(name+'_genesis_control_hold_core100oct31_physics')
        state_path = output/'state.json'
        state = json.loads(state_path.read_text())
        assert state['metadata']['engine'] == 'Isaac Sim 5.1.0'
        assert abs(state['metadata']['physics_dt']*state['metadata']['steps_per_frame']-.02) < 1e-12
        assert state['metadata']['force_mode'] == 'genesis_control_hold'
        assert state['metadata']['source_config_sha256'] == sha(config_path)
        row = dict(theta=theta, label=label(state, required), state_path=str(state_path),
                   state_sha256=sha(state_path), config_sha256=sha(config_path),
                   producer_sha256=signatures, elapsed_s=time.time()-started,
                   seed=source['seed'], event='complete_required_contact_chain',
                   condition_frame_index=4, end_frame_index=209, horizon_s=4.1,
                   formal_admission=False)
        save(receipt, row)
        points[theta] = row
        return row['label']

    try:
        assert evaluate(base_theta) == 0, 'Isaac source event did not reproduce'
        low, high = base_theta, 1.8571429
        left, right = evaluate(low), evaluate(high)
        if left != right:
            while high-low > .0005:
                middle = (low+high)/2
                if evaluate(middle) == left:
                    low = middle
                else:
                    high = middle
            intervals = [dict(event='complete_required_contact_chain', bracket=[low, high], labels=[left, right])]
            status = 'observed_local_transition'
        else:
            intervals, status = [], 'no_flip_in_requested_local_bracket'
        save(root/'result.json', dict(clip_id='T06_C04', engine='isaac', status=status,
            theta=base_theta, normalization_domain=[1.,4.], horizon_s=4.1,
            condition_frame_index=4, end_frame_index=209, intervals=intervals,
            source_label=left, source_pinned_config_sha256=sha(root/'source.json'),
            probes=list(points.values()), original_seed_preserved=True,
            source_force_mode_preserved=True, intervention='proportional original force waveform amplitude',
            producer_sha256=signatures, formal_admission=False))
        save(root/'status.json', dict(state='complete', probes=len(points), intervals=len(intervals)))
    except Exception:
        save(root/'status.json', dict(state='failed', completed=len(points), error=traceback.format_exc()))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--gpu', type=int, choices=[0,1,2,4,5], required=True)
    args = parser.parse_args()
    run(args.root, args.gpu)
