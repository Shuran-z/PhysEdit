"""Freeze current near roster and generate event-focused, hash-bound RGB review sheets."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018');DEST=OUT/'near375_visual';DEST.mkdir(exist_ok=True)

def main():
 frozen=DEST/'frozen_candidates.json'
 if not frozen.exists():
  rows=[]
  for name in ['isaac_verified_numerical_registry.json','t02_published_scoring_registry.json']:
   rows += [r for r in json.loads((OUT/name).read_text()) if r.get('near_numerical_eligible')]
  assert len(rows)==375
  frozen.write_text(json.dumps(rows,indent=2),encoding='utf-8')
 rows=json.loads(frozen.read_text());matched={r['sample_id']:r for r in json.loads(Path('review/release_boundary_binding_20261018/matched_registry.json').read_text())}
 proofs={r['sample_id']:r for r in json.loads((OUT/'isaac_original_scoring_provenance.json').read_text())}
 plan=[]
 for i,r in enumerate(rows):
  if r['engine']!='isaac':continue
  proof=proofs[r['sample_id']];qa=proof['metadata']['qa.json']
  pairs=qa.get('first_contacts_s',{})
  contact=next((v for k,v in pairs.items() if k in ['folder|receiver1','t19_striker|t19_target']),None)
  center=round(30*contact) if contact is not None else (83 if r['scene_id']=='T16' else 10)
  frames=sorted(set([0,max(0,center-3),center,min(209,center+3),min(209,center+30),209]))
  plan.append(dict(index=i,sample_id=r['sample_id'],scene_id=r['scene_id'],family_id=r['family_id'],
   folder=matched[r['sample_id']]['folder'],frames=frames,expected_sha256=r['reference_video_hashes']['cam01']))
 code=r'''
import cv2,numpy as np,pathlib,json,hashlib
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/near375_visual_20261018');root.mkdir(exist_ok=True)
records=[]
for start in range(0,len(ROWS),6):
 canvas=np.full((6*170,6*300,3),245,np.uint8)
 for j,r in enumerate(ROWS[start:start+6]):
  path=pathlib.Path(r['folder'])/'cam01.mp4';sha=hashlib.sha256(path.read_bytes()).hexdigest()
  assert sha==r['expected_sha256'];cap=cv2.VideoCapture(str(path));frames=[]
  while True:
   ok,im=cap.read()
   if not ok:break
   frames.append(im)
  cap.release();assert len(frames)==210
  for k,fi in enumerate(r['frames']):
   im=frames[fi];h,w=im.shape[:2]
   im=im[175:325,270:570] if r['scene_id']=='T19' else im[int(.22*h):int(.90*h),int(.18*w):int(.83*w)]
   im=cv2.resize(im,(300,150));canvas[j*170+20:(j+1)*170,k*300:(k+1)*300]=im
   cv2.putText(canvas,str(r['index'])+' '+r['scene_id']+' '+r['family_id']+' f'+str(fi),(k*300+3,j*170+15),cv2.FONT_HERSHEY_SIMPLEX,.40,(0,0,0),1)
  # Each frame is decoded, while visual review below is explicitly sparse/event-focused.
  records.append(dict(**r,video_sha256=sha,decoded_frames=len(frames),page=start//6,review_camera='cam01'))
 page=root/('page_%02d.jpg'%(start//6));cv2.imwrite(str(page),canvas,[cv2.IMWRITE_JPEG_QUALITY,94])
 print(json.dumps({'page':start//6,'samples':len(records)}),flush=True)
(root/'index.json').write_text(json.dumps(records))
'''
 packed=base64.b64encode(gzip.compress(json.dumps(plan).encode())).decode()
 code='import json,gzip,base64\nROWS=json.loads(gzip.decompress(base64.b64decode('+repr(packed)+')))\n'+code
 p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 p.stdin.write(code.encode());p.stdin.close()
 for line in p.stdout:print(line.decode().strip(),flush=True)
 if p.wait():raise RuntimeError('remote review preparation failed')
 subprocess.run(['scp','-O','-q','p25:/data_cached/wangzijun_p25/liyuhan/near375_visual_20261018/*.jpg',str(DEST)],check=True)
 subprocess.run(['scp','-O','-q','p25:/data_cached/wangzijun_p25/liyuhan/near375_visual_20261018/index.json',str(DEST/'index.json')],check=True)
if __name__=='__main__':main()
