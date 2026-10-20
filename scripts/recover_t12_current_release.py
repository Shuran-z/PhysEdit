"""Recover R005 config/state bytes using immutable Hugging Face Git/LFS IDs."""
import gzip
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')
REMOTE=r'''
import pathlib,json,hashlib,tarfile,gzip,sys
expected={e['path']:e for e in ENTRIES}
archive=pathlib.Path('/home/wangzijun_p25/t12_dualsim_v3_20261011/genesis_r005_full880_20261017.tar.gz')
seen=set()
with gzip.GzipFile(fileobj=sys.stdout.buffer,mode='wb') as output:
 with tarfile.open(archive,'r|gz') as tar:
  for member in tar:
   if not member.isfile() or member.name not in expected:continue
   e=expected[member.name];raw=tar.extractfile(member).read()
   if len(raw)!=e['size']:raise ValueError('published byte size mismatch')
   actual=hashlib.sha256(raw).hexdigest()
   if e.get('lfs_sha256'):
    if actual!=e['lfs_sha256']:raise ValueError('published LFS hash mismatch')
   elif hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=e['blob_id']:raise ValueError('published Git blob mismatch')
   if member.name in seen:raise ValueError('duplicate archive entry')
   seen.add(member.name)
   output.write((json.dumps(dict(path=member.name,sha256=actual,blob_id=e['blob_id'],data=json.loads(raw)))+'\n').encode())
 if len(seen)!=len(expected):raise ValueError('missing published config/state archive members')
'''

def main():
    identity=json.loads((ROOT/'t12_r005_file_identities_20261019.json').read_text(encoding='utf-8'))[0]
    entries=[e for d in identity['directories'] if d['path'].endswith(('/configs','/metadata_shared','/state/success')) for e in d['entries']]
    if len(entries)!=2640:raise ValueError('expected 880 configs, shared states and success records')
    path=ROOT/'t12_latest_verified_records_20261019.jsonl.gz';temp=path.with_suffix('.partial')
    with temp.open('wb') as stream:
        p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p26','python3 -'],input=REMOTE.replace('ENTRIES',repr(entries)).encode(),stdout=stream,stderr=subprocess.PIPE,timeout=600)
    if p.returncode:raise RuntimeError('T12 exact release recovery failed: '+p.stderr.decode(errors='replace')[-500:])
    count=0
    with gzip.open(temp,'rt',encoding='utf-8') as stream:
        for line in stream:json.loads(line);count+=1
    if count!=2640:raise ValueError('incomplete T12 recovery')
    temp.replace(path);print(json.dumps(dict(revision=identity['revision'],records=count,configs=880,states=880,success_records=880,verified_against='immutable HF Git blob or LFS SHA256')))

if __name__=='__main__':main()
