"""Collect original task contracts and reports, without inventing family mappings."""
import concurrent.futures
import hashlib
import gzip
import base64
import json
from pathlib import Path
import subprocess

OUT = Path('review/original_search_tasks_20261018')
ROOTS = {'p25': '/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer',
         'p26': '/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'}
REMOTE = r'''
import pathlib,json,hashlib,re,os,gzip,base64
root=pathlib.Path(ROOT)
paths=set(pathlib.Path(x) for x in KNOWN)
for p in (root/'scripts').glob('*.py'):
 if re.search(r't\d\d',p.name,re.I):paths.add(p)
for project in root.glob('everyday_bifurcation*'):
 paths.update((project/'scripts').glob('*.py'))
 for name in ['PROJECT_MEMORY.md','README.md']:
  if (project/name).is_file():paths.add(project/name)
 for folder in ['manifests']:
  base=project/folder
  if not base.exists():continue
  candidates=[]
  for directory,dirs,files in os.walk(base):
   if len(pathlib.Path(directory).relative_to(base).parts)>=2:dirs[:]=[]
   candidates.extend(pathlib.Path(directory)/f for f in files if f.endswith('.json'))
  for p in candidates:
   # Search contracts/results, not every rendering config or state frame.
   if re.search(r'(boundary|search_plan|search_result|threshold|registry|selected|calibration_result|contract|parameter_design)',p.name,re.I) or (folder=='manifests' and (p.name=='matrix.json' or p.parent==base)) or p.name=='manifest.json':paths.add(p)
result=[]
for p in sorted(paths):
 try:
  if p.stat().st_size>8000000:
   result.append(dict(path=str(p),status='oversize',bytes=p.stat().st_size));continue
  b=p.read_bytes();result.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),text=b.decode()))
 except Exception as e:result.append(dict(path=str(p),error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''

def collect(host):
    sources=json.loads(Path(f'review/all_scene_boundary_audit_20261018/{host}_sources.json').read_text())
    known=[r['path'] for r in sources]
    code=REMOTE.replace('ROOT',repr(ROOTS[host])).replace('KNOWN',repr(known))
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'python3 -'],input=code.encode(),capture_output=True,timeout=300)
    (OUT/f'{host}_stderr.txt').write_bytes(p.stderr)
    p.check_returncode()
    raw=gzip.decompress(base64.b64decode(p.stdout))
    rows=json.loads(raw)
    (OUT/f'{host}_records.json').write_bytes(raw)
    return {'host':host,'records':len(rows),'readable':sum('text' in r for r in rows),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    OUT.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        receipts=list(pool.map(collect,ROOTS))
    (OUT/'receipt.json').write_text(json.dumps(receipts,indent=2))
    print(json.dumps(receipts))

if __name__=='__main__':main()
