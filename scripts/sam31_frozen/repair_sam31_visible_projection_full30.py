"""All original cases/frames: initial identity, actual-RGB integer boundaries.
No fitting/reference trajectory/target gravity input to this runner.
"""
import copy,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from track_sam31_identity_center_control import pixel_box
from sam31_rgb_observation_health import initial_background_valid,choose_actual_mask,repair_certified,foreground_evidence
from sam31_observed_integer_rgb_rim import fill_observed_rim


def current_background_measurement(rgb,initial,valid,cue,gap):
    b=pixel_box(cue)
    if b is None:return None,dict(status='no_independent_identity_cue')
    x,y,xx,yy=b;h,w=cue.shape;pad=32*max(1,gap)
    x,y,xx,yy=max(0,x-pad),max(0,y-pad),min(w,xx+pad),min(h,yy+pad)
    known=float(valid[y:yy,x:xx].mean())
    if known<.98:return None,dict(status='uncertified_initial_background',known_fraction=known)
    fg=foreground_evidence(rgb[y:yy,x:xx],initial[y:yy,x:xx],valid[y:yy,x:xx])
    vicinity=cv2.dilate(cue,np.ones((2*pad+1,2*pad+1),np.uint8))[y:yy,x:xx]>0
    n,labels,stats,_=cv2.connectedComponentsWithStats(fg.astype(np.uint8),connectivity=8)
    candidates=[(int(stats[k,cv2.CC_STAT_AREA]),-k)for k in range(1,n)if ((labels==k)&vicinity).any()]
    if not candidates:return None,dict(status='no_current_rgb_foreground')
    _,k=max(candidates);m=np.zeros_like(cue);m[y:yy,x:xx]=(labels==-k)
    return m,dict(status='independent_current_rgb_with_nonrecovered_identity_cue',known_fraction=known,box=pixel_box(m),roi=[x,y,xx,yy],cue_gap=gap)


def main():
 r=Path(sys.argv[1]);cv2.setNumThreads(1);protocol=json.loads((r/'sam31_visible_projection_full30_protocol.json').read_text())
 for name,sha in protocol['observation_sources'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==sha
 jobs={j['id']:j for j in map(json.loads,(r/'sam31_rgb_health_full30_jobs.jsonl').read_text().splitlines())}
 base={t['id']:t for t in map(json.loads,(r/'runs/sam31_rgb_certified_full30_tracks.jsonl').read_text().splitlines())};updates={};dirs={}
 for w in range(4):
  rows=list(map(json.loads,(r/'runs'/f'sam31_initial_actual_foreground_w{w}_tracks.jsonl').read_text().splitlines()));expected=list(map(json.loads,(r/f'sam31_initial_actual_foreground_w{w}_jobs.jsonl').read_text().splitlines()));assert{t['id']for t in rows}=={j['id']for j in expected}
  for t in rows:
   updates[t['id']]=t;dirs[t['id']]=r/'runs'/f'sam31_initial_actual_foreground_w{w}_masks'
 assert len(updates)==58 and len(base)==len(jobs)==1038
 def load(directory,stem,f):
  p=directory/f'{stem}_{f}.npz'
  return np.load(p)['mask'].astype(np.uint8)if p.exists()else None
 output=r/'runs/sam31_visible_projection_full30_tracks.jsonl';assert not output.exists();outdir=r/'runs/sam31_visible_projection_full30_masks';outdir.mkdir(exist_ok=True)
 visual=r/'runs/sam31_visible_projection_full30_actual';visual.mkdir(exist_ok=True)
 with output.open('w')as writer:
  for id,j in jobs.items():
   t=copy.deepcopy(base[id]);u=updates.get(id);stem=hashlib.sha256(id.encode()).hexdigest()[:12];source=r/'runs/sam31_rgb_certified_full30_masks'
   cap=cv2.VideoCapture(j['video']);cap.set(cv2.CAP_PROP_POS_FRAMES,j['prompt_frame']);ok,initial=cap.read();assert ok;valid=initial_background_valid(initial.shape[:2],j['scene_boxes']);images=[];masks=[];choices=[]
   grounded=u is not None and 'selected_initial_obj_id'in u and any(b is not None for b in u['boxes'])
   for k,f in enumerate(t['frames']):
    cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,rgb=cap.read();assert ok;images.append(rgb);old=load(source,stem,f)if t['boxes'][k]is not None else None
    if grounded:
     m=load(dirs[id],stem,f)if u['boxes'][k]is not None else None
     m,a=choose_actual_mask(rgb,initial,valid,m,old)
    else:m,a=old,dict(route='unchanged_initial_identity')
    masks.append(m);a['frame']=f;choices.append(a)
   cap.release()
   # Recovered masks must never be the identity cue for another recovery.
   recovered={a['frame']for a in t['rgb_health_recovery']if a['status']=='current_rgb_instance_crop'}
   recovery_audit=[]
   independent=[k for k,f in enumerate(t['frames'])if masks[k]is not None and (f not in recovered or (grounded and u['boxes'][k]is not None))]
   for k,f in enumerate(t['frames']):
    if f not in recovered and masks[k]is not None:continue
    if not independent:recovery_audit.append(dict(frame=f,status='no_independent_actual_observation'));continue
    q=min(independent,key=lambda q:(abs(t['frames'][q]-f),q));m,a=current_background_measurement(images[k],initial,valid,masks[q],abs(t['frames'][q]-f))
    if m is not None:masks[k]=m
    a.update(frame=f,cue_frame=t['frames'][q]);recovery_audit.append(a)
   idx=[k for k,m in enumerate(masks)if m is not None]
   if grounded and len(idx)>=4:
    fixed,cleanup=repair_certified([images[k]for k in idx],[masks[k]for k in idx],initial,valid)
    for k,m in zip(idx,fixed):masks[k]=m
   else:cleanup=[]
   rim=[];boxes=[]
   for k,f in enumerate(t['frames']):
    m=masks[k]
    if m is None:boxes.append(None);rim.append(dict(frame=f,status='missing_actual_mask',added_pixels=0));continue
    m,a=fill_observed_rim(images[k],initial,valid,m);a['frame']=f;rim.append(a);boxes.append(pixel_box(m));np.savez_compressed(outdir/f'{stem}_{f}.npz',mask=m)
    if j.get('review_actual_rgb'):
     im=images[k].copy();cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(im,cs,-1,(0,255,0),1);x,y,xx,yy=boxes[-1];im=im[max(0,y-15):yy+15,max(0,x-15):xx+15];cv2.imwrite(str(visual/f'{stem}_{f}.png'),cv2.resize(im,None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST))
   if grounded:t['initial_actual_foreground_identity']=u.get('initial_identity_repair','original_positive_membership');t['initial_actual_foreground_candidates']=u['initial_candidates']
   t['boxes']=boxes;t['reasons']=['actual_integer_rgb_certified_mask'if b else'missing_actual_mask'for b in boxes];t['box_mode']='prefix_initial_foreground_visible_projection_pixel';t['observation_runner_sha256']=protocol['observation_sources'][Path(__file__).name];t['initial_actual_foreground_choices']=choices;t['independent_recovery_audit']=recovery_audit;t['visible_projection_integer_rim']=rim;t['initial_actual_foreground_cleanup']=cleanup
   assert t['frames']==j['frames']and len(boxes)==len(j['frames']);assert all(b is None or all(isinstance(v,int)for v in b)for b in boxes)
   writer.write(json.dumps(t)+'\n');writer.flush()
 print(json.dumps({'processed':len(jobs),'input_frames':13918,'prefix_frames':79687}),flush=True)

if __name__=='__main__':main()
