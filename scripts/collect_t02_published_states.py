"""Recover exact published T02 state sidecars, retaining bytes for original event extraction."""
import argparse,concurrent.futures,gzip,hashlib,json,subprocess,urllib.request,base64
from pathlib import Path
from scripts.collect_sidecars_via_local_transport import REMOTE
OUT=Path('review/scene_family_completion_20261018');RAW=OUT/'t02_published_states';RAW.mkdir(exist_ok=True)
def fetch(x):
 r=x['row'];dest=RAW/(r['sample_id']+'.json.gz')
 try:
  if x.get('error'):return {**r,'error':x['error']}
  if x.get('inline') is not None:b=base64.b64decode(x['inline'])
  else:
   op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
   with op.open(x['url'],timeout=25) as response:b=response.read()
  d=json.loads(gzip.decompress(b));assert len(d.get('frames',[]))==210
  temp=dest.with_suffix('.tmp');temp.write_bytes(b);temp.replace(dest)
  return {**r,'path':str(dest.resolve()),'sha256':hashlib.sha256(b).hexdigest(),'frame_count':210}
 except Exception as e:return {**r,'error':type(e).__name__}
def main():
 args=argparse.ArgumentParser();args.add_argument('--start',type=int,default=0);args.add_argument('--stop',type=int,default=880);args=args.parse_args()
 if args.start%8 or args.stop%8:raise ValueError('start and stop must align with eight-record receipts')
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 rows=[]
 for r in inventory:
  if r['event_id']=='T02' and r['engine']=='genesis':rows.append(dict(sample_id=r['sample_id'],repo_id=r['repo_id'],revision=r['revision'],sidecar=next(p for p in r['sidecar_paths'] if 'cam01' in p)))
 rows.sort(key=lambda r:r['sample_id'])
 for i in range(args.start,min(args.stop,len(rows)),8):
  dest=OUT/f't02_state_receipt_{i//8:03}.json'
  if dest.exists() and all('path' in r for r in json.loads(dest.read_text())):continue
  port=45000+i//8
  try:
   code=REMOTE.replace('ROWS',repr(rows[i:i+8]))
   p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes','-R',f'127.0.0.1:{port}:127.0.0.1:7897','p25',f'HTTPS_PROXY=http://127.0.0.1:{port} /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=50);p.check_returncode()
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(fetch,json.loads(p.stdout)))
   dest.write_text(json.dumps(result),encoding='utf-8');print(json.dumps(dict(batch=i//8,found=sum('path' in r for r in result))),flush=True)
  except Exception as e:print(json.dumps(dict(batch=i//8,error=type(e).__name__)),flush=True)
if __name__=='__main__':main()
