"""Recover T13 configs/states from archives authenticated by the live HF manifest."""
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,hashlib,tarfile
root=pathlib.Path('/data_cached/wangzijun_p25/t13_genesis_release_20261018')
for shard in SHARDS:
 path=root/shard['archive'];h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
 if h.hexdigest()!=shard['archive_sha256']:raise ValueError('published archive hash mismatch')
 with tarfile.open(path,'r|gz') as archive:
  for member in archive:
   if not member.isfile() or not member.name.endswith('.json'):continue
   if '/configs/' not in member.name and '/annotations/' not in member.name:continue
   raw=archive.extractfile(member).read();d=json.loads(raw)
   record=dict(archive=shard['archive'],archive_sha256=h.hexdigest(),path=member.name,sha256=hashlib.sha256(raw).hexdigest())
   if '/configs/' in member.name:record['config']=d
   else:
    record.update(experiment=d.get('experiment'),frame_count=len(d.get('frames',[])),scene_overrides=d.get('scene_overrides'),objects=d.get('dynamic_objects'),
      tracks={name:[dict(frame=f.get('frame_index',i),position=o['position'],quaternion_xyzw=o.get('quaternion_xyzw'),linear_velocity=o.get('linear_velocity')) for i,f in enumerate(d['frames']) for o in f['objects'] if o['name']==name] for name in [o['name'] for o in d['frames'][0]['objects'] if 'book' in o['name'] or 'drink' in o['name']]},
      frames_sha256=hashlib.sha256(json.dumps(d['frames'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
   print(json.dumps(record),flush=True)
'''

def main():
    sources=json.loads((ROOT/'new_release_manifests_20261019.json').read_text(encoding='utf-8'))[0]
    manifest=json.loads(next(f['text'] for f in sources['files'] if f['path']=='data/T13/genesis_720p_880_20261018/release_manifest.json'))
    code=REMOTE.replace('SHARDS',repr(manifest['shards']))
    output=ROOT/'t13_latest_archive_records_20261019.jsonl'
    with output.with_suffix('.partial').open('wb') as stream:
        p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','python3 -'],input=code.encode(),stdout=stream,stderr=subprocess.PIPE,timeout=300)
    if p.returncode:raise RuntimeError('archive recovery failed: '+p.stderr.decode(errors='replace')[-400:])
    output.with_suffix('.partial').replace(output)
    rows=[json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()]
    print(json.dumps(dict(revision=sources['revision'],records=len(rows),configs=sum('config' in r for r in rows),states=sum('tracks' in r for r in rows),archives=len(manifest['shards']))))

if __name__=='__main__':main()
