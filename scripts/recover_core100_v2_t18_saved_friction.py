"""Read existing T18 friction states using the registered table-contact rule."""
import hashlib
import inspect
import json
from pathlib import Path
from scripts.t18_table_contact_boundary_worker import table_event
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS
from physedit.core100_critical import load

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
def norm(v):
 if isinstance(v,float):return round(v,9)
 if isinstance(v,list):return[norm(x)for x in v]
 if isinstance(v,dict):return{k:norm(x)for k,x in v.items()}
 return v
def read_point(path):
 packed=path.read_bytes();raw=gzip.decompress(packed)if packed[:2]==bytes([31,139])else packed
 state=json.loads(raw);e=state['experiment'];theta=e['parameter']['parameter_value']
 specs={o['name']:copy.deepcopy(o.get('spec',o))for o in state['dynamic_objects']}
 for name,o in specs.items():
  if name.startswith('t18_book_'):
   assert abs(o.pop('friction')-theta)<1e-9
   if'friction'in o.get('material_preset',{}):assert abs(o['material_preset'].pop('friction')-theta)<1e-9
 keys=['gravity','dt','substeps','solver_iterations','settle_steps','record_contacts','static_scene_collision',
  'layout_collision','add_ground_plane','room_wall_colliders','room_boundary_safety','use_gjk_collision',
  'enable_multi_contact','box_box_detection','constraint_timeconst','iterations','ls_iterations','noslip_iterations']
 context=norm(dict(objects=specs,physics={k:state['scene_overrides'].get(k)for k in keys},
  supported_book_names=e['supported_book_names'],pre_static_frames=state['render']['pre_static_frames'],
  steps_per_frame=state['render']['physics_steps_per_render_frame']))
 period=state['scene_overrides']['dt']*state['render']['physics_steps_per_render_frame'];assert abs(period*150-5)<1e-12
 label=table_event(state,state['frames'][154])
 return dict(theta=theta,labels={'upper_nonpulled_book_on_table_at_end':label['label']},
  sample_id=path.parent.parent.name,source_state_path=str(path),stored_state_sha256=hashlib.sha256(packed).hexdigest(),
  decoded_state_sha256=hashlib.sha256(raw).hexdigest(),fixed_context_sha256=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest(),
  evidence=label,horizon_s=5.0,end_frame_index=154)
cases=[]
for target in TARGETS:
 source_path=Path(target['state_path']);source=read_point(source_path)
 assert target['source_state_sha256']in[source['stored_state_sha256'],source['decoded_state_sha256']]
 prefix=target['sample_id'].rsplit('__p',1)[0]+'__p'
 paths=sorted(source_path.parents[2].glob(prefix+'*/metadata/*__cam01.json.gz'))
 points=[];failures=[]
 for path in paths:
  try:points.append(read_point(path))
  except Exception as exc:failures.append(dict(path=str(path),error=type(exc).__name__+': '+str(exc)))
 own=[p for p in points if p['fixed_context_sha256']==source['fixed_context_sha256']]
 groups={}
 for p in own:groups.setdefault(round(p['theta'],10),[]).append(p)
 unique=[]
 for theta,rows in sorted(groups.items()):
  labels={p['labels']['upper_nonpulled_book_on_table_at_end']for p in rows}
  unique.append(dict(theta=theta,label=next(iter(labels))if len(labels)==1 else None,points=rows))
 intervals=[]
 for a,b in zip(unique,unique[1:]):
  if a['label']in(0,1)and b['label']in(0,1)and a['label']!=b['label']:
   intervals.append(dict(bracket=[a['theta'],b['theta']],labels=[a['label'],b['label']],endpoints=[a['points'],b['points']]))
 cases.append(dict(clip_id=target['clip_id'],source=source,points_read=len(points),points_failed=failures,
  same_original_context_points=len(own),observed_values=[dict(theta=p['theta'],label=p['label'])for p in unique],
  intervals=intervals,reference_label=target['reference_label'],reference_video_sha256=target['reference_video_sha256'],
  formal_admission=False,scope='Read-only existing native states; release-version endpoint provenance is not auto-approved.'))
print(json.dumps(dict(cases=cases,new_simulations=0,original_files_modified=False)))
'''


def main():
    data,_=load();readback=json.loads((ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json').read_text(encoding='utf8'))
    sources={r['clip_id']:r['points'][0]for r in readback}
    targets=[dict(clip_id=r['clip_id'],sample_id=r['sample_id'],state_path=sources[r['clip_id']]['state_path'],
        source_state_sha256=r['source_state_sha256'],reference_label=r['reference_events']['upper_nonpulled_book_on_table_at_end'],
        reference_video_sha256=r['reference_video_sha256'])for r in data['cases']if r['scene_id']=='T18'and r['parameter']=='contact_friction']
    code='TARGETS='+repr(targets)+'\n'+inspect.getsource(table_event)+'\n'+REMOTE
    result=rpc(P21_OPTIONS,'p25',code)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t18_saved_friction_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T18_SAVED_FRICTION.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=c['clip_id'],read=c['points_read'],failed=len(c['points_failed']),
        matched=c['same_original_context_points'],intervals=[i['bracket']for i in c['intervals']])for c in result['cases']]))


if __name__=='__main__':main()
