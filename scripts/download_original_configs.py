"""Export verified original configs from the downloaded metadata package."""
import argparse,gzip,hashlib,json
from pathlib import Path
import zipfile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video-id',action='append',default=[])
    p.add_argument('--scene')
    p.add_argument('--all',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not (a.video_id or a.scene or a.all):p.error('Choose --video-id, --scene, or --all')
    root=Path(__file__).resolve().parents[1]
    with gzip.open(root/'catalog/config_bindings.jsonl.gz','rt',encoding='utf8') as f:
        selected=[r for r in map(json.loads,f) if (not a.video_id or r['canonical_video_id'] in a.video_id) and (not a.scene or r['scene']==a.scene)]
    if a.video_id and {r['canonical_video_id'] for r in selected}!=set(a.video_id):raise SystemExit('Unknown or filtered video ID')
    if not selected:raise SystemExit('No matching videos')
    missing=[r['canonical_video_id'] for r in selected if r['status']!='VERIFIED']
    # Do not export a partially satisfied requested selection as success.
    if missing:raise SystemExit('Original config unresolved for '+str(len(missing))+' requested videos: '+', '.join(missing[:10]))
    count=0
    with zipfile.ZipFile(root/'provenance/configs.zip') as z:
        for r in selected:
            cid=r['canonical_video_id'];scene=r['scene']
            if Path(cid).name!=cid or scene not in ['T'+str(i).zfill(2) for i in range(1,21)]:raise ValueError('Unsafe config identity')
            raw=z.read(r['archive_member'])
            if hashlib.sha256(raw).hexdigest()!=r['config_sha256']:raise ValueError('Config hash mismatch: '+cid)
            target=a.output/'configs'/scene/(cid+'.json');target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=raw:raise ValueError('Existing config differs: '+str(target))
            if not target.exists():target.write_bytes(raw)
            count+=1
    print(json.dumps({'exported_configs':count,'output':str(a.output/'configs'),'original_bytes_sha256_verified':True}))

if __name__=='__main__':main()
