import json,subprocess,base64,gzip
from pathlib import Path
out=Path('review/scene_family_completion_20261018')
r=json.loads((out/'isaac_original_distance_registry.json').read_text());p={x['sample_id']:x for x in json.loads((out/'isaac_original_scoring_provenance.json').read_text())};d={x['sample_id']:x for x in json.loads(Path('review/release_boundary_binding_20261018/matched_registry.json').read_text())}
rows=[dict(sample_id=x['sample_id'],folder=d[x['sample_id']]['folder'],label=x['reference_label']) for x in r if x['scene_id']=='T19' and x['family_id']=='d3']
code=r'''
import pathlib,json,cv2,numpy as np
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/nearacc_rgb_review_20261018');root.mkdir(exist_ok=True)
index=[]
for start in range(0,len(ROWS),12):
 canvas=np.full((12*155,3*320,3),245,np.uint8)
 for j,r in enumerate(ROWS[start:start+12]):
  cap=cv2.VideoCapture(r['folder']+'/cam01.mp4')
  for k,frame in enumerate([0,105,209]):
   cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,im=cap.read()
   if not ok:raise ValueError('decode failure')
   h,w=im.shape[:2];im=im[int(.22*h):int(.9*h),int(.18*w):int(.83*w)]
   im=cv2.resize(im,(320,135));canvas[j*155+20:(j+1)*155,k*320:(k+1)*320]=im
  cap.release();cv2.putText(canvas,str(start+j)+' label='+str(r['label']), (3,j*155+15),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
  index.append(dict(index=start+j,**r))
 path=root/('page_%02d.jpg'%(start//12));cv2.imwrite(str(path),canvas)
(root/'index.json').write_text(json.dumps(index))
print(json.dumps(dict(pages=(len(ROWS)+11)//12,samples=len(ROWS),root=str(root))))
'''
packed=base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode();code='import base64,gzip,json\nROWS=json.loads(gzip.decompress(base64.b64decode('+repr(packed)+')))\n'+code
p=subprocess.run(['ssh','-o','BatchMode=yes','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=120);p.check_returncode();print(p.stdout.decode())
