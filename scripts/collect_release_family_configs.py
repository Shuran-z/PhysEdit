"""Collect original camera configs for frozen inventory IDs, retaining candidates."""
import base64,gzip,json,subprocess,concurrent.futures
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
ROOTS={'p25':'/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','p26':'/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'}
REMOTE=r'''
import pathlib,os,json,hashlib,gzip,base64
root=pathlib.Path(ROOT);wanted=set(WANTED);paths=set(PATHS)
for base in [root/'configs']+[p/'configs' for p in root.glob('everyday_bifurcation*')]:
 if not base.exists():continue
 for directory,dirs,files in os.walk(base):
  d=pathlib.Path(directory);depth=len(d.relative_to(base).parts)
  if depth>=3:dirs[:]=[]
  if d.name in wanted:
   for name in ['cam01.json','trajectory.json']:
    if name in files:paths.add(str(d/name))
   dirs[:]=[]
  for name in files:
   if name.endswith('.json') and (name[:-5] in wanted or name.split('__cam01')[0] in wanted):paths.add(str(d/name))
rows=[]
for name in sorted(paths):
 try:
  p=pathlib.Path(name)
  if p.stat().st_size>200000:continue
  b=p.read_bytes();c=json.loads(b);sid=c.get('sample_id') or c.get('experiment',{}).get('trajectory_id') or p.parent.name
  rows.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest(),sample_id=sid,config=c))
 except Exception as e:rows.append(dict(path=name,error=str(e)))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
def main():
 OUT.mkdir(exist_ok=True)
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 wanted=[r['sample_id'] for r in inventory if r['engine']=='genesis']
 links=[json.loads(l) for l in Path('review/original_search_tasks_20261018/inventory_task_links.jsonl').read_text(encoding='utf-8').splitlines()]
 def run(host):
  paths=set()
  for r in links:
   for c in r['original_task_candidates']:
    if c['host']==host and c['original_row'].get('cam01_config'):paths.add(c['original_row']['cam01_config'])
  code=REMOTE.replace('ROOT',repr(ROOTS[host])).replace('WANTED',repr(wanted)).replace('PATHS',repr(sorted(paths)))
  p=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=300)
  p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));rows=json.loads(raw)
  (OUT/f'{host}_configs.json').write_bytes(raw)
  return dict(host=host,configs=sum('config' in r for r in rows),errors=sum('error' in r for r in rows))
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(run,ROOTS))
 (OUT/'receipt.json').write_text(json.dumps(receipts,indent=2));print(json.dumps(receipts))
if __name__=='__main__':main()
