"""Prepare local I2V pilot inputs without future-outcome prompts.

Reads the existing reference audit; extracts only 5 pre-trigger images on p25.
Creates model inputs separately from answer keys. Does not run video models.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/t15_boundary_pilot_20261014'
data = json.loads((OUT / 'reference_audit.json').read_text(encoding='utf-8'))
lookup = {r['sample_id']: r for r in data['rows']}
groups = sorted(data['canonical_A_groups'], key=lambda x: x['gravity'])
requests = [lookup[g['points'][1]['sample_id']] for g in groups]
remote = '''
import base64,cv2,hashlib,json,pathlib
requests = REQUESTS
results=[]
for row in requests:
 folder=pathlib.Path(row['output']);completed=json.loads((folder/'COMPLETED.json').read_text())
 video=next(pathlib.Path(completed['video_output']).glob('*__cam01.mp4'))
 cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_POS_FRAMES,29);ok,frame=cap.read();cap.release()
 if not ok:raise RuntimeError(str(video))
 ok,png=cv2.imencode('.png',frame)
 if not ok:raise RuntimeError('PNG encoding failed')
 cfg=json.loads(pathlib.Path(row['config']).read_text())
 state=json.loads((folder/'metadata/physics.json').read_text())
 results.append({'sample_id':row['sample_id'],'video':str(video),'frame':29,
   'png':base64.b64encode(png.tobytes()).decode(),'completed':completed,
   'config':cfg,'initial_objects':state['frames'][29]['objects']})
print(json.dumps(results))
'''.replace('REQUESTS', repr(requests))
result = subprocess.run(['ssh', 'p25', 'python3', '-'], input=remote, text=True,
                        encoding='utf-8', capture_output=True, timeout=90)
result.check_returncode()
assets = {r['sample_id']: r for r in json.loads(result.stdout)}
(OUT / 'conditioning').mkdir(exist_ok=True)
inputs, keys, receipts = [], [], []
for group in groups:
    assert group['single_speed_contract']
    anchor = assets[group['points'][1]['sample_id']]
    png = base64.b64decode(anchor.pop('png'))
    image = OUT / 'conditioning' / (group['gravity'] + '.png')
    image.write_bytes(png)
    cfg = anchor['config']
    mass_friction = {o['name']: {'mass_kg': o.get('mass'), 'friction': o['friction'], 'size_m': o['size']}
                     for o in cfg['dynamic_objects']}
    anchor['image_sha256'] = hashlib.sha256(png).hexdigest()
    receipts.append(anchor)
    velocities = [p['speed'] for p in group['points']]
    for index, point in enumerate(group['points']):
        for arm in ['correct_parameter', 'constant_parameter', 'cyclic_wrong_parameter']:
            speed = (velocities[index] if arm == 'correct_parameter' else
                     velocities[1] if arm == 'constant_parameter' else velocities[(index + 1) % 3])
            prompt = (
                'Fixed camera, one continuous six-second shot, preserving object identities. '
                'A book and a closed laptop are on a table; a phone is on the floor. '
                f'At the beginning, set the book velocity to ({speed:.6g}, 0, 0) metres per second '
                'in the declared world coordinates. No subsequent external actuation. '
                f'Gravity vector is {cfg["scene_overrides"]["gravity"]} metres per second squared. '
                'Generate the subsequent physical motion from the initial image and conditions. '
                'World +x is the direction from the book toward the laptop. '
                'Rigid-body sizes, masses, and friction coefficients: ' + json.dumps(mass_friction, sort_keys=True) + '. '
                'Initial object poses: ' + json.dumps({o['name']: {'position_m': o['position'],
                 'quaternion_xyzw': o['quaternion_xyzw']} for o in anchor['initial_objects']}, sort_keys=True)
            )
            for seed in range(5):
                sample_id = f'{group["gravity"]}_A{index}_{arm}_s{seed}'
                inputs.append({'sample_id': sample_id, 'mode': 'i2v', 'arm': arm,
                               'condition_image': str(image), 'prompt': prompt, 'seed': 27100 + seed,
                               'num_frames': 97, 'fps': 16, 'evaluation_duration_s': 6,
                               'source_width': 854, 'source_height': 480,
                               'input_speed_mps': speed, 'group_id': group['context_hash']})
                # Keys never enter prompt or inference input. Wrong-parameter arms are controls
                # scored against the original target, not labelled as physical errors under their own inputs.
                keys.append({'sample_id': sample_id, 'reference_sample_id': point['sample_id'],
                             'target_speed_mps': point['speed'], 'reference_events': point['events'],
                             'metric_status': 'sparse_development_only_not_certified_NearAcc',
                             'control_interpretation': 'response to the target condition; wrong-input controls are not physical-fidelity rankings'})
for filename, values in [('generation_inputs.jsonl', inputs), ('answer_key.jsonl', keys), ('conditioning_receipts.jsonl', receipts)]:
    (OUT / filename).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in values), encoding='utf-8')
print(json.dumps({'inputs': len(inputs), 'correct_parameter_inputs': sum(x['arm'] == 'correct_parameter' for x in inputs),
                  'condition_images': len(receipts), 'status': 'prepared_not_generated'}))
