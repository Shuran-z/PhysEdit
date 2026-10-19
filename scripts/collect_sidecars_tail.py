"""Recover tail batches concurrently with the existing head recovery, with shared receipts."""
import concurrent.futures,json,subprocess
from scripts.collect_sidecars_via_local_transport import OUT,REMOTE,fetch
rows=json.loads((OUT/'remaining_sidecar_download_plan.json').read_text());rows.sort(key=lambda r:(r['scene_id'],r['sample_id']))
for i in range(500,len(rows),16):
 block=[]
 for j in range(i,min(i+16,len(rows)),4):
  dest=OUT/f'recovered_sidecar_local_{j//4:03}.json'
  if not dest.exists():block.extend(rows[j:j+4])
 if not block:continue
 port=43000+i//16
 code=REMOTE.replace('ROWS',repr(block))
 try:
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes','-R',f'127.0.0.1:{port}:127.0.0.1:7897','p25',f'HTTPS_PROXY=http://127.0.0.1:{port} /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=65);p.check_returncode()
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(fetch,json.loads(p.stdout)))
  byid={r['sample_id']:r for r in result}
  for j in range(i,min(i+16,len(rows)),4):
   dest=OUT/f'recovered_sidecar_local_{j//4:03}.json'
   part=[byid[r['sample_id']] for r in rows[j:j+4] if r['sample_id'] in byid]
   if part and not dest.exists():dest.write_text(json.dumps(part),encoding='utf-8')
  print(json.dumps(dict(start=i,found=sum('config' in r for r in result),attempted=len(result))),flush=True)
 except Exception as e:print(json.dumps(dict(start=i,error=type(e).__name__)),flush=True)
