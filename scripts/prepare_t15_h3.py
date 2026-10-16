from pathlib import Path
import json
import hashlib
import argparse
p=argparse.ArgumentParser()
p.add_argument('--out',required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
assets=root/'examples/t15_h3'
for name, expected in json.loads((assets/'checksums.json').read_text()).items():
    if hashlib.sha256((assets/name).read_bytes()).hexdigest() != expected:
        raise ValueError('input hash mismatch: '+name)
rows=[]
for seed in (41000,41001):
    for case in ('case01','case02'):
        sid=f't15_h3_{case}_s{seed}'
        rows.append(dict(sample_id=sid,source_sample_id=sid,index=len(rows),
            prompt_granularity='basic_initial_conditions',
            condition_image=str(assets/f'{case}.png'),
            prompt_file=str(assets/f'{case}.txt'),seed=seed,
            source_width=854,source_height=480,gen_width=896,gen_height=512,
            scenario='T15',template='basic_validation',num_frames=124,output_fps=24))
with Path(a.out).open('x',encoding='utf-8') as f:
    for row in rows:f.write(json.dumps(row)+'\n')
print('Registered four outputs, unique directories; shared seeds 41000/41001.')
