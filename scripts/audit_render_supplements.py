"""CPU-only post-render integrity audit and visual review sheets, no auto acceptance."""
import argparse
import collections
import gzip
import hashlib
import json
import math
import time
from pathlib import Path

def save(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    t=p.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2));t.replace(p)

def audit(receipt, root, out):
    import cv2
    import numpy as np
    sid=receipt['sample']; errors=[]; panels=[]
    videos=[]
    for v in receipt['results']:
        p=Path(v['video']); h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h!=v['sha256']: errors.append('video_hash:'+v['camera'])
        cap=cv2.VideoCapture(str(p)); fps=cap.get(cv2.CAP_PROP_FPS);n=0;chosen=[]
        while True:
            ok,frame=cap.read()
            if not ok:break
            if n in [0,24,50,100,150,209]:
                tile=cv2.resize(frame,(320,180));cv2.putText(tile,v['camera']+' f'+str(n),(4,16),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1);chosen.append(tile)
            n+=1
        cap.release()
        if n!=210 or abs(fps-30)>.01:errors.append('video_length_or_fps:'+v['camera'])
        if len(chosen)==6:panels.append(np.concatenate(chosen,axis=1))
        videos.append(dict(camera=v['camera'],frames=n,fps=fps,sha256=h))
    sheet=out/'sheets'/(sid+'.jpg');sheet.parent.mkdir(parents=True,exist_ok=True)
    if len(panels)==3:cv2.imwrite(str(sheet),np.concatenate(panels,axis=0),[cv2.IMWRITE_JPEG_QUALITY,85])
    sp=receipt.get('trajectory',{}).get('path')
    if not sp:
        cp=root/'configs'/sid/'cam01.json'
        if cp.exists():
            sp=json.loads(cp.read_text()).get('annotations',{}).get('save_path')
            if sp and not Path(sp).exists() and Path(sp+'.gz').exists():sp+='.gz'
    state={}
    if sp and Path(sp).exists():
        p=Path(sp);raw=gzip.open(p,'rb').read() if p.suffix=='.gz' else p.read_bytes()
        expected=receipt.get('trajectory',{}).get('uncompressed_sha256')
        if expected and hashlib.sha256(raw).hexdigest()!=expected:errors.append('state_hash')
        d=json.loads(raw);frames=d.get('frames',[]);names={o['name'] for o in d.get('dynamic_objects',[])}
        if len(frames)!=210:errors.append('state_frame_count')
        max_speed=0.;changed=[];nonfinite=[]
        for i,f in enumerate(frames):
            objs=f.get('objects',[])
            if {o['name'] for o in objs}!=names:changed.append(i)
            for ob in objs:
                for field in ['position','velocity','quaternion_xyzw','angular_velocity']:
                    vals=ob.get(field)
                    if not isinstance(vals,list) or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vals):nonfinite.append([i,ob['name'],field])
                vel=ob.get('velocity',[])
                if vel and all(isinstance(x,(float,int)) and math.isfinite(x) for x in vel):max_speed=max(max_speed,math.sqrt(sum(x*x for x in vel)))
        if changed:errors.append('state_object_set_changed')
        if nonfinite:errors.append('state_nonfinite_or_missing')
        state=dict(path=sp,frames=len(frames),objects=len(names),changed_object_frames=changed,
            nonfinite_or_missing=nonfinite[:20],max_speed_mps=max_speed,time_diagnostic=d.get('time_diagnostic'),
            boundary_safety=d.get('wall_boundary_safety_summary'))
    else:errors.append('state_unavailable')
    return dict(sample=sid,media_and_state_integrity='FAIL' if errors else 'PASS',errors=errors,
        videos=videos,state=state,contact_sheet=str(sheet),visual_physics_review='PENDING',
        scientific_acceptance=False,notes='Frame sheets do not prove between-frame contact or visibility; no outcome-based rejection.',checked=time.time())

def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',nargs='+',required=True);p.add_argument('--out',required=True);p.add_argument('--watch',action='store_true');p.add_argument('--expected-count',type=int);args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(out/'audit.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        rs={};planned=set()
        for name in args.roots:
            root=Path(name)
            if (root/'plan.json').exists():planned.update(x['sample'] for x in json.loads((root/'plan.json').read_text()))
            for p in (root/'receipts').glob('*.json'):
                r=json.loads(p.read_text())
                if r.get('media_complete'):rs[r['sample']]=(r,root)
        for sid,(r,root) in rs.items():
            dst=out/'results'/(sid+'.json')
            signature=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
            if dst.exists() and json.loads(dst.read_text()).get('receipt_signature')==signature:continue
            try:result=audit(r,root,out)
            except Exception as e:result=dict(sample=sid,media_and_state_integrity='ERROR',error=str(e),scientific_acceptance=False,visual_physics_review='PENDING')
            result['receipt_signature']=signature;save(dst,result)
            all_results=[json.loads(q.read_text()) for q in (out/'results').glob('*.json')]
            save(out/'status.json',dict(updated=time.time(),planned=len(planned),rendered=len(rs),audited=len(all_results),
                integrity_counts=dict(collections.Counter(x['media_and_state_integrity'] for x in all_results)),
                expected_local=args.expected_count or len(planned),
                physics_accepted=0,visual_review_pending=len(all_results),render_complete=len(rs)==(args.expected_count or len(planned))))
        if not args.watch or len(rs)==(args.expected_count or len(planned)):break
        time.sleep(60)

if __name__=='__main__':main()
