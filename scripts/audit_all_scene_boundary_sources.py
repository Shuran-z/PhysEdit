"""Read-only report/source discovery on dataset hosts, with retained evidence."""
import concurrent.futures
import json
from pathlib import Path
import subprocess

REMOTE=r'''
import pathlib,json,re,hashlib
root=pathlib.Path(ROOT)
result=[]
pattern=re.compile(r'critical|threshold|theta_star|bracket|transition|boundary',re.I)
for project in sorted(root.glob('everyday_bifurcation*')):
 for sub in ['reports','scripts']:
  folder=project/sub
  if not folder.exists():continue
  for p in sorted(folder.glob('**/*')):
   if not p.is_file() or p.suffix not in ('.json','.py','.md'):continue
   rel=p.relative_to(folder)
   if len(rel.parts)>2 or p.stat().st_size>3000000:continue
   if sub=='reports' and not re.search(r'calibr|bound|critical|threshold|formal|summary|result|select',str(rel),re.I):continue
   try:text=p.read_text()
   except Exception:continue
   lines=text.splitlines();hits=[]
   for i,line in enumerate(lines):
    if pattern.search(line):hits.append({'line':i+1,'text':line[:800]})
   if not hits:continue
   result.append(dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),hits=hits[:50],total_hits=len(hits)))
print(json.dumps(result))
'''

def main():
 out=Path('review/all_scene_boundary_audit_20261018')
 roots={'p25':'/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer',
        'p26':'/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'}
 def collect(item):
  host,root=item;code=REMOTE.replace('ROOT',repr(root))
  r=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=240)
  (out/(host+'_sources.json')).write_bytes(r.stdout)
  (out/(host+'_stderr.txt')).write_bytes(r.stderr)
  return dict(host=host,root=root,returncode=r.returncode)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(collect,roots.items()))
 (out/'discovery_receipt.json').write_text(json.dumps(r,indent=2))
 print(r)

if __name__=='__main__':main()
