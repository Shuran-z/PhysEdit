"""Trace immutable archived states and documented compatibility transcoding."""
import gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101')
BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
jobs=json.loads((ROOT/'ORIGINAL_SOURCE_JOBS.json').read_text());out=[]
for j in jobs:
    cid=j['clip_id'];sample=j['sample_id'];scene=cid[:3]
    row=dict(clip_id=cid,states=[],related_files=[])
    candidates=[]
    if j.get('original_metadata_path'):candidates.append(Path(j['original_metadata_path']))
    for root in [Path('/data_cached/wangzijun_p25/hf_phyediting/data')/scene,
                 Path('/data_cached/wangzijun_p25/hf_upload_staging_20260906')/scene,
                 Path('/data_cached/wangzijun_p25/hf_upload_staging_t09_20260907')]:
        if root.exists():
            for p in root.rglob(sample+'*'):
                if p.is_file()and p.suffix in('.gz','.json'):candidates.append(p)
    for p in dict.fromkeys(candidates):
        if not p.exists():continue
        stored=p.read_bytes()
        try:s=json.loads(gzip.decompress(stored)if p.suffix=='.gz'else stored)
        except Exception:continue
        if not isinstance(s,dict):continue
        if not isinstance(s.get('frames'),list):
            row['related_files'].append(dict(path=str(p),sha256=hashlib.sha256(stored).hexdigest(),keys=list(s)[:20]));continue
        raw=gzip.decompress(stored)if p.suffix=='.gz'else stored
        v=s.get('render',{}).get('save_video')or s.get('video_path')
        record=dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),stored_sha256=hashlib.sha256(stored).hexdigest(),frames=len(s['frames']),
                    sample_id=s.get('sample_id'),render=s.get('render'),scene_overrides=s.get('scene_overrides'),experiment=s.get('experiment'),physical_provenance=s.get('physical_provenance'),declared_video=v)
        if v and Path(v).is_file():
            record['declared_video_sha256']=hashlib.sha256(Path(v).read_bytes()).hexdigest()
            record['stream']=json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_streams','-of','json',v]))['streams'][0]
        row['states'].append(record)
    video=next(Path(x['source'])for x in j['transfer_records']if x['destination'].endswith('.mp4'))
    row['original_transfer_video_sha256']=hashlib.sha256(video.read_bytes()).hexdigest()
    row['original_transfer_stream']=json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams'][0]
    out.append(row)
(ROOT/'ARCHIVED_STATE_TRACE.json').write_text(json.dumps(out,indent=2))
print(json.dumps([dict(clip_id=r['clip_id'],states=[dict(path=s['path'],sha256=s['sha256'],codec=s.get('stream',{}).get('codec_name'))for s in r['states']])for r in out]))
