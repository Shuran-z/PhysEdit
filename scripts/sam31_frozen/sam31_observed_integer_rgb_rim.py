"""Fill an omitted integer rim only with independent current RGB evidence.

The SAM3.1 mask is the target identity cue. No fit, target gravity, reference
trajectory, geometric reference boundary or future frames are inputs. Output
is an integer binary mask; no continuous/subpixel boxes are generated.
"""
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from sam31_rgb_observation_health import foreground_evidence


def fill_observed_rim(rgb, initial, valid, neural):
    m=np.asarray(neural,dtype=np.uint8)
    yy,xx=np.where(m)
    if not len(xx):return m.copy(),dict(status='empty_mask',added_pixels=0)
    h,w=m.shape
    x,y,x1,y1=max(0,int(xx.min())-4),max(0,int(yy.min())-4),min(w,int(xx.max())+5),min(h,int(yy.max())+5)
    old=m[y:y1,x:x1]>0
    core=cv2.erode(old.astype(np.uint8),np.ones((3,3),np.uint8))>0
    if core.sum()<16:return m.copy(),dict(status='insufficient_observed_interior',added_pixels=0)
    distance=distance_transform_edt(~old)
    _,indices=distance_transform_edt(~core,return_indices=True)
    current=rgb[y:y1,x:x1].astype(np.float32)
    bg=initial[y:y1,x:x1].astype(np.float32)
    interior=current[indices[0],indices[1]]
    direction=interior-bg
    denom=np.sum(direction*direction,axis=-1)
    alpha=np.sum((current-bg)*direction,axis=-1)/np.maximum(denom,1)
    residual=np.max(np.abs(current-(bg+alpha[...,None]*direction)),axis=-1)
    # Half-colour binary membership, bounded to two raster pixels around
    # an actually measured target. Ambiguous colours/backgrounds stay intact.
    independently_changed=foreground_evidence(rgb[y:y1,x:x1],initial[y:y1,x:x1],valid[y:y1,x:x1])
    candidate=(~old)&(distance<=2)&independently_changed&(denom>=144)&(alpha>=.5)&(alpha<=1.25)&(residual<=8)
    out=m.copy();out[y:y1,x:x1][candidate]=1
    return out,dict(status='independent_integer_rgb_rim',added_pixels=int(candidate.sum()),roi=[x,y,x1,y1])
