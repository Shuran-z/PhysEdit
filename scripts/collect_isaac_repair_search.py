"""Recover original repair search manifests and frozen calibration records, read-only."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
code=r'''
import pathlib,json,hashlib,base64,gzip
root=pathlib.Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/repair_t16_t19_20260923')
paths=list(root.glob('release_T*.json'))+[root/'REPAIR_STATUS.md',root/'search.py',root/'calibrate.py',root/'design.py',root/'contract.py']
releases=[]
for p in root.glob('release_T*.json'):
 d=json.loads(p.read_text());releases.append(d)
 for value in d.values():
  if isinstance(value,str) and value.startswith('/'):
   q=pathlib.Path(value)
   if q.is_dir():
    paths+=list(q.glob('*.json'))
    for folder in ['calibration','reports','searches']:
     if (q/folder).exists():paths+=list((q/folder).rglob('*.json'))
result=[]
for p in sorted(set(paths)):
 try:
  if p.stat().st_size>15000000:continue
  b=p.read_bytes();result.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),text=b.decode()))
 except Exception as e:result.append(dict(path=str(p),error=type(e).__name__))
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=code.encode(),capture_output=True,timeout=90);p.check_returncode()
r=gzip.decompress(base64.b64decode(p.stdout));(OUT/'isaac_repair_search_records.json').write_bytes(r)
a=json.loads(r);print('records',len(a))
for x in a:
 if 'release_T' in x['path']:print(x['path'],x.get('text','')[:1200])
