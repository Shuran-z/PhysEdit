import base64,concurrent.futures,hashlib,json,subprocess,urllib.request
from pathlib import Path
from scripts.collect_sidecars_via_local_transport import REMOTE
OUT=Path('review/scene_family_completion_20261018/near375_visual');RAW=OUT/'t02_videos';RAW.mkdir(exist_ok=True)
def fetch(x):
 r=x['row'];p=RAW/(r['sample_id']+'.mp4')
 try:
  if x.get('error'):return {**r,'error':x['error']}
  if x.get('inline') is not None:b=base64.b64decode(x['inline'])
  else:
   op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
   with op.open(x['url'],timeout=30) as response:b=response.read()
  assert hashlib.sha256(b).hexdigest()==r['sha256'];p.write_bytes(b)
  return {**r,'local_path':str(p.resolve())}
 except Exception as e:return {**r,'error':type(e).__name__}
def main():
 candidates=json.loads((OUT/'frozen_candidates.json').read_text());inventory={r['sample_id']:r for r in [json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]}
 rows=[]
 for index,c in enumerate(candidates):
  if c['engine']!='genesis':continue
  r=inventory[c['sample_id']];v=r['videos']['cam01']
  rows.append(dict(index=index,sample_id=c['sample_id'],repo_id=r['repo_id'],revision=r['revision'],sidecar=v['path'],sha256=v['sha256'],event_frame=c.get('reference_event_frame')))
 result=[]
 for start in range(0,len(rows),5):
  batch=rows[start:start+5];code=REMOTE.replace('ROWS',repr(batch));port=47000+start
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-R',f'127.0.0.1:{port}:127.0.0.1:7897','p25',f'HTTPS_PROXY=http://127.0.0.1:{port} /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=60);p.check_returncode()
  with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:result+=list(pool.map(fetch,json.loads(p.stdout)))
 (OUT/'t02_video_receipts.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'found':sum('local_path' in r for r in result),'total':len(result)}))
if __name__=='__main__':main()
