"""Use server authorization for exact-revision URLs; fetch bytes through local proxy.
Signed URLs remain in process memory and are never persisted or printed.
"""
import base64,concurrent.futures,gzip,hashlib,json,subprocess,urllib.request
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
REMOTE='''
import base64,concurrent.futures,requests,json
from huggingface_hub import get_token,hf_hub_url
token=get_token()
def locate(row):
 try:
  r=requests.get(hf_hub_url(row['repo_id'],row['sidecar'],repo_type='dataset',revision=row['revision']),headers={'Authorization':'Bearer '+token},allow_redirects=False,timeout=(6,12))
  r.raise_for_status()
  return dict(row=row,url=r.headers.get('Location'),inline=base64.b64encode(r.content).decode() if r.status_code==200 else None)
 except Exception as e:return dict(row=row,error=type(e).__name__)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:print(json.dumps(list(p.map(locate,ROWS))))
'''
def fetch(x):
 row=x['row']
 try:
  if x.get('error'):return {**row,'error':x['error']}
  if x.get('inline') is not None:b=base64.b64decode(x['inline'])
  else:
   op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
   with op.open(x['url'],timeout=25) as response:b=response.read()
  c=json.loads(gzip.decompress(b) if row['sidecar'].endswith('.gz') else b)
  kind='original_config'
  if row['sidecar'].endswith('.gz'):
   kind='published_metadata_projection'
   c={k:v for k,v in c.items() if k in ['experiment','manifest','scene_overrides','dynamic_objects','runtime_forces','render','time_diagnostic']}
   c['dynamic_objects']=[o.get('spec',o) for o in c.get('dynamic_objects',[])]
  return {**row,'sha256':hashlib.sha256(b).hexdigest(),'config':c,'path':row['sidecar'],'evidence_kind':kind}
 except Exception as e:return {**row,'error':type(e).__name__}
def main():
 rows=json.loads((OUT/'remaining_sidecar_download_plan.json').read_text())
 rows.sort(key=lambda r:(r['scene_id'],r['sample_id']))
 for i in range(0,len(rows),4):
  dest=OUT/f'recovered_sidecar_local_{i//4:03}.json'
  if dest.exists() and all('config' in r for r in json.loads(dest.read_text())):continue
  port=40100+i//4
  code=REMOTE.replace('ROWS',repr(rows[i:i+4]))
  try:
   p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes','-R',f'127.0.0.1:{port}:127.0.0.1:7897','p25',f'HTTPS_PROXY=http://127.0.0.1:{port} /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=code.encode(),capture_output=True,timeout=45)
   p.check_returncode();links=json.loads(p.stdout)
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(fetch,links))
  except Exception as e:
   print(json.dumps(dict(batch=i//4,error=type(e).__name__)),flush=True);continue
  dest.write_text(json.dumps(result),encoding='utf-8')
  print(json.dumps(dict(batch=i//4,scene=rows[i]['scene_id'],found=sum('config' in r for r in result),total=len(result))),flush=True)
if __name__=='__main__':main()
