"""Materialize selected, exact-hash source videos under the canonical catalog names."""
import argparse
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import uuid


def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def install(stream,row,root):
    relative=PurePosixPath(row['canonical_path'])
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe output path')
    target=(root/Path(*relative.parts)).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError('Output escapes target directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if sha_file(target)!=row['sha256']:raise ValueError('Existing output has a different hash: '+str(target))
    else:
        temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
        try:
            with temp.open('xb') as f:shutil.copyfileobj(stream,f,1024*1024)
            if sha_file(temp)!=row['sha256']:raise ValueError('Source video SHA-256 mismatch: '+row['video_id'])
            if target.exists():
                if sha_file(target)!=row['sha256']:raise ValueError('Concurrent output differs')
                temp.unlink()
            else:temp.rename(target)
        finally:
            if temp.exists():temp.unlink()
    meta=target.parent.parent/'metadata'/(row['canonical_video_id']+'.json')
    raw=json.dumps(row,ensure_ascii=False,indent=2).encode()
    meta.parent.mkdir(exist_ok=True)
    if meta.exists() and meta.read_bytes()!=raw:raise ValueError('Existing metadata differs: '+str(meta))
    if not meta.exists():meta.write_bytes(raw)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scene',required=True,help='Quota scene T01..T20, or native T14S')
    p.add_argument('--engine',choices=['genesis','isaac'])
    p.add_argument('--admission',choices=['usable','nonretired','all'],default='usable')
    a=p.parse_args()
    if a.output.is_symlink():raise ValueError('Choose a real output directory')
    groups=collections.defaultdict(list)
    with gzip.open(a.manifest,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if (r['scene'] if a.scene=='T14S' else r['quota_scene'])!=a.scene:continue
            if a.engine and r['engine']!=a.engine:continue
            state=r['quality_admission_status']
            if a.admission=='usable' and not state.startswith('USABLE_'):continue
            if a.admission=='nonretired' and state.startswith('UNUSABLE_'):continue
            d=r['download'];assert d.get('revision'),'A fixed media revision is required'
            groups[d['repo_id'],d['revision'],d['path']].append(r)
    if not groups:
        raise SystemExit('No records match this scene, engine and admission filter. Check the scene index and quality states.')
    from huggingface_hub import hf_hub_download
    completed=0
    for (repo,revision,path),rows in groups.items():
        local=Path(hf_hub_download(repo_id=repo,repo_type='dataset',revision=revision,filename=path))
        if rows[0]['download'].get('member'):
            members={r['download']['member']:r for r in rows}
            assert len(members)==len(rows)
            with tarfile.open(local,'r|gz') as tar:
                for member in tar:
                    if member.name not in members:continue
                    if not member.isfile():raise ValueError('Video archive member is not a regular file')
                    with tar.extractfile(member) as stream:install(stream,members.pop(member.name),a.output)
                    completed+=1
            if members:raise ValueError('Selected source archive members are absent')
        else:
            for row in rows:
                with local.open('rb') as stream:install(stream,row,a.output)
                completed+=1
        print(json.dumps({'materialized_videos':completed}),flush=True)
    print(json.dumps({'completed':completed,'scene':a.scene,'admission':a.admission}))


if __name__=='__main__':main()
