"""Reject background-shaped recovery masks using actual initially clear RGB.

Same 1038-case scope. Original successful non-recovered measurements stay
unchanged. No fitting/trajectory/reference-box inputs and no subpixel edges.
"""
import copy, hashlib, json, sys
from pathlib import Path
import cv2, numpy as np
from sam31_rgb_observation_health import initial_background_valid
from track_sam31_identity_center_control import pixel_box


def certify(rgb, initial, valid, neural):
    box = pixel_box(neural)
    if box is None: return neural, dict(status='no_model_mask')
    x,y,xx,yy = box;h,w=neural.shape
    x,y,xx,yy=max(0,x-32),max(0,y-32),min(w,xx+32),min(h,yy+32)
    fraction=float(valid[y:yy,x:xx].mean())
    if fraction < .98:
        return neural,dict(status='initial_background_uncertified',known_fraction=fraction)
    # This independently observed background is never inferred from missed
    # target masks. The old neural mask supplies an identity/ROI cue only;
    # it cannot force foreground onto currently unchanged RGB pixels.
    delta=np.max(np.abs(rgb[y:yy,x:xx].astype(np.int16)-initial[y:yy,x:xx].astype(np.int16)),axis=-1)
    foreground=(delta>12)&valid[y:yy,x:xx]
    vicinity=cv2.dilate(neural,np.ones((7,7),np.uint8))[y:yy,x:xx]>0
    n,labels,stats,_=cv2.connectedComponentsWithStats(foreground.astype(np.uint8),connectivity=8)
    candidates=[]
    for k in range(1,n):
        contact=int(np.sum((labels==k)&vicinity))
        if contact: candidates.append((int(stats[k,cv2.CC_STAT_AREA]),contact,-k))
    if not candidates:
        # A returned mask with no independent foreground evidence is a
        # tracking failure, never a successful observation of background.
        return None,dict(status='no_current_rgb_foreground',known_fraction=fraction)
    _,_,negk=max(candidates)
    result=np.zeros_like(neural);result[y:yy,x:xx]=(labels==-negk)
    return result,dict(status='independent_current_rgb_component',known_fraction=fraction,
        before_pixels=int(neural.sum()),after_pixels=int(result.sum()),
        model_box=box,actual_rgb_box=pixel_box(result),roi=[x,y,xx,yy])


def main():
    root=Path(sys.argv[1]);cv2.setNumThreads(1)
    protocol=json.loads((root/'sam31_rgb_certified_full30_protocol.json').read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==protocol['runner_sha256']
    assert hashlib.sha256((root/'sam31_rgb_observation_health.py').read_bytes()).hexdigest()==protocol['rgb_health_module_sha256']
    rows=list(map(json.loads,(root/'runs/sam31_rgb_health_full30_tracks.jsonl').read_text().splitlines()))
    jobs={j['id']:j for j in map(json.loads,(root/'sam31_rgb_health_full30_jobs.jsonl').read_text().splitlines())}
    assert len(rows)==len({t['id']for t in rows})==len(jobs)==1038
    assert sum(len(t['frames'])for t in rows)==13918 and sum(len(t['tracking_frames'])for t in rows)==79687
    out=root/'runs/sam31_rgb_certified_full30_tracks.jsonl';assert not out.exists()
    masks=root/'runs/sam31_rgb_certified_full30_masks';masks.mkdir(exist_ok=True)
    visual=root/'runs/sam31_rgb_certified_recovery_actual';visual.mkdir(exist_ok=True)
    with out.open('w')as writer:
        for row in rows:
            t=copy.deepcopy(row);j=jobs[t['id']];stem=hashlib.sha256(t['id'].encode()).hexdigest()[:12]
            recoveries={z['frame']for z in t['rgb_health_recovery']if z['status']=='current_rgb_instance_crop'}
            audit=[];cap=None
            if recoveries:
                cap=cv2.VideoCapture(j['video']);cap.set(cv2.CAP_PROP_POS_FRAMES,j['prompt_frame']);ok,initial=cap.read();assert ok
                valid=initial_background_valid(initial.shape[:2],j['scene_boxes'])
            for k,f in enumerate(t['frames']):
                if t['boxes'][k] is None:continue
                source=root/'runs/sam31_rgb_health_full30_masks'/f'{stem}_{f}.npz'
                m=np.load(source)['mask']
                if f in recoveries:
                    cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,rgb=cap.read();assert ok
                    m,z=certify(rgb,initial,valid,m);z['frame']=f;audit.append(z)
                    t['boxes'][k]=pixel_box(m)if m is not None else None
                    t['reasons'][k]=z['status']
                    im=rgb.copy()
                    if m is not None:
                        contours,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(im,contours,-1,(0,255,0),1)
                        x,y,xx,yy=pixel_box(m);im=im[max(0,y-20):yy+20,max(0,x-20):xx+20]
                    cv2.imwrite(str(visual/f'{stem}_{f}.png'),cv2.resize(im,None,fx=5,fy=5,interpolation=cv2.INTER_NEAREST))
                if m is not None:np.savez_compressed(masks/f'{stem}_{f}.npz',mask=m)
            if cap:cap.release()
            t['box_mode']='prefix_rgb_certified_component_pixel';t['certified_runner_sha256']=protocol['runner_sha256'];t['rgb_recovery_certification']=audit
            writer.write(json.dumps(t)+'\n');writer.flush()
            if audit:print(json.dumps({'id':t['id'],'audit':audit}),flush=True)
    print(json.dumps({'processed':len(rows),'original_frames':13918}),flush=True)


if __name__=='__main__':main()
