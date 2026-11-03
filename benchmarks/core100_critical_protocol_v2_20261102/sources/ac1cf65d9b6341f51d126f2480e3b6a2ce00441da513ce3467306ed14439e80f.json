"""Read the original T09 terminal event and saved-pose contact geometry."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from scripts.audit_core100_v2_t03_contact_geometry import REMOTE as GEOMETRY
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
rows=[]
for p in POINTS:
 path=Path(p['state_path']);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==p['state_sha256']
 s=json.loads(raw);assert len(s['frames'])==210 and s['render']['fps']==30
 upper=set(s['experiment']['supported_book_names']);table='frozen_tabletop_collision_slab'
 specs={o['name']:o.get('spec',o)for o in s['dynamic_objects']};names=sorted(specs)
 assert all(o['shape']=='box'for o in specs.values())
 contacts=[];max_geometry=0.;peak_geometry=None;terminal=[];history=[]
 for f in s['frames'][4:210]:
  obs={o['name']:o for o in f['objects']}
  if f['frame_index']>=s['render']['pre_static_frames']:exterior=f['original_exterior_contacts']
  else:exterior=f.get('contacts',[])
  target=[c for c in exterior if any({c['entity_a'],c['entity_b']}=={name,table}for name in upper)]
  label=int(bool(target))
  if label:history.append(f['frame_index'])
  for i,a in enumerate(names):
   for b in names[i+1:]:
    depth=box_depth(obs[a],specs[a].get('collision_proxy_size',specs[a]['size']),obs[b],specs[b].get('collision_proxy_size',specs[b]['size']))
    if depth>max_geometry:max_geometry=depth;peak_geometry=dict(frame=f['frame_index'],pair=[a,b],depth_m=depth)
  if f['frame_index']>=200:
   actor_names=sorted({c['entity_a']if c['entity_a']!=table else c['entity_b']for c in target})
   tabletop=specs[table]['pose']['position'][2]+specs[table]['size'][2]/2
   clearance=[]
   for name in actor_names:
    sizes=specs[name].get('collision_proxy_size',specs[name]['size']);ax=axes(obs[name]['quaternion_xyzw'])
    bottom=obs[name]['position'][2]-sum(abs(a[2])*size/2 for a,size in zip(ax,sizes))
    clearance.append(abs(bottom-tabletop))
   terminal.append(dict(frame=f['frame_index'],label=label,upper_books_on_table=sorted({c['entity_a']if c['entity_a']!=table else c['entity_b']for c in target}),
    maximum_target_bottom_to_table_plane_distance_m=max(clearance,default=0),
    minimum_target_bottom_to_table_plane_distance_m=min(clearance,default=0),
    independently_confirmed_top_contact_witness_books=[name for name,distance in zip(actor_names,clearance)if distance<=.001],
    target_table_maximum_contact_depth_m=max((c.get('penetration_m',0)for c in target),default=0),
    all_target_contacts_inside_support=all(abs(c['position'][i]-specs[table]['pose']['position'][i])<=specs[table]['size'][i]/2+.0001 for c in target for i in [0,1])))
 rows.append(dict(theta=p['theta'],source_repeat=p['source_repeat'],state_path=str(path),state_sha256=p['state_sha256'],
  source_state_sha256=p['source_state_sha256'],reference_video_sha256=p['reference_video_sha256'],
  original_configuration_seed_solver_and_clock_verified=p['actual_objects_solver_seed_control_and_clock_verified'],
  window=[4,209],native_fps=30,simulation_frame_period_s=s['scene_overrides']['dt']*s['render']['physics_steps_per_render_frame'],
  original_source_position_error_m=p['source_position_error_m'],
  target_contact_history=history,terminal_frames=terminal,
  maximum_saved_frame_obb_overlap_m=max_geometry,maximum_saved_geometry=peak_geometry,
  all_saved_positions_finite=all(math.isfinite(v)for f in s['frames'][4:210]for o in f['objects']for v in o['position']),
  raw_native_depth_diagnostic=p['native_depth_diagnostic'],formal_admission=False))
 del s
print(json.dumps(dict(clip_id='T09_C01',points=rows,original_event='upper_nonpulled_book_on_table_at_end',
 source_files_modified=False,new_simulations=0,scope='Original terminal table contact at native frame209. Saved-pose OBB geometry does not reconstruct internal peak poses or establish physical convergence.')))
'''


def main():
    pointer=json.loads((WORK/'LEGACY_EXACT_COLLECT.json').read_text());path=ROOT/pointer['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
    points=[p for p in json.loads(path.read_text())['points']if p['clip_id']=='T09_C01']
    assert len(points)==4 and all(p['status']=='completed'for p in points)
    payload='POINTS='+repr(points)+'\n'+GEOMETRY.split('rows=[]')[0]+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    result['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in[path,Path(__file__),ROOT/'scripts/audit_core100_v2_t03_contact_geometry.py']}
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t09_terminal_geometry_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T09_TERMINAL_GEOMETRY.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    for p in result['points']:
        print(json.dumps(dict(theta=p['theta'],maximum_saved_geometry=p['maximum_saved_geometry'],
            terminal_labels=[f['label']for f in p['terminal_frames']],terminal_target_depth_m=max(f['target_table_maximum_contact_depth_m']for f in p['terminal_frames']))))


if __name__=='__main__':main()
