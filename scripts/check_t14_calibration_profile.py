"""Compare actual calibration and formal solver settings before accepting distances."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
records=json.loads(Path('review/original_search_tasks_20261018/p26_records.json').read_text(encoding='utf-8'))
paths=set()
for r in records:
 if 'T14' not in r['path'] or '/manifests/' not in r['path'] or 'dryrun' not in r['path'] or not r['path'].endswith('matrix.json'):continue
 for row in json.loads(r['text'])['rows']:
  if row.get('cam01_config'):paths.add(row['cam01_config'])
code=r'''
import json,pathlib,hashlib,gzip,base64
rows=[]
for name in PATHS:
 p=pathlib.Path(name)
 if not p.exists():p=pathlib.Path(name.replace('/home/wangzijun_p25/','/data2/wangzijun_p25/'))
 try:
  b=p.read_bytes();c=json.loads(b);rows.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),config=c))
 except Exception as e:rows.append(dict(path=str(p),error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=code.replace('PATHS',repr(sorted(paths))).encode(),capture_output=True,timeout=90)
p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/'t14_calibration_configs.json').write_bytes(raw)
rows=json.loads(raw);keys=['dt','substeps','iterations','ls_iterations','constraint_timeconst','box_box_detection','settle_steps']
profiles={json.dumps({k:r['config'].get('scene_overrides',{}).get(k) for k in keys},sort_keys=True) for r in rows if 'config' in r}
print(json.dumps(dict(found=sum('config' in r for r in rows),errors=sum('error' in r for r in rows),profiles=[json.loads(p) for p in profiles])))
formal=json.loads(Path('review/original_search_tasks_20261018/t14_source_identity.json').read_text(encoding='utf-8'))
comparison=[]
for r in formal:
 profile={k:r['scene_overrides'].get(k) for k in keys}
 comparison.append(dict(sample_id=r['sample_id'],formal_profile=profile,
  matches_any_collected_calibration_profile=json.dumps(profile,sort_keys=True) in profiles,
  status='solver_profile_matches' if json.dumps(profile,sort_keys=True) in profiles else 'solver_profile_mismatch_requires_same_profile_search_or_validation'))
(OUT/'t14_solver_profile_comparison.json').write_text(json.dumps(dict(calibration_profiles=[json.loads(p) for p in profiles],rows=comparison),indent=2),encoding='utf-8')
