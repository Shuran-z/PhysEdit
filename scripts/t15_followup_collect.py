"""Collect completed run artifacts and sampled full-field frames from p26."""
import argparse
import base64
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser();p.add_argument('run');args=p.parse_args()
if args.run not in ('run06','run07','run08','run09','run10'):raise ValueError('unregistered run')
root=Path(__file__).resolve().parents[1]
out=root/'review/t15_followup_20261014'
remote='/home/wangzijun_p25/liyuhan/t15_boundary_pipeline_20261014/'+args.run
code='''
import base64,cv2,json,pathlib,numpy as np
cv2.setNumThreads(1)
root=pathlib.Path(ROOT)
rows=[json.loads(s) for s in (root/'observed_rows.jsonl').read_text().splitlines()]
result=[]
for r in rows:
 if r.get('status')!='ok':continue
 cap=cv2.VideoCapture(r['video']);fps=cap.get(cv2.CAP_PROP_FPS);tiles=[]
 for t in [i*.4 for i in range(16)]:
  cap.set(cv2.CAP_PROP_POS_FRAMES,round(t*fps));ok,frame=cap.read()
  if not ok:raise RuntimeError(r['video'])
  frame=cv2.resize(frame,(427,240))
  cv2.putText(frame,f'{t:.2f}s',(8,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
  tiles.append(frame)
 cap.release()
 sheet=np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,16,4)])
 ok,jpg=cv2.imencode('.jpg',sheet)
 result.append(dict(sample_id=r['sample_id'],video=r['video'],video_sha256=r['video_sha256'],jpg=base64.b64encode(jpg.tobytes()).decode()))
print(json.dumps(result))
'''.replace('ROOT',repr(remote))
r=subprocess.run(['ssh','-o','BatchMode=yes','p26',
 '/data1/zhangshuran/miniconda3/envs/cosmos-predict2/bin/python','-'],input=code,
 text=True,encoding='utf-8',capture_output=True,timeout=180)
r.check_returncode()
result=json.loads(r.stdout)
media=out/'generated_media';media.mkdir(exist_ok=True)
for row in result:
 (media/(row['sample_id']+'_sheet.jpg')).write_bytes(base64.b64decode(row.pop('jpg')))
 subprocess.run(['scp','p26:'+row['video'],str(media/(row['sample_id']+'.mp4'))],check=True,timeout=180)
subprocess.run(['scp','-r','p26:'+remote,str(out)],check=True,timeout=180)
(out/(args.run+'_media_provenance.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(run=args.run,media=len(result))))
