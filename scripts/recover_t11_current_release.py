"""Recover exact current T11 configs and quality records using published hashes."""
import concurrent.futures
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import concurrent.futures,hashlib,json,pathlib
def read(row):
 result=dict(sample_id=row['sample_id'],source_host=row['source_host'],files=[])
 for f in row['files']:
  if not (f['archive_path'].endswith('/configs/cam01.json') or f['archive_path'].endswith('/quality_record.json')):continue
  try:
   raw=pathlib.Path(f['source']).read_bytes();actual=hashlib.sha256(raw).hexdigest()
   if actual!=f['sha256']:raise ValueError('published hash mismatch')
   result['files'].append(dict(path=f['source'],archive_path=f['archive_path'],sha256=actual,data=json.loads(raw)))
  except Exception as e:result['files'].append(dict(path=f['source'],error=type(e).__name__))
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(read,ROWS):print(json.dumps(r),flush=True)
'''

def main():
    rows=json.loads((ROOT/'t11_latest_selection_20261019.json').read_text(encoding='utf-8'))
    def fetch(host):
        selected=[r for r in rows if r['source_host']==host]
        code=REMOTE.replace('ROWS',repr(selected))
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',host,'python3 -'],input=code.encode(),capture_output=True,timeout=240)
        if result.returncode:raise RuntimeError('T11 source recovery failed on '+host)
        data=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        (ROOT/('t11_latest_'+host+'_evidence_20261019.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(json.dumps(dict(host=host,rows=len(data),verified_files=sum('data' in f for r in data for f in r['files']),failed_files=sum('error' in f for r in data for f in r['files']))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,sorted(set(r['source_host'] for r in rows))))

if __name__=='__main__':main()
