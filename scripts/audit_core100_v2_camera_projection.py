"""Project archived world poses into the frozen reference's original camera.

This produces diagnostic evidence, never automatic camera/trajectory admission.
It can expose an incorrect trajectory association even when sample IDs agree.
Only existing files are read remotely; no simulator or GPU job is launched.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import base64,gzip,hashlib,json,math
from pathlib import Path
import cv2,numpy as np
t=TARGET
config=Path(next(r['source']for r in t['transfer_records']if'/configs/'in r['source']))
video=Path(next(r['source']for r in t['transfer_records']if'/videos/'in r['source']))
config_raw=config.read_bytes();assert hashlib.sha256(config_raw).hexdigest()==next(r['sha256']for r in t['transfer_records']if'/configs/'in r['source'])
assert hashlib.sha256(video.read_bytes()).hexdigest()==t['parent_video_sha256']
cfg=json.loads(config_raw);raw=Path(STATE_PATH).read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw;s=json.loads(decoded)
camera=cfg['render']['fixed_view'];pos=np.array(camera['position']);fwd=np.array(camera['look_at'])-pos;fwd=fwd/np.linalg.norm(fwd)
right=np.cross(fwd,[0,0,1]);right=right/np.linalg.norm(right);up=np.cross(right,fwd)
cap=cv2.VideoCapture(str(video));width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
assert[width,height]==cfg['render']['resolution']
focal=height/2/math.tan(math.radians(camera['fov_deg'])/2)
indices=[4,12,24,40,60,80,100,120,145,170,190,209];wanted=set(indices);frames={};i=0
while True:
 ok,im=cap.read()
 if not ok:break
 if i in wanted:frames[i]=im
 i+=1
cap.release();assert i==len(s['frames'])==210
names=[o['name']for o in s['dynamic_objects']if not o.get('spec',o).get('fixed',False)]
panels=[];projected=[]
for index in indices:
 im=frames[index].copy();pts=[]
 for number,name in enumerate(names):
  obj=next(o for o in s['frames'][index]['objects']if o['name']==name)
  v=np.array(obj['position'])-pos;z=np.dot(v,fwd)
  if z<=0:continue
  x=width/2+focal*np.dot(v,right)/z;y=height/2-focal*np.dot(v,up)/z
  pts.append(dict(name=name,pixel=[float(x),float(y)]))
  if not(0<=x<width and 0<=y<height):continue
  color=tuple(int(a)for a in cv2.cvtColor(np.uint8([[[number*31%180,240,255]]]),cv2.COLOR_HSV2BGR)[0,0])
  cv2.circle(im,(round(x),round(y)),5,(0,0,0),3);cv2.circle(im,(round(x),round(y)),4,color,2)
  cv2.putText(im,str(number),(round(x)+5,round(y)-5),cv2.FONT_HERSHEY_SIMPLEX,.4,color,1,cv2.LINE_AA)
 cv2.rectangle(im,(0,0),(width,27),(0,0,0),-1)
 cv2.putText(im,t['clip_id']+' f'+str(index)+' / archived poses -> cam01',(6,19),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA)
 panels.append(im);projected.append(dict(frame=index,centers=pts))
sheet=np.vstack([np.hstack(panels[k:k+3])for k in range(0,12,3)])
ok,encoded=cv2.imencode('.jpg',sheet,[cv2.IMWRITE_JPEG_QUALITY,88]);assert ok
print(json.dumps(dict(clip_id=t['clip_id'],image_b64=base64.b64encode(encoded.tobytes()).decode(),
 config_sha256=hashlib.sha256(config_raw).hexdigest(),parent_video_sha256=t['parent_video_sha256'],
 frozen_video_sha256=t['video_sha256'],archived_state_stored_sha256=hashlib.sha256(raw).hexdigest(),
 archived_state_decoded_sha256=hashlib.sha256(decoded).hexdigest(),camera=camera,
 archived_declared_video=s['render']['save_video'],projected_centers=projected,number_to_actor=names,
 admission=False,scope='Cross-camera world-pose projection diagnostic only; no same-trajectory assumption or automatic event admission.')))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--clip',required=True);args=p.parse_args()
    old=ROOT/'review/core100_remaining20_20261101'
    target=next(r for r in json.loads((old/'ORIGINAL_SOURCE_JOBS.json').read_text(encoding='utf8'))if r['clip_id']==args.clip)
    trace=next(r for r in json.loads((old/'ARCHIVED_STATE_TRACE.json').read_text(encoding='utf8'))if r['clip_id']==args.clip)
    state_path=trace['states'][0]['path']
    payload='TARGET='+repr(target)+'\nSTATE_PATH='+repr(state_path)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    wrapper='import base64,zlib,subprocess,json;code=zlib.decompress(base64.b64decode('+repr(encoded)+')).decode();p=subprocess.run(["/home/wangzijun_p25/miniconda3/envs/genesis/bin/python","-c",code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True);assert p.returncode==0,p.stderr[-1500:];print(p.stdout)'
    result=rpc(P21_OPTIONS,'p25',wrapper)
    image=base64.b64decode(result.pop('image_b64'));image_path=WORK/(args.clip+'_camera_projection.jpg');image_path.write_bytes(image)
    result.update(image_path=image_path.relative_to(ROOT).as_posix(),image_sha256=hashlib.sha256(image).hexdigest())
    path=WORK/(args.clip+'_camera_projection.json');path.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(clip_id=args.clip,image=str(image_path),receipt=str(path),admission=False)))


if __name__=='__main__':main()
