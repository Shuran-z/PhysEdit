"""Read bounded original report trees, retaining failures and file provenance."""
import base64,gzip,json,subprocess,concurrent.futures
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
ROOTS={'p25':'/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','p26':'/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'}
REMOTE=r'''
import pathlib,os,json,hashlib,gzip,base64,re
root=pathlib.Path(ROOT);result=[]
for project in root.glob('everyday_bifurcation*'):
 for folder in ['reports','logs']:
  base=project/folder
  if not base.exists():continue
  for directory,dirs,files in os.walk(base):
   d=pathlib.Path(directory)
   if len(d.relative_to(base).parts)>=3:dirs[:]=[]
   for name in files:
    p=d/name
    if p.suffix not in ['.json','.jsonl','.md']:continue
    if not re.search(r'calibrat|critical|boundary|search|probe|pilot|contract|release|fine|refin|sweep',str(p.relative_to(project)),re.I):continue
    try:
     if p.stat().st_size>2500000:result.append(dict(path=str(p),status='oversize'));continue
     b=p.read_bytes();result.append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),text=b.decode()))
    except Exception as e:result.append(dict(path=str(p),error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''
def fetch(host):
 p=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=REMOTE.replace('ROOT',repr(ROOTS[host])).encode(),capture_output=True,timeout=240)
 p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/f'{host}_extra_reports.json').write_bytes(raw)
 return dict(host=host,files=len(json.loads(raw)))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:print(list(pool.map(fetch,ROOTS)))
