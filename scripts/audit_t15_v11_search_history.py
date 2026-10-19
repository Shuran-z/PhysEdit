"""Read-only targeted history audit; retains stdout, stderr and command receipts."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess

BASE='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'
PROJECT=BASE+'/everyday_bifurcation_T15_v4_edge_transfer'
CODE=r'''
import json,pathlib,hashlib
root=pathlib.Path(ROOT)
result=[]
for phase in ['search','moonsearch','extreme_search','scene_bounds_search','scene_bounds_search_fine','scene_bounds_search_x']:
 p=root/'configs/v11_20260914'/phase/'manifest.json'
 if not p.exists():continue
 rows=json.loads(p.read_text()); rows=rows if isinstance(rows,list) else rows.get('samples',rows.get('rows',[]))
 selected=[]
 for r in rows:
  cfg=pathlib.Path(r['config']);c=json.loads(cfg.read_text());m=c.get('sample_metadata',{})
  if m.get('background_id')=='bg01_home_ase' and m.get('gravity_id')=='g03_earth':
   selected.append(dict(sample_id=r.get('sample_id'),config=str(cfg),sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),metadata=m))
 result.append(dict(phase=phase,count=len(rows),manifest=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),earth_home=selected))
print(json.dumps(result))
'''.replace('ROOT',repr(PROJECT))

def main():
 out=Path('review/t15_multihost_search_20261018');out.mkdir(exist_ok=False)
 jobs=[('p25','v11_manifests', 'python3 -',CODE),
       ('p25','git_history',f"git -C {BASE} log --all --oneline -- '*t15*'; git -C {BASE} show --stat 20b27d4",None),
       ('p25','search_logs',f"tail -8 /data_cached/wangzijun_p25/liyuhan/ebb_new_outputs/t15/v11_20260914/search_gpu4.log; tail -8 /data_cached/wangzijun_p25/liyuhan/ebb_new_outputs/t15/v11_20260914/search_gpu5.log",None),
       ('p26','t15_inventory',"find /data2/wangzijun_p25/liyuhan/phydataset -maxdepth 4 -iname '*t15*' 2>/dev/null",None),
       ('p29','t15_inventory',"find /data1/liyuhan/isaac_render_worker/project -maxdepth 3 -iname '*t15*' 2>/dev/null",None),
       ('p28','t15_inventory',"find /mnt/data2 /mnt/model /mnt/sda1 /mnt/sdb1 -maxdepth 4 -iname '*t15*' 2>/dev/null",None)]
 def collect(job):
  host,name,command,stdin=job
  try:
   r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],input=stdin.encode() if stdin else None,capture_output=True,timeout=90)
   p=out/(host+'_'+name+'.txt');p.write_bytes(r.stdout)
   (out/(host+'_'+name+'.stderr.txt')).write_bytes(r.stderr)
   return dict(host=host,command=command,stdin=stdin,returncode=r.returncode,output=str(p),sha256=hashlib.sha256(r.stdout).hexdigest())
  except subprocess.TimeoutExpired:return dict(host=host,command=command,status='timeout')
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(collect,jobs))
 (out/'receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
 print(json.dumps([{k:v for k,v in r.items() if k in ('host','returncode','status')} for r in receipts]))

if __name__=='__main__':main()
