"""Read T11 G-family saved poses before interpreting a native depth maximum."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from scripts.audit_core100_v2_t03_contact_geometry import REMOTE as GEOMETRY
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/t11_observable_events_candidate_v1_20261103'
REMOTE = r'''
rows=[]
for p in POINTS:
 path=Path(p['state_path']);raw=path.read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 assert hashlib.sha256(raw).hexdigest()==p['stored_state_sha256']
 assert hashlib.sha256(decoded).hexdigest()==p['decoded_state_sha256']
 s=json.loads(decoded);specs={o['name']:o.get('spec',o)for o in s['dynamic_objects']}
 pairs={};unsupported=[]
 for f in s['frames'][4:155]:
  obs={o['name']:o for o in f['objects']}
  for c in f.get('contacts',[]):
   a,b=c['entity_a'],c['entity_b'];pair=tuple(sorted([a,b]))
   if a not in specs or b not in specs:unsupported.append(list(pair));continue
   sa,sb=specs[a],specs[b]
   if not all(o.get('collision_proxy',o.get('shape'))=='box'for o in [sa,sb]):
    unsupported.append(list(pair));continue
   size_a=sa.get('collision_proxy_size',sa['size']);size_b=sb.get('collision_proxy_size',sb['size'])
   row=pairs.setdefault(pair,dict(pair=list(pair),shape_a=specs[pair[0]].get('collision_proxy_size',specs[pair[0]]['size']),shape_b=specs[pair[1]].get('collision_proxy_size',specs[pair[1]]['size']),native_peak=0.,saved_pose_peak=0.,peak_frame=None,
     native_depth_incompatible_with_any_box_overlap=False))
   depth=c.get('penetration_m',0);row['native_peak']=max(row['native_peak'],depth)
   # For two convex boxes, minimum separating translation cannot exceed the
   # sum of the shorter total box-axis widths. This is a deliberately loose
   # pose-independent upper bound, never a saved/internal pose equivalence.
   bound=min(sum(size_a)/2+min(size_b)/2,sum(size_b)/2+min(size_a)/2)
   row['pose_independent_loose_box_bound_m']=bound
   row['native_depth_incompatible_with_any_box_overlap']|=depth>bound
 for pair,row in pairs.items():
  a,b=pair;sa=specs[a].get('collision_proxy_size',specs[a]['size']);sb=specs[b].get('collision_proxy_size',specs[b]['size'])
  for f in s['frames'][4:155]:
   obs={o['name']:o for o in f['objects']}
   overlap=box_depth(obs[a],sa,obs[b],sb)
   if overlap>row['saved_pose_peak']:row.update(saved_pose_peak=overlap,peak_frame=f['frame_index'])
 rows.append(dict(kind=p['kind'],theta=p.get('theta'),stored_state_sha256=p['stored_state_sha256'],
  decoded_state_sha256=p['decoded_state_sha256'],pairs=list(pairs.values()),unsupported_pairs=sorted(set(tuple(a)for a in unsupported)),
  all_saved_positions_finite=all(math.isfinite(v)for f in s['frames'][4:155]for o in f['objects']for v in o['position']),
  source_config_sha256=p.get('config_sha256'),original_experiment=s['experiment'].get('formal_design')))
print(json.dumps(dict(rows=rows,simulations_started=0,internal_substep_poses_reconstructed=False,
 formal_admission=False,scope='Independent saved-box geometry; internal scalar telemetry is retained. No internal convergence or full physical correctness claim.')))
'''


def main():
    pointer=json.loads((OUT/'EXISTING_G_PATH_ENDPOINT_REREAD.json').read_text());path=OUT/pointer['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
    old=json.loads(path.read_text());data,_=load();native=next(r for r in data['cases']if r['clip_id']=='T11_C03')['reference_native_state_binding']
    points=[dict(r,kind='endpoint')for r in old['rows']]
    points.append(dict(kind='frozen_reference',**native))
    payload='POINTS='+repr(points)+'\n'+GEOMETRY.split('rows=[]')[0]+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();target=OUT/('G_saved_geometry_'+digest[:12]+'.json');target.write_bytes(raw)
    (OUT/'G_SAVED_GEOMETRY.json').write_text(json.dumps(dict(path=target.name,sha256=digest),indent=2))
    print(json.dumps([dict(kind=r['kind'],theta=r['theta'],unsupported=r['unsupported_pairs'],
     maximum_saved_overlap_m=max((a['saved_pose_peak']for a in r['pairs']),default=0),
     deep_pairs=[a for a in r['pairs']if a['native_peak']>.001])for r in result['rows']]))


if __name__=='__main__':main()
