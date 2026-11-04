"""Recover source sidecars via exact parent video identity; no simulation."""
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path('/data2/liyuhan/core100_remaining74_admission_20261101')
os.environ.update(HTTPS_PROXY='http://127.0.0.1:17891',HTTP_PROXY='http://127.0.0.1:17891')
BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')


def audit(j):
    r=dict(j);sample=j['sample_id']
    try:
        candidates=([Path(j['original_metadata_path'])]if j.get('original_metadata_path')else[])+[BASE/'outputs/pilot'/sample/'metadata'/(sample+'__cam01.json'),BASE/'production'/sample/'metadata'/(sample+'__cam01.json')]
        found=next((p for p in candidates if p.is_file()),None)
        if found is None:raise FileNotFoundError('original sidecar not located')
        stored=found.read_bytes();raw=gzip.decompress(stored)if found.suffix=='.gz'else stored;s=json.loads(raw)
        declared=s.get('render',{}).get('save_video')or s.get('video_path')
        video=Path(j.get('original_parent_video_path')or declared)if j.get('original_parent_video_path')or declared else found.parent.parent/'videos'/(sample+'__cam01.mp4')
        r['located_parent_video_sha256']=hashlib.sha256(video.read_bytes()).hexdigest()
        active=json.loads(Path(j['active_video_identity']).read_text());assert active['video_sha256']==j['video_sha256']
        def frames(p):
            out=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(p),'-vsync','0','-f','framemd5','-'])
            return [line.rsplit(b',',1)[-1].strip().decode()for line in out.splitlines()if line and not line.startswith(b'#')]
        a=frames(video);b=frames(active['video_path']);assert len(a)==len(b)==210 and a==b,'decoded original-sidecar video and active retimed frames differ'
        if r['located_parent_video_sha256']!=j['parent_video_sha256']:
            from huggingface_hub import hf_hub_download
            loc=j['parent_locator'];published=Path(hf_hub_download(repo_id=loc['repo_id'],filename=loc['path'],revision=loc['revision'],repo_type='dataset'))
            assert hashlib.sha256(published.read_bytes()).hexdigest()==j['parent_video_sha256'],'published parent digest mismatch'
            assert frames(published)==a,'published original and located source decoded frames differ'
            r['published_parent_container_differs_but_all_decoded_frames_identical']=True
        fs=s['frames'];end=fs[j['end_frame_index']]
        r.update(status='original_sidecar_parent_video_and_all_retimed_frames_verified',state_path=str(found),state_sha256=hashlib.sha256(raw).hexdigest(),
                 parent_video_path=str(video),decoded_frame_count=len(a),
                 decoded_frame_hashes_sha256=hashlib.sha256(json.dumps(a).encode()).hexdigest(),
                 state_keys=list(s),experiment=s.get('experiment'),scene_overrides=s.get('scene_overrides'),render=s.get('render'),
                 frame_keys=list(end),contacts_at_end=end.get('contacts'),native_last_substep_contacts=end.get('native_last_substep_contacts'),
                 physical_provenance=s.get('physical_provenance'),all_frames_have_contacts=all('contacts'in f for f in fs[5:]))
    except Exception as e:r.update(status='unverified',error_type=type(e).__name__,error=str(e))
    return r


out=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
    for r in pool.map(audit,json.loads((ROOT/'RETIMED_PLAN.json').read_text())):
        out.append(r);(ROOT/'RETIMED_SOURCE_AUDIT.json').write_text(json.dumps(out,indent=2))
print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'],error=r.get('error'))for r in out]))
