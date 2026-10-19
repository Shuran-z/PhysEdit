"""Recover three existing reference videos and sampled sheets; never render physics."""
import base64
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/t15_followup_20261014'
audit=json.loads((ROOT/'review/t15_boundary_pilot_20261014/reference_audit.json').read_text())
group=next(g for g in audit['canonical_A_groups'] if g['gravity']=='g03_earth')
lookup={r['sample_id']:r for r in audit['rows']}
requests=[lookup[p['sample_id']] for p in group['points']]
code='''
import base64,cv2,json,pathlib,numpy as np,hashlib
cv2.setNumThreads(1)
requests=REQUESTS
results=[]
for r in requests:
 folder=pathlib.Path(r['output'])
 c=json.loads((folder/'COMPLETED.json').read_text())
 video=next(pathlib.Path(c['video_output']).glob('*__cam01.mp4'))
 cap=cv2.VideoCapture(str(video)); tiles=[]
 for index in [29,35,41,47,53,59,65,71,89,119,149,209]:
  cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read()
  if not ok:raise RuntimeError(str(video))
  # full field of view, no crop hides downstream objects
  frame=cv2.resize(frame,(427,240))
  cv2.putText(frame,f'{(index-29)/30:.2f}s',(8,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
  tiles.append(frame)
 cap.release()
 sheet=np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,12,4)])
 ok,png=cv2.imencode('.jpg',sheet)
 results.append(dict(sample_id=r['sample_id'],video=str(video),video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
  sheet_jpg=base64.b64encode(png.tobytes()).decode(),frame_indices=[29,35,41,47,53,59,65,71,89,119,149,209]))
print(json.dumps(results))
'''.replace('REQUESTS',repr(requests))
run=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3','-'],input=code,text=True,
                   encoding='utf-8',capture_output=True,timeout=180)
run.check_returncode()
results=json.loads(run.stdout)
media=OUT/'reference_media';media.mkdir(exist_ok=False)
for i,r in enumerate(results):
 (media/f'A{i}_sheet.jpg').write_bytes(base64.b64decode(r.pop('sheet_jpg')))
 subprocess.run(['scp','p25:'+r['video'],str(media/f'A{i}.mp4')],check=True,timeout=180)
(OUT/'reference_media_provenance.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'recovered':len(results),'out':str(media)}))
