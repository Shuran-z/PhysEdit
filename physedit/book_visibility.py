"""Visible silhouette and censored box-edge constraints; retain every frame."""
import cv2,numpy as np

def clip_polygon(points,image_size):
    points=np.asarray(points,float)
    poly=points[cv2.convexHull(points.astype(np.float32),returnPoints=False).ravel()].copy()
    width,height=image_size
    for axis,bound,lower in [(0,-.5,True),(0,width-.5,False),(1,-.5,True),(1,height-.5,False)]:
        if len(poly)==0:break
        out=[]
        for a,b in zip(np.roll(poly,1,axis=0),poly):
            ai=a[axis]>=bound if lower else a[axis]<=bound
            bi=b[axis]>=bound if lower else b[axis]<=bound
            if ai!=bi:
                ratio=(bound-a[axis])/(b[axis]-a[axis]);out.append(a+ratio*(b-a))
            if bi:out.append(b)
        poly=np.asarray(out,float).reshape(-1,2)
    return poly

def visibility(sample):
    b=np.asarray(sample['boxes']['xyxy']);width,height=sample['image_size'];flags=sample.get('window',{}).get('edges_visible',{})
    if not isinstance(flags,dict) or any(str(f) not in flags for f in sample['boxes']['frames']):
        raise ValueError('missing_registered_book_edge_visibility')
    values=[flags[str(f)] for f in sample['boxes']['frames']]
    if any(len(v)!=4 or any(type(x) is not bool for x in v) for v in values):
        raise ValueError('invalid_registered_book_edge_visibility')
    seen=np.asarray(values,bool)
    viewport=np.c_[b[:,0]<=1,b[:,1]<=1,b[:,2]>=width-1,b[:,3]>=height-1]
    # Cropping at the camera boundary can be modeled by clipping the polygon.
    # Other-object occlusion has no full silhouette observation: use only its
    # declared visible box edges, without pretending the missing shape exists.
    shape=~np.any((~seen)&(~viewport),axis=1)
    return seen,shape,viewport


def clip_observed_polygon(points,image_size,observed_box,seen):
    poly=clip_polygon(points,image_size)
    for axis,bound,lower,visible in [(0,observed_box[0]-.5,True,seen[0]),
                                   (1,observed_box[1]-.5,True,seen[1]),
                                   (0,observed_box[2]-.5,False,seen[2]),
                                   (1,observed_box[3]-.5,False,seen[3])]:
        if visible or len(poly)==0:continue
        out=[]
        for a,b in zip(np.roll(poly,1,axis=0),poly):
            ai=a[axis]>=bound if lower else a[axis]<=bound
            bi=b[axis]>=bound if lower else b[axis]<=bound
            if ai!=bi:out.append(a+(bound-a[axis])/(b[axis]-a[axis])*(b-a))
            if bi:out.append(b)
        poly=np.asarray(out,float).reshape(-1,2)
    return poly
