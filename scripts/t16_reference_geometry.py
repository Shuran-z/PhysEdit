"""Audit/repair the T16 family using the measured canonical C04 clearance.

This is a construction parameter, not an event-scoring threshold. Old files
are never overwritten. Both repaired endpoints use the same clearance rule.
"""
import copy
import math


def folder_support_clearance(config):
    objects={o['name']:o for o in config['dynamic_objects']}
    a,b=objects['t16_folder'],objects['t16_support_book']
    assert a['collision_proxy']==b['collision_proxy']=='box'
    assert all(abs(o['pose']['euler_xyz'][i])<1e-10 for o in [a,b]for i in [0,2])
    angle=[math.radians(o['pose']['euler_xyz'][1])for o in [a,b]]
    axes=[[(math.cos(t),-math.sin(t)),(math.sin(t),math.cos(t))]for t in angle]
    half=[[o['collision_proxy_size'][i]/2 for i in [0,2]]for o in [a,b]]
    delta=[b['pose']['position'][i]-a['pose']['position'][i]for i in [0,2]]
    dot=lambda x,y:sum(v*w for v,w in zip(x,y))
    overlaps=[]
    for axis in axes[0]+axes[1]:
        radius=sum(h*abs(dot(v,axis))for hs,vs in zip(half,axes)for h,v in zip(hs,vs))
        overlaps.append(radius-abs(dot(delta,axis)))
    assert abs(a['pose']['position'][1]-b['pose']['position'][1])<(a['collision_proxy_size'][1]+b['collision_proxy_size'][1])/2
    return dict(minimum_xz_sat_overlap_m=min(overlaps),folder_normal_overlap_m=overlaps[1],
                intersects=all(v>0 for v in overlaps),axis_overlaps_m=overlaps,
                folder_normal_x=axes[0][1][0])


def repair(config,clearance):
    result=copy.deepcopy(config);before=folder_support_clearance(result)
    shift=(before['folder_normal_overlap_m']+clearance)/abs(before['folder_normal_x'])
    assert shift>=0
    book=next(o for o in result['dynamic_objects']if o['name']=='t16_support_book')
    book['pose']['position'][0]+=shift
    for keyframe in book['motion']['keyframes']:keyframe['position'][0]+=shift
    after=folder_support_clearance(result)
    assert not after['intersects'] and abs(after['folder_normal_overlap_m']+clearance)<1e-10
    return result,dict(shift_x_m=shift,before=before,after=after,shared_clearance_m=clearance)
