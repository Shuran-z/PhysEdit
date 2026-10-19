"""Check declared inputs of representative original configurations on known hosts."""
import concurrent.futures,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def main():
 inv={r['sample_id']:r for r in [json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()] if r['engine']=='genesis'}
 chosen={}
 for file in [OUT/'p25_configs.json',OUT/'p26_configs.json']+sorted(OUT.glob('published_batch_*.json')):
  for r in json.loads(file.read_text(encoding='utf-8')):
   if 'config' not in r:continue
   c=r['config'];e=c.get('experiment',{});p=Path(r.get('path',''))
   aliases=[r.get('sample_id'),e.get('trajectory_id'),p.parent.name,p.stem.split('__cam01')[0]]
   sid=next((s for s in aliases if s in inv),None)
   if sid is None:continue
   scene=inv[sid]['event_id']
   if scene in chosen:continue
   paths=[]
   for k in ['manifest','background_profile_path']:
    if isinstance(c.get(k),str):paths.append(dict(field=k,path=c[k]))
   for o in c.get('dynamic_objects',[]):
    for k in ['visual_mesh_path','collision_mesh_path','mesh_path']:
     if isinstance(o.get(k),str):paths.append(dict(field=o.get('name','')+'.'+k,path=o[k]))
   chosen[scene]=dict(scene=scene,sample_id=sid,config_sha256=r['sha256'],required_paths=paths)
 def probe(host):
  paths=sorted({p['path'] for r in chosen.values() for p in r['required_paths'] if p['path'].startswith('/')})
  code='import json,pathlib\nprint(json.dumps({p:pathlib.Path(p).is_file() for p in '+repr(paths)+'}))'
  p=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=60)
  p.check_returncode();return host,json.loads(p.stdout)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(probe,['p25','p26']))
 for r in chosen.values():
  for p in r['required_paths']:p['exists_exact_path']={h:d.get(p['path']) for h,d in results.items()}
  r['missing_on_both']=[p for p in r['required_paths'] if all(v is False for v in p['exists_exact_path'].values())]
  r['scope']='representative config only; not proof all scene inputs missing; no path remapping performed'
 (OUT/'original_backend_input_availability.json').write_text(json.dumps(list(chosen.values()),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps([dict(scene=r['scene'],missing=len(r['missing_on_both']),checked=len(r['required_paths'])) for r in sorted(chosen.values(),key=lambda r:r['scene'])]))
if __name__=='__main__':main()
