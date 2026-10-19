"""Use the dataset host's existing Hugging Face login; never export credentials."""
import argparse,base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import json,hashlib,gzip,base64,pathlib,concurrent.futures
from huggingface_hub import hf_hub_download
def fetch(row):
 try:
  p=pathlib.Path(hf_hub_download(repo_id=row['repo_id'],repo_type='dataset',revision=row['revision'],filename=row['sidecar']))
  b=p.read_bytes();payload=gzip.decompress(b) if p.name.endswith('.gz') else b
  return {**row,'sha256':hashlib.sha256(b).hexdigest(),'config':json.loads(payload),'server_cache':str(p)}
 except Exception as e:return {**row,'error':type(e).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,ROWS))
print(base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode())
'''
parser=argparse.ArgumentParser();parser.add_argument('--input',default='published_config_probe.json');parser.add_argument('--output',default='authenticated_published_configs.json');args=parser.parse_args()
rows=json.loads((OUT/args.input).read_text(encoding='utf-8'))
rows=[{k:v for k,v in r.items() if k!='error'} for r in rows]
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-R','127.0.0.1:50991:127.0.0.1:7897','p25','timeout 90 env HTTPS_PROXY=http://127.0.0.1:50991 HF_HUB_ETAG_TIMEOUT=8 HF_HUB_DOWNLOAD_TIMEOUT=10 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],input=REMOTE.replace('ROWS',repr(rows)).encode(),capture_output=True,timeout=105)
p.check_returncode();raw=gzip.decompress(base64.b64decode(p.stdout));(OUT/args.output).write_bytes(raw)
print(json.dumps([{'sample_id':r['sample_id'],'status':'downloaded' if 'config' in r else r.get('error')} for r in json.loads(raw)]))
