"""Prepare H3 inputs locally; deployment requires an existing H3 host/environment."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'review/t15_basic_validation_20261014'
OUT=BASE/'h3_inputs'
OUT.mkdir(exist_ok=False)
rows=[]
for i,name in enumerate(('nofall','fall')):
    key=f'case{i+1:02d}'
    shutil.copyfile(BASE/f'{name}.png',OUT/f'{key}.png')
    prompt=(BASE/f'{name}_prompt.txt').read_text(encoding='utf-8').replace('six seconds','about five seconds')
    (OUT/f'{key}.txt').write_text(prompt,encoding='utf-8')
    rows.append(dict(sample_id=key,source_sample_id=key,index=i,prompt_granularity='basic_initial_conditions',
                     condition_image=f'__INPUT_ROOT__/{key}.png',prompt_file=f'__INPUT_ROOT__/{key}.txt',
                     seed=41000,source_width=854,source_height=480,gen_width=896,gen_height=512,
                     scenario='T15',template='basic_validation',num_frames=124,output_fps=24))
(OUT/'manifest.template.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
(OUT/'checksums.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()},indent=2),encoding='utf-8')
(BASE/'basic_status.json').write_text(json.dumps(dict(
    ltx_status='stopped_by_user_model_switch; process 53971 exited; no completed video',
    h3_status='inputs_ready; no inference launched; existing host and environment unresolved',
    reference_labels=[0,1],reference_speed_mps=[1.728,2.832],
    reference_review='12 timestamp sheets per clip visually checked against previous state audit',
    h3_frames=124,h3_fps=24,h3_last_frame_s=123/24,
    horizon_policy='Basic probe only: compare reference over 0..5.125s. No time stretching to six seconds.',
    padding=dict(left=21,right=21,top=16,bottom=16),
    gate='Both branches must preserve camera and target identity, permit event judgment and match fall/no-fall; then repeat second predeclared seed 41001. Critical generation remains gated.',
    checks='17 existing boundary regression tests pass; both edited runners compile; H3 GPU behavior untested'),indent=2),encoding='utf-8')
print('H3 input bundle prepared; deployment placeholder must be resolved before execution.')
