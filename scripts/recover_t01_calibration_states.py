"""Recover actual T01 calibration runtime contracts, beyond nominal star values."""
import concurrent.futures
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,gzip,hashlib,concurrent.futures
def read(row):
 try:
  p=pathlib.Path(row['metadata']);raw=p.read_bytes();d=json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
  return dict(**row,state_sha256=hashlib.sha256(raw).hexdigest(),contract={k:d.get(k) for k in ['experiment','manifest','render','scene_overrides','dynamic_objects','runtime_forces','room_boundary']},frame_count=len(d['frames']))
 except Exception as e:
  p=pathlib.Path(row['metadata']);project=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T01_v2_7s')
  cp=project/'configs'/p.parents[2].name/row['original_audit']['sample_id']/'cam01.json'
  if cp.exists():
   raw=cp.read_bytes();return dict(**row,state_error=type(e).__name__,config_path=str(cp),config_sha256=hashlib.sha256(raw).hexdigest(),original_config=json.loads(raw))
  return dict(**row,error=type(e).__name__)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 print(json.dumps(list(pool.map(read,ROWS))))
'''

def main():
    rows=[]
    for host in ['p25','p26']:
        sources=json.loads(Path(f'review/original_search_tasks_20261018/{host}_records.json').read_text(encoding='utf-8'))
        for r in sources:
            if 'T01_v2' not in r['path'] or '/reports/' not in r['path'] or not r['path'].endswith('.json') or 'text' not in r:continue
            try:data=json.loads(r['text'])
            except ValueError:continue
            if not isinstance(data,dict):continue
            source_rows=data.get('rows',[])
            if not source_rows and isinstance(data.get('result'),dict):source_rows=[data['result']]
            for row in source_rows:
                if isinstance(row,dict) and row.get('metadata'):
                    rows.append(dict(host=host,report=r['path'],report_sha256=r['sha256'],metadata=row['metadata'],original_audit=row))
    unique={(r['host'],r['metadata']):r for r in rows}
    def fetch(host):
        chosen=[r for r in unique.values() if r['host']==host]
        p=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=REMOTE.replace('ROWS',repr(chosen)).encode(),capture_output=True,timeout=180)
        p.check_returncode();result=json.loads(p.stdout)
        (ROOT/('t01_original_calibration_contracts_'+host+'_20261019.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(host=host,records=len(result),recovered_states=sum('contract' in r for r in result),recovered_configs=sum('original_config' in r for r in result))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,['p25','p26']))


if __name__=='__main__':main()
