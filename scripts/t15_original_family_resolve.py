"""Bounded original-backend probes; run on p25. Never overwrite release files."""
import argparse,copy,hashlib,json,os,subprocess,time
from pathlib import Path
BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
OUT=Path('/data_cached/wangzijun_p25/liyuhan/critical_family_resolve_20261018')
PY='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
FIELDS={'cfA':'initial_velocity_mps','cfB':'laptop_edge_margin_m','cfC':'phone_offset_y_scan_m'}
ALLOWED={'cfA':{('t15v4_driver_book','motion','initial_velocity',0)},
 'cfB':{('t15v4_driver_book','pose','position',0),('t15v4_closed_laptop','pose','position',0)},
 'cfC':{('t15v4_floor_phone','pose','position',1)}}
def differences(a,b,path=()):
 if isinstance(a,dict) and isinstance(b,dict):
  if set(a)!=set(b):return [path]
  return [p for k in a for p in differences(a[k],b[k],path+(k,))]
 if isinstance(a,list) and isinstance(b,list):
  if len(a)!=len(b):return [path]
  return [p for k in range(len(a)) for p in differences(a[k],b[k],path+(k,))]
 return [] if a==b else [path]
def get(x,path):
 for k in path:x=x[k]
 return x
def put(x,path,value):
 for k in path[:-1]:x=x[k]
 x[path[-1]]=value
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--extended',action='store_true');parser.add_argument('--refined',action='store_true');args=parser.parse_args()
 if args.extended and args.refined:raise ValueError('choose one scan stage')
 if args.extended:OUT=OUT.with_name(OUT.name+'_extended')
 if args.refined:OUT=OUT.with_name(OUT.name+'_refined')
 OUT.mkdir(exist_ok=False)
 manifest=json.loads((BASE/'configs/v11_20260914/delivery/manifest.json').read_text())
 records=[]
 for family,field in FIELDS.items():
  if args.refined and family=='cfA':continue
  candidates=[r for r in manifest if r['background_id']=='bg01_home_ase' and r['gravity_id']=='g03_earth' and r['slot'].startswith(family+'_') and r['slot'].endswith('rep01')]
  configs=[json.loads(Path(r['config']).read_text()) for r in candidates]
  items=sorted(zip(candidates,configs),key=lambda x:x[1]['sample_metadata'][field])
  entry={'family':family,'parameter_field':field,'references':[{**r,'config_sha256':sha(Path(r['config']))} for r,c in items]}
  records.append(entry)
  if len(items)!=3:
   entry['status']='blocked_missing_original_triplet';continue
  lo,mid,hi=[c for r,c in items];a,b=[c['sample_metadata'][field] for c in [lo,hi]]
  objects=[{o['name']:o for o in c['dynamic_objects']} for c in [lo,mid,hi]]
  diff=differences(objects[0],objects[2]);unexpected=set(diff)-ALLOWED[family]
  if unexpected or not diff or b==a:
   entry.update(status='blocked_original_intervention_mapping',different_paths=[list(p) for p in diff],unexpected_paths=[list(p) for p in unexpected]);continue
  ratio=(mid['sample_metadata'][field]-a)/(b-a)
  reconstructed=copy.deepcopy(objects[0])
  for path in diff:put(reconstructed,path,get(objects[0],path)+ratio*(get(objects[2],path)-get(objects[0],path)))
  mid_errors=[p for p in differences(reconstructed,objects[1]) if not isinstance(get(reconstructed,p),(int,float)) or abs(get(reconstructed,p)-get(objects[1],p))>1e-9]
  if mid_errors:
   entry.update(status='blocked_non_affine_original_mapping',different_paths=[list(p) for p in mid_errors]);continue
  folder=OUT/family;folder.mkdir();rows=[]
  # Original endpoints plus new quarter points; no unvalidated extrapolation.
  values=sorted(set([a+(b-a)*i/8 for i in range(9)]+[mid['sample_metadata'][field]]))
  if args.extended:
   bounds={'cfA':(2.088,2.160),'cfB':(.02,.30),'cfC':(-.30,.40)}[family]
   values=sorted(set([round(bounds[0]+(bounds[1]-bounds[0])*i/8,9) for i in range(9)]+[a,mid['sample_metadata'][field],b]))
   values=[x for x in values for repeat in range(2)]
  if args.refined:
   intervals={'cfB':[(.09,.125)],'cfC':[(-.125,-.0375),(.145,.225)]}[family]
   values=sorted({round(a+(b-a)*i/8,10) for a,b in intervals for i in range(9)})
   values=[x for x in values for repeat in range(2)]
  for i,theta in enumerate(values):
   c=copy.deepcopy(lo);byname={o['name']:o for o in c['dynamic_objects']}
   for path in diff:put(byname,path,get(objects[0],path)+(theta-a)/(b-a)*(get(objects[2],path)-get(objects[0],path)))
   sid=f'T15_original_{family}_{i:02d}';output=folder/sid;path=folder/(sid+'.json')
   c['sample_id']=sid;c['sample_metadata'][field]=theta
   c['sample_metadata'].update(calibration_only=True,formal_candidate=False,supplemental_search=True)
   c['annotations']['save_path']=str(output/'metadata/physics.json')
   path.write_text(json.dumps(c,indent=2));rows.append(dict(sample_id=sid,config=str(path),output=str(output),theta=theta))
  plan=folder/'manifest.json';plan.write_text(json.dumps(rows,indent=2))
  profile=lo['sample_metadata']['physics_profile'];steps=round(1/(30*profile['solver_dt_s']))
  command=[PY,str(BASE/'scripts/t15_v11_physics.py'),'--manifest',str(plan),'--steps',str(steps),'--timeconst',str(profile['constraint_timeconst']),'--precision',str(profile['precision_bits'])]
  if profile['box_box_detection']:command.append('--box')
  if profile['settle_seconds']==1.:command.append('--settle')
  if profile['integrator']=='implicitfast':command.append('--exact')
  entry.update(status='running',command=command,solver_script_sha256=sha(BASE/'scripts/t15_v11_physics.py'),original_profile=profile,planned_points=len(rows))
  (OUT/'status.json').write_text(json.dumps(records,indent=2))
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='2')
  with (folder/'run.log').open('w') as log:
   try:p=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
   except subprocess.TimeoutExpired:entry['status']='solver_timeout';continue
  entry.update(status='completed' if p.returncode==0 else 'solver_failed',returncode=p.returncode)
  if (folder/'results.json').exists():
   results=json.loads((folder/'results.json').read_text());entry['outcomes']=[{'theta':r['theta'],'valid':r['audit'].get('valid'),'event_frames':r['audit'].get('event_frames'),'errors':r['audit'].get('errors')} for r in results]
  (OUT/'status.json').write_text(json.dumps(records,indent=2))
 (OUT/'status.json').write_text(json.dumps(records,indent=2));print(json.dumps(records))
if __name__=='__main__':main()
