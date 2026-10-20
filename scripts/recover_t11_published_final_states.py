"""Read checksum-matched released T11 states on their source hosts.

Uses the original T11 analyzer's final-center-z < -0.20 m fall definition.
This is simulation event extraction, independent of visual quality admission.
"""
import json
import subprocess
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import concurrent.futures,gzip,hashlib,json,pathlib
rows=INPUT
cache=pathlib.Path('/tmp/physedit_t11_final_state_receipts_20261019');cache.mkdir(exist_ok=True)
names=('t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case')
def read(r):
 try:
  f=next(f for f in r['files'] if '/annotations/cam01.json.gz' in f['archive_path'])
  receipt=cache/(r['sample_id']+'.json')
  if receipt.exists():
   old=json.loads(receipt.read_text(encoding='utf-8'))
   if old['state_sha256']==f['sha256']:return old
  raw=pathlib.Path(f['source']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('published annotation SHA256 mismatch')
  d=json.loads(gzip.decompress(raw));frames=d['frames']
  final={o['name']:o['position'] for o in frames[-1]['objects'] if o['name'] in names}
  if set(final)!=set(names):raise ValueError('missing final target position')
  c=next(f for f in r['files'] if '/configs/cam01.json' in f['archive_path'])
  rawc=pathlib.Path(c['source']).read_bytes()
  if hashlib.sha256(rawc).hexdigest()!=c['sha256']:raise ValueError('published config SHA256 mismatch')
  config=json.loads(rawc)
  slab=next(o for o in config['dynamic_objects'] if o['name']=='t11_tabletop_collision_slab')
  top=slab['pose']['position'][2]+slab['size'][2]/2
  if abs(top)>1e-6:raise ValueError('original fall criterion requires zero-height tabletop')
  out=dict(sample_id=r['sample_id'],state_sha256=f['sha256'],source_state=f['source'],frame_count=len(frames),
   config_sha256=c['sha256'],final_positions=final,fallen={n:int(final[n][2]<-.20) for n in names},
   original_target_definition='fallen iff final center z < -0.20 m; original r009 analyzer',tabletop_height_m=top)
  receipt.write_text(json.dumps(out));return out
 except Exception as e:return dict(sample_id=r['sample_id'],error=str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(read,rows))
print(json.dumps(result))
'''


def main():
    selected=json.loads((ROOT/'t11_latest_selection_20261019.json').read_text(encoding='utf-8'))
    records=[]
    for host in ['p25','p29']:
        rows=[r for r in selected if r['source_host']==host]
        code=REMOTE.replace('INPUT',repr(rows))
        p=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=1200)
        p.check_returncode();data=json.loads(p.stdout);records.extend(data)
        (ROOT/('t11_'+host+'_published_final_states.json')).write_text(json.dumps(data),encoding='utf-8')
        print(json.dumps(dict(host=host,records=len(data),failed=sum('error' in r for r in data))),flush=True)
    (ROOT/'t11_published_final_states.json').write_text(json.dumps(records),encoding='utf-8')
    print(json.dumps(dict(total=len(records),failed=sum('error' in r for r in records))))


if __name__=='__main__':main()
