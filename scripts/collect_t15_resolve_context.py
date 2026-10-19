"""Verify supplemental scans against the same physical contract as frozen answers."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
base=Path('scripts/t15_boundary_reference_pilot.py').read_text(encoding='utf-8').split("if __name__")[0]
tail=r'''
import gzip,base64
rows=[]
for family in ['cfA','cfB','cfC']:
 stage='extended' if family=='cfA' else 'refined'
 root=Path('/data_cached/wangzijun_p25/liyuhan/critical_family_resolve_20261018_'+stage)
 for r in json.loads((root/family/'manifest.json').read_text()):
  cp=Path(r['config']);sp=Path(r['output'])/'metadata/physics.json'
  c=json.loads(cp.read_text());s=json.loads(sp.read_text())
  raw=int(any(o['position'][2]<-.15 for f in s['frames'] for o in f['objects'] if o['name']==LAPTOP))
  rows.append(dict(family=family,stage=stage,sample_id=r['sample_id'],theta=r['theta'],config_path=str(cp),state_path=str(sp),config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(sp.read_bytes()).hexdigest(),speed_context_hash=sha(physical_contract(c,s,True)),raw_fall=raw))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=(base+tail).encode(),capture_output=True,timeout=90)
p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/'t15_resolve_context.json').write_bytes(raw)
print('verified supplemental state contexts:',len(json.loads(raw)))
