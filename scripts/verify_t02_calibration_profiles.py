"""Recover all original T02 triplet configs/audits and compare actual solver fields."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def main():
 rows=json.loads(Path('review/original_search_tasks_20261018/t02_original_family_bindings.json').read_text(encoding='utf-8'))
 for r in rows:
  for t in r['calibrated_triplet'].values():
   if 'config' not in t:
    meta=Path(t['metadata']);root=meta.parents[3];t['config']=str(root/'configs'/meta.parents[2].name/t['sample_id']/'cam01.json').replace('\\','/')
 paths=sorted({p for r in rows for t in r['calibrated_triplet'].values() for p in [t['config'],t['audit']]})
 code=r'''
import pathlib,json,hashlib,base64,gzip
result=[]
for name in PATHS:
 try:
  p=pathlib.Path(name);b=p.read_bytes();result.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest(),data=json.loads(b)))
 except Exception as e:result.append(dict(path=name,error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''
 p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=code.replace('PATHS',repr(paths)).encode(),capture_output=True,timeout=90)
 p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/'t02_calibration_actual_files.json').write_bytes(raw)
 bypath={r['path']:r for r in json.loads(raw)}
 formal=json.loads((OUT/'p26_configs.json').read_text(encoding='utf-8'))
 formal={r['config'].get('experiment',{}).get('trajectory_id',r['config'].get('sample_id')):r for r in formal if 'config' in r}
 keys=['gravity','dt','substeps','settle_steps','iterations','ls_iterations','noslip_iterations','constraint_timeconst','box_box_detection','use_gjk_collision','enable_multi_contact']
 results=[]
 for r in rows:
  f=formal[r['sample_id']]['config'];checks=[]
  for branch,t in r['calibrated_triplet'].items():
   c=bypath[t['config']];a=bypath[t['audit']]
   if 'data' not in c or 'data' not in a:checks.append(dict(branch=branch,status='missing'));continue
   cs=c['data'].get('scene_overrides',{});fs=f.get('scene_overrides',{})
   differences={k:[cs.get(k),fs.get(k)] for k in keys if cs.get(k)!=fs.get(k)}
   checks.append(dict(branch=branch,config_hash_matches=c['sha256'].lower()==t['config_sha256'].lower(),solver_differences=differences,
    calibration_audit=a['data'].get('status'),audit_sha256=a['sha256'],calibration_render=c['data'].get('render',{}).get('frames'),formal_render=f.get('render',{}).get('frames')))
  results.append(dict(sample_id=r['sample_id'],family=r['family'],checks=checks,
   profile_match=all(c.get('config_hash_matches') and not c.get('solver_differences') and c.get('status')!='missing' for c in checks)))
 (OUT/'t02_solver_profile_comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps(dict(files=len(bypath),read=sum('data' in r for r in bypath.values()),samples=len(results),profiles_match=sum(r['profile_match'] for r in results))))
if __name__=='__main__':main()
