"""Read archived runtime provenance, avoiding inference from current config file hashes."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
rows=json.loads(Path('review/original_search_tasks_20261018/t02_original_family_bindings.json').read_text(encoding='utf-8'))
paths=sorted({t['metadata'] for r in rows for t in r['calibrated_triplet'].values()})
code=r'''
import pathlib,json,hashlib,gzip,base64
rows=[]
for name in PATHS:
 try:
  p=pathlib.Path(name);b=p.read_bytes();d=json.loads(b)
  frames=d.pop('frames',[]);d['frame_count']=len(frames)
  rows.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest(),metadata=d))
 except Exception as e:rows.append(dict(path=name,error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=code.replace('PATHS',repr(paths)).encode(),capture_output=True,timeout=120)
p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/'t02_calibration_runtime_provenance.json').write_bytes(raw)
print(json.dumps(dict(total=len(paths),read=sum('metadata' in r for r in json.loads(raw)))))
