"""Read-only geometric disposition of T03's internal depth diagnostic.

The maximum diagnostic row combines a maximum scalar with the first row's
position/normal. It is not a synchronized peak pose. Check a pose-independent
upper bound and separately compute oriented-box overlap at every saved frame;
never present saved-frame geometry as an internal-substep reconstruction.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json,math
from pathlib import Path
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def axes(q):
 x,y,z,w=q;n=math.sqrt(sum(v*v for v in q));x,y,z,w=[v/n for v in q]
 return[[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w)],
  [2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)],
  [2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)]]
def box_depth(a,sa,b,sb):
 aa,bb=axes(a['quaternion_xyzw']),axes(b['quaternion_xyzw']);delta=[x-y for x,y in zip(a['position'],b['position'])]
 candidates=aa+bb+[cross(x,y)for x in aa for y in bb];depth=float('inf')
 for v in candidates:
  norm=math.sqrt(dot(v,v))
  if norm<1e-10:continue
  v=[x/norm for x in v]
  radius=sum(abs(dot(v,ax))*size/2 for ax,size in zip(aa,sa))+sum(abs(dot(v,ax))*size/2 for ax,size in zip(bb,sb))
  overlap=radius-abs(dot(v,delta))
  if overlap<=0:return 0.
  depth=min(depth,overlap)
 return depth
rows=[]
for p in POINTS:
 path=Path(p['state_path']);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==p['state_sha256']
 s=json.loads(gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw)
 assert len(s['frames'])==210
 specs={o['name']:o.get('spec',o)for o in s['dynamic_objects']}
 book='t03v5_impulsed_book';slab='t03v5_upper_tabletop_collision_slab'
 size=specs[book].get('collision_proxy_size',specs[book]['size']);ss=specs[slab]['size']
 assert specs[book]['collision_proxy']=='box'and specs[slab]['shape']=='box'
 assert specs[slab]['fixed']and specs[slab]['pose']['euler_xyz']==[0.,0.,0.]
 # Along the fixed slab's z separating axis, even a maximally rotated book
 # has a half-extent no greater than its half-diagonal. Minimum translation
 # overlap therefore cannot exceed this bound, at ANY internal pose.
 bound=math.sqrt(sum(x*x for x in size))/2+ss[2]/2
 saved=[];peaks=[];exterior_peak=0.
 for f in s['frames'][4:155]:
  obs={o['name']:o for o in f['objects']}
  saved.append(dict(frame=f['frame_index'],oriented_box_translation_overlap_m=box_depth(obs[book],size,obs[slab],ss)))
  for c in f.get('contacts',[]):
   if{c['entity_a'],c['entity_b']}=={book,slab}:peaks.append(dict(c,frame=f['frame_index']))
  exterior_peak=max(exterior_peak,max((c.get('penetration_m',0)for c in f.get('original_exterior_contacts',[])if{c['entity_a'],c['entity_b']}=={book,slab}),default=0))
 peak=max(peaks,key=lambda c:c.get('penetration_m',0),default={})
 rows.append(dict(kind=p['kind'],theta=p['theta'],state_path=str(path),state_sha256=p['state_sha256'],
  box_pair=[book,slab],book_collision_size=size,slab_collision_size=ss,
  pose_independent_geometric_depth_upper_bound_m=bound,
  maximum_internal_reported_depth_m=peak.get('penetration_m',0),peak_report=peak,
  reported_depth_exceeds_any_pose_box_overlap_bound=peak.get('penetration_m',0)>bound,
  maximum_saved_frame_box_overlap_m=max(x['oriented_box_translation_overlap_m']for x in saved),
  saved_frames_above_1mm=[x for x in saved if x['oriented_box_translation_overlap_m']>.001],
  maximum_render_step_exterior_pair_depth_m=exterior_peak,
  internal_peak_pose_reconstructed=False,all_saved_frames_finite=all(math.isfinite(v)for f in s['frames'][4:155]for o in f['objects']for v in o['position']),
  formal_admission=False))
 del s
print(json.dumps(dict(points=rows,source_files_modified=False,new_simulations=0,
 conclusion='Internal maxima incompatible with geometric box overlap must not be reported as observed centimeter penetration. Saved-frame overlap is independently measured; no internal-substep convergence or general physical certification is asserted.')))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','collect']);args=parser.parse_args()
    points=[]
    for name in ['T03_ORIGINAL_GPU_SOURCE_RESULT.json','T03_ORIGINAL_GPU_ENDPOINTS_RESULT.json']:
        pointer=json.loads((WORK/name).read_text());path=ROOT/pointer['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
        report=json.loads(path.read_text())
        for p in report.get('points',[report]):
            assert p['status']=='completed'
            points.append(dict(kind='source'if name=='T03_ORIGINAL_GPU_SOURCE_RESULT.json'else'endpoint',theta=p.get('theta',.1),state_path=p['state_path'],state_sha256=p['state_sha256']))
    payload='POINTS='+repr(points)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode();digest=hashlib.sha256(payload.encode()).hexdigest()
    code=r'''
import hashlib,json,subprocess
from pathlib import Path
root=Path('/data_cached/wangzijun_p25/liyuhan/core100_v2_t03_contact_geometry_20261102');root.mkdir(exist_ok=True)
p=root/(DIGEST+'.py');out=root/(DIGEST+'.json');receipt=root/(DIGEST+'_dispatch.json')
if ACTION=='start':
 if not receipt.exists():
  p.write_text(PAYLOAD)
  with out.open('x')as f, (root/(DIGEST+'.stderr')).open('x')as err:
   proc=subprocess.Popen(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python',str(p)],stdin=subprocess.DEVNULL,stdout=f,stderr=err,start_new_session=True)
  receipt.write_text(json.dumps(dict(pid=proc.pid,script=str(p),output=str(out))))
 print(receipt.read_text())
else:
 d=json.loads(receipt.read_text());process=Path('/proc',str(d['pid']),'cmdline')
 if process.exists()and str(p).encode()in process.read_bytes():print(json.dumps(dict(status='running',pid=d['pid'])))
 else:
  report=json.loads(out.read_text());print(json.dumps(dict(status='completed',result=report)))
'''
    prefix='DIGEST='+repr(digest)+'\nACTION='+repr(args.action)+'\nPAYLOAD='+repr('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')+'\n'
    result=rpc(P21_OPTIONS,'p25',prefix+code)
    raw=json.dumps(result,indent=2).encode();sha=hashlib.sha256(raw).hexdigest();path=WORK/('t03_geometry_'+args.action+'_'+sha[:12]+'.json');path.write_bytes(raw)
    (WORK/('T03_CONTACT_GEOMETRY_'+args.action.upper()+'.json')).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha),indent=2))
    if args.action=='collect'and result.get('status')=='completed':
        for p in result['result']['points']:
            print(json.dumps({k:p[k]for k in ['kind','theta','reported_depth_exceeds_any_pose_box_overlap_bound','maximum_saved_frame_box_overlap_m','maximum_render_step_exterior_pair_depth_m']}))
    else:print(json.dumps(result))


if __name__=='__main__':main()
