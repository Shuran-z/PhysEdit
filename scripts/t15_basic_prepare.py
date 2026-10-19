"""Prepare a bounded basic-generation probe from existing matched T15 references."""
import base64
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/t15_basic_validation_20261014'
REMOTE='/data2/wangzijun_p25/liyuhan/t15_basic_validation_20261014'
OUT.mkdir(exist_ok=False)
a=json.loads((ROOT/'review/t15_boundary_pilot_20261014/reference_audit.json').read_text(encoding='utf-8'))
g=next(g for g in a['canonical_A_groups'] if g['gravity']=='g03_earth')
selected=[]
for speed in (1.728,2.832):
    selected.append(next(r for r in a['rows'] if r['speed_context_hash']==g['context_hash'] and r['speed']==speed))
(OUT/'references.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
code=r'''
import base64,cv2,json,pathlib,numpy as np
cv2.setNumThreads(1)
result=[]
for r in REQUESTS:
 folder=pathlib.Path(r['output']); c=json.loads((folder/'COMPLETED.json').read_text())
 video=next(pathlib.Path(c['video_output']).glob('*__cam01.mp4'))
 cap=cv2.VideoCapture(str(video)); tiles=[]; condition=None
 for index in [29,35,41,47,53,59,65,71,89,119,149,209]:
  cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read()
  assert ok
  if index==29:condition=base64.b64encode(cv2.imencode('.png',frame)[1]).decode()
  frame=cv2.resize(frame,(427,240));cv2.putText(frame,str(index),(8,22),0,.6,(0,255,255),2);tiles.append(frame)
 cap.release()
 sheet=np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,12,4)])
 result.append(dict(video=str(video),condition=condition,sheet=base64.b64encode(cv2.imencode('.jpg',sheet)[1]).decode(),config=json.loads(pathlib.Path(r['config']).read_text())))
print(json.dumps(result))
'''.replace('REQUESTS',repr(selected))
run=subprocess.run(['ssh','p25','python3','-'],input=code,text=True,encoding='utf-8',capture_output=True,timeout=180)
run.check_returncode(); recovered=json.loads(run.stdout)
rows=[]
for i,(r,media) in enumerate(zip(selected,recovered)):
    key=('nofall','fall')[i]
    (OUT/f'{key}.png').write_bytes(base64.b64decode(media.pop('condition')))
    (OUT/f'{key}_reference.jpg').write_bytes(base64.b64decode(media.pop('sheet')))
    (OUT/f'{key}_source.json').write_text(json.dumps(media,indent=2),encoding='utf-8')
    prompt=(f'A fixed wide camera observes a computer-rendered living room. A green book and a closed gray laptop lie on the table, and a black phone rests on the floor beside the table. '
            f'At the start the book moves toward the laptop at {r["speed"]} meters per second. Gravity is 9.81 meters per second squared. '
            'The book mass is 0.58 kg, laptop mass 1.35 kg, and phone mass 0.19 kg. No further external actuation occurs. '
            'Show six seconds of continuous motion from this initial image, with the same objects, static background, and fixed camera.')
    (OUT/f'{key}_prompt.txt').write_text(prompt,encoding='utf-8')
    rows.append(dict(sample_id=key,condition_image=f'{REMOTE}/{key}.png',prompt_file=f'{REMOTE}/{key}_prompt.txt',negative_prompt_file=f'{REMOTE}/negative.txt',seed=41000,num_frames=161,output_fps=25,source_width=854,source_height=480,width=864,height=480,out_dir=f'{REMOTE}/generated/{key}'))
(OUT/'negative.txt').write_text('camera movement, scene cut, morphing objects, disappearing objects, distorted geometry, blurry, jittery',encoding='utf-8')
(OUT/'generation_rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
(OUT/'plan.json').write_text(json.dumps(dict(stage='basic validation, not boundary experiment',seeds=[41000],source_frame=29,horizon_s=6,threshold_distance=None,gate='Both outputs preserve scene and target identity over 0..6 s; fall/no-fall separately judged. Repeat with second seed only if this pair passes. No critical experiment before repeat passes.',limitations='Single image does not encode velocity; text provides speed but not a complete simulator state. No conclusion about exact physics accuracy. Multiple input/config fixes bundled, no causal attribution of improvement.',selected=[dict(sample_id=r['sample_id'],speed=r['speed'],events=r['events']) for r in selected]),indent=2),encoding='utf-8')
print(str(OUT))
