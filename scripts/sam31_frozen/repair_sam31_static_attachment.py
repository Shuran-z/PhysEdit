"""Remove only RGB-supported static background attached to a SAM3.1 mask.

At least three other observed frames must expose the same pixel outside the
two-pixel dilated target mask, with stable background colour (range <=12).
Current colour must match that background within20 levels in every channel,
allowing local cast-shadow variation ONLY if its channel ratios match the
observed background. Brighter or differently coloured object material is
retained even when every channel differs by less than20. The guard allows two
8-bit levels per channel for quantisation; no gravity or geometry enters.
Only candidates connected to the existing mask exterior are considered. Each
removed attachment must occupy >=5% of the original mask; scattered small rim
pixels remain untouched because similarly coloured object rims can match the
background. Interior holes remain. All frames and integer coordinates remain.
"""
import cv2
import numpy as np


def _repair_core(images, masks):
    assert len(images)==len(masks)>=4
    rgb=np.asarray(images,dtype=np.int16)
    masks=np.asarray(masks,dtype=np.uint8)
    assert rgb.shape[:3]==masks.shape
    cv2.setNumThreads(1)
    dilated=np.array([cv2.dilate(m,np.ones((5,5),np.uint8))>0 for m in masks])
    background_count=(~dilated).sum(axis=0)
    exposed=np.where((~dilated)[...,None],rgb,np.nan)
    # Median colour of observed exposed background; range verifies consistency.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        background=np.nanmedian(exposed,axis=0)
        spread=np.nanmax(exposed,axis=0)-np.nanmin(exposed,axis=0)
    stable=(background_count>=3)&(spread.max(axis=-1)<=12)
    # Use observed background channel variability as the colour uncertainty.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        low=np.nanmin(exposed,axis=0);high=np.nanmax(exposed,axis=0)
    outputs=[];audit=[]
    for i,m in enumerate(masks):
        same_colour=np.max(np.abs(rgb[i]-background),axis=-1)<=20
        # Absolute RGB tolerance alone confuses real dark green/red covers
        # with the nearby dark tabletop. A cast shadow must dim, not brighten,
        # the background while preserving its colour direction.
        bden=np.sum(background*background,axis=-1)
        scale=np.sum(rgb[i]*background,axis=-1)/np.maximum(bden,1)
        quantisation_match=np.all((rgb[i]>=low-2)&(rgb[i]<=high+2),axis=-1)
        colour_noise=2+np.maximum(scale,0)[...,None]*spread
        shadow_match=(scale>=0)&(scale<=1)&np.all(np.abs(rgb[i]-scale[...,None]*background)<=colour_noise,axis=-1)
        colour_supported=quantisation_match|shadow_match
        # Strong colour evidence seeds an attached region. Permit its RGB-
        # matching codec fringe only when a majority of the whole attachment
        # and >=5% of the original mask have independent colour support.
        candidate=(m>0)&stable&same_colour
        # Retain candidates enclosed by original foreground; remove only a
        # continuous attachment to known exterior background.
        outside=(m==0)
        admissible=(candidate|outside).astype(np.uint8)
        n,labels,_,_=cv2.connectedComponentsWithStats(admissible,connectivity=8)
        exterior_labels=np.unique(labels[outside])
        supported=candidate&np.isin(labels,exterior_labels)
        n,parts,stats,_=cv2.connectedComponentsWithStats(supported.astype(np.uint8),connectivity=8)
        retained_parts=[]
        for k in range(1,n):
            area=int(stats[k,cv2.CC_STAT_AREA])
            strong=int(np.sum((parts==k)&colour_supported))
            if strong>=0.05*m.sum() and strong>=0.5*area:
                retained_parts.append(k)
        removed=np.isin(parts,retained_parts)
        fixed=m.copy();fixed[removed]=0
        # RGB equality cannot distinguish a foreground object from a matching
        # flat background. Keep its actual SAM observation rather than erase
        # all foreground or abort a full-set pass.
        ambiguous=bool(m.sum()>0 and fixed.sum()==0)
        if ambiguous:fixed=m.copy();removed[:]=False
        outputs.append(fixed)
        audit.append(dict(frame_index=i,before_pixels=int(m.sum()),removed_background_pixels=int(removed.sum()),after_pixels=int(fixed.sum()),ambiguous_rgb_retained=ambiguous))
    return outputs,audit


def repair(images, masks):
    # All decisions concern foreground pixels and their 2px dilation. Limit
    # median/range/connectivity work to the observed-mask union plus a 3px
    # exterior margin; pixel decisions and every fitting frame stay identical.
    assert len(images)==len(masks)>=4
    ms=np.asarray(masks,dtype=np.uint8)
    yy,xx=np.where(ms.any(axis=0))
    if not len(xx):
        return _repair_core(images,masks)
    h,w=ms.shape[1:]
    x0=max(0,int(xx.min())-3);x1=min(w,int(xx.max())+4)
    y0=max(0,int(yy.min())-3);y1=min(h,int(yy.max())+4)
    crops=[im[y0:y1,x0:x1] for im in images]
    fixed,audit=_repair_core(crops,ms[:,y0:y1,x0:x1])
    result=[]
    for original,cropped in zip(ms,fixed):
        m=original.copy();m[y0:y1,x0:x1]=cropped;result.append(m)
    return result,audit
