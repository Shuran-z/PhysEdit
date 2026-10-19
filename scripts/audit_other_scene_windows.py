import json
from pathlib import Path
import cv2,numpy as np
base=Path(__file__).resolve().parents[1]
src=base/'review/T16-T20_samples_2026-10-10';out=base/'review/other_scene_window_probe_20261016';out.mkdir(exist_ok=True)
records=[]
for video in sorted(src.rglob('cam01.mp4')):
    if not any(t in str(video) for t in ('T16/','T17/','T18/','T16\\','T17\\','T18\\')):continue
    rel=video.relative_to(src);sid='_'.join(rel.parts[:-1]);cap=cv2.VideoCapture(str(video));fps=cap.get(5);n=int(cap.get(7));panels=[]
    for idx in np.linspace(0,n-1,6).round().astype(int):
        cap.set(1,int(idx));ok,f=cap.read();assert ok
        f=cv2.resize(f,(480,270));cv2.putText(f,f'{sid} {idx} {idx/fps:.2f}s',(5,20),0,.44,(0,0,255),1);panels.append(f)
    cap.release();sheet=np.concatenate([np.concatenate(panels[:3],axis=1),np.concatenate(panels[3:],axis=1)],axis=0)
    ok,b=cv2.imencode('.jpg',sheet);assert ok;(out/f'{sid}.jpg').write_bytes(b.tobytes())
    records.append(dict(sample_id=sid,video=str(video),fps=fps,frames=n,sidecars=[x.name for x in video.parent.glob('*.json')]))
(out/'inventory.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
