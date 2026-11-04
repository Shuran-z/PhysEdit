"""Bounded filename/parent search of original project and archive/cache backups."""
import gzip,hashlib,json,os
from pathlib import Path
ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101')
jobs=json.loads((ROOT/'ORIGINAL_SOURCE_JOBS.json').read_text());by={j['sample_id']:j['clip_id']for j in jobs}
roots=[Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1'),
       Path('/data_cached/wangzijun_p25/hf_cache'),Path('/home/wangzijun_p25/.cache/huggingface/hub/datasets--phyeditingvideo--Phyediting'),
       Path('/data_cached/wangzijun_p25/hf_upload_staging'),Path('/data_cached/wangzijun_p25/hf_upload_staging_20260905'),
       Path('/data_cached/wangzijun_p25/hf_upload_staging_20260906'),Path('/data_cached/wangzijun_p25/hf_upload_staging_t09_20260907'),
       Path('/data_cached/wangzijun_p25/config_bindings_20261031'),Path('/data2/liyuhan/core100_reference_storage_backups_20261101')]
skip={'videos','previews','rgb','depth','seg','assets','.git','__pycache__','node_modules','blobs','models'}
out=[];searched=[];seen=set();skipped=[]
for root in roots:
    if not root.exists():continue
    count=0
    for directory,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in skip];count+=1
        matched=[(sample,cid)for sample,cid in by.items()if sample in directory]
        for name in files:
            own=matched or[(s,c)for s,c in by.items()if s in name]
            if not own or not name.endswith(('.json','.json.gz')):continue
            path=Path(directory)/name
            try:
                stat=path.stat();identity=(stat.st_dev,stat.st_ino)
                if identity in seen:continue
                seen.add(identity)
                if stat.st_size>64*1024*1024:
                    skipped.append(dict(path=str(path),reason='bounded_read_size_not_scientific_exclusion'));continue
                stored=path.read_bytes();raw=gzip.decompress(stored)if name.endswith('.gz')else stored;s=json.loads(raw)
                if not isinstance(s,dict)or not isinstance(s.get('frames'),list):continue
                digest=hashlib.sha256(raw).hexdigest();framehash=hashlib.sha256()
                for frame in s['frames']:framehash.update(json.dumps(frame,sort_keys=True).encode())
                for sample,cid in own:
                    out.append(dict(clip_id=cid,path=str(path),sha256=digest,stored_sha256=hashlib.sha256(stored).hexdigest(),
                        declared_video=s.get('render',{}).get('save_video'),frames=len(s['frames']),seed=s.get('seed'),
                        frame_payload_sha256=framehash.hexdigest()))
            except (OSError,ValueError,EOFError):continue
    searched.append(dict(root=str(root),visited_directories=count))
    (ROOT/'BACKUP_STATE_SEARCH.json').write_text(json.dumps(dict(searched=searched,matches=out,skipped=skipped),indent=2))
print(json.dumps(dict(roots=searched,states=len(out),unique_state_hashes=len({r['sha256']for r in out}))))
