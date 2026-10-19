"""Compare physics recorded during calibration with formal configuration, by original axis."""
import copy,collections,json
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def physics(c,family,metadata=False):
 objects=[]
 for original in c.get('dynamic_objects',[]):
  o=original.get('spec',original)
  if o.get('collision') is False:continue
  row={k:copy.deepcopy(v) for k,v in o.items() if k in ['name','shape','size','radius','height','mass','friction','restitution','fixed','pose','motion','collision','collision_mesh_path','convexify','linear_damping','angular_damping','ccd_enabled','contact_offset','disable_sleep']}
  name=o.get('name','')
  if family=='A' and name=='t02v2_striker_eraser':row['pose']['position'][0]='INTERVENTION'
  if family=='B' and name=='t02v2_striker_eraser':row['motion']['initial_velocity'][1]='INTERVENTION'
  if family=='C' and name=='t02v2_probe_marble':
   v=row['motion']['initial_velocity'][0];w=row['motion']['initial_angular_velocity'][1]
   assert abs(w-v/row['radius'])<1e-8, 'unverified derived rolling velocity'
   row['motion']['initial_velocity'][0]='INTERVENTION';row['motion']['initial_angular_velocity'][1]='DERIVED_V_OVER_RADIUS'
  objects.append(row)
 scene={k:v for k,v in c.get('scene_overrides',{}).items() if not k.startswith('raytracing') and k not in ['static_visual_only_instance_ids']}
 render={k:c.get('render',{}).get(k) for k in ['frames','fps','pre_static_frames','physics_steps_per_render_frame']}
 return dict(objects=sorted(objects,key=lambda x:x['name']),scene=scene,render=render)
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [x for k in set(a)|set(b) for x in diff(a.get(k),b.get(k),path+'/'+str(k))]
 if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):return [x for i,(u,v) in enumerate(zip(a,b)) for x in diff(u,v,path+'/'+str(i))]
 return [] if a==b else [dict(path=path,calibration=a,formal=b)]
def main():
 bindings=json.loads(Path('review/original_search_tasks_20261018/t02_original_family_bindings.json').read_text(encoding='utf-8'))
 meta={r['path']:r for r in json.loads((OUT/'t02_calibration_runtime_provenance.json').read_text(encoding='utf-8'))}
 configs={r['config'].get('experiment',{}).get('trajectory_id',r['config'].get('sample_id')):r['config'] for r in json.loads((OUT/'p26_configs.json').read_text(encoding='utf-8')) if 'config' in r}
 rows=[]
 for b in bindings:
  comparisons=[]
  for branch,t in b['calibrated_triplet'].items():
   m=meta[t['metadata']];a=physics(m['metadata'],b['family'],True);f=physics(configs[b['sample_id']],b['family'])
   differences=diff(a,f)
   comparisons.append(dict(branch=branch,metadata_sha256=m['sha256'],differences=differences,match=not differences))
  rows.append(dict(sample_id=b['sample_id'],family=b['family'],comparisons=comparisons,all_contexts_match=all(c['match'] for c in comparisons)))
 (OUT/'t02_runtime_context_comparison.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 reasons=collections.Counter(x['path'] for r in rows for c in r['comparisons'] for x in c['differences'])
 print(json.dumps(dict(total=len(rows),matching=sum(r['all_contexts_match'] for r in rows),difference_paths=reasons.most_common(12))))
if __name__=='__main__':main()
