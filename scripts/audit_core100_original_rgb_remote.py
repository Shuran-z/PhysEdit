"""Read original, SHA-bound references; CPU decode only, no simulation or GPU."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(os.environ.get('CORE100_REFERENCE_AUDIT_ROOT','/data2/liyuhan/core100_reference_admission_continue_20261101'))
jobs=json.loads((ROOT/'JOBS.json').read_text())


def audit(job):
    dest=ROOT/job['clip_id'];dest.mkdir(exist_ok=True)
    receipt=dest/'IDENTITY.json'
    if receipt.exists():
        prior=json.loads(receipt.read_text())
        if (prior.get('state')=='original_hash_verified_cpu_decode_complete' and prior.get('decoder')=='/usr/bin/ffmpeg'
            and prior['sha256']==job['sha256'] and prior['end_frame_index']==job['end_frame_index']):
            return prior
    candidates=[];header=job.get('header',{})
    candidates.extend(Path(p) for p in job.get('extra_video_paths',[]))
    if header.get('recorded_video'):candidates.append(Path(header['recorded_video']))
    if header.get('path'):
        base=Path(header['path']).parent.parent
        basename=Path(job['source_video_path']).name
        candidates.extend([base/basename,base/'videos'/basename])
        candidates.extend(base.glob('*.mp4'));candidates.extend((base/'videos').glob('*.mp4'))
    importer=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
    scene=job['clip_id'][:3];sample=job['sample_id']
    candidates += [importer/'everyday_bifurcation_72k_T16_T20_v1/production'/sample/'videos'/(sample+'__cam01.mp4'),
                   importer/'everyday_bifurcation_72k_T06_T10_v1/production'/sample/'videos'/(sample+'__cam01.mp4')]
    for cache in [Path('/home/wangzijun_p25/.cache/huggingface/hub'),Path('/data_cached/wangzijun_p25/.cache/huggingface/hub')]:
        if job.get('source_repo'):
            folder=cache/('datasets--'+job['source_repo'].replace('/','--'))/'snapshots'
            candidates.extend(folder.glob('*/'+job['source_video_path']))
    checked=[];video=None
    for p in dict.fromkeys(candidates):
        if not p.is_file():continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest();checked.append(dict(path=str(p),sha256=digest))
        if digest==job['sha256']:video=p;break
    if video is None:return dict(**job,state='original_video_not_found_by_hash',candidates_checked=checked)
    probe=subprocess.run(['/usr/bin/ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(video)],capture_output=True,check=True)
    stream=next(x for x in json.loads(probe.stdout)['streams']if x['codec_type']=='video')
    frames=int(stream['nb_read_frames']);end=min(frames-1,job['end_frame_index'])
    indices=sorted({0,job['condition_frame_index'],end,*[min(end,max(0,x))for x in [40,80,84,85,110,112,113,114,130,154]]})
    select='+'.join('eq(n,%d)'%i for i in indices)
    command=['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(video),'-vf',
             "select='%s',scale=480:-1,tile=4x4"%select,
             '-frames:v','1','-q:v','3','-y',str(dest/'original_sheet.jpg')]
    run=subprocess.run(command,capture_output=True);(dest/'decode_stderr.txt').write_bytes(run.stderr)
    # Also preserve the exact native condition frame; no GPU replay substitutes.
    frame_run=subprocess.run(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(video),'-vf',
        'select=eq(n\\,%d)'%job['condition_frame_index'],'-frames:v','1','-y',str(dest/'condition_native.png')],capture_output=True)
    row=dict(**job,state='original_hash_verified_cpu_decode_complete' if run.returncode==frame_run.returncode==0 else 'decode_failed',
        video_path=str(video),video_sha256=job['sha256'],native_frames=frames,native_fps=stream['avg_frame_rate'],
        width=stream['width'],height=stream['height'],review_frame_indices=indices,metadata=stream,
        original_sheet_sha256=hashlib.sha256((dest/'original_sheet.jpg').read_bytes()).hexdigest() if (dest/'original_sheet.jpg').exists()else None,
        condition_png_sha256=hashlib.sha256((dest/'condition_native.png').read_bytes()).hexdigest()if(dest/'condition_native.png').exists()else None,
        no_simulation_launched=True,reference_admitted=False,candidates_checked=checked,
        decoder='/usr/bin/ffmpeg',decoder_version=subprocess.check_output(['/usr/bin/ffmpeg','-version']).decode().splitlines()[0])
    (dest/'IDENTITY.json').write_text(json.dumps(row,indent=2));return row


with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:rows=list(pool.map(audit,jobs))
(ROOT/'RESULT.json').write_text(json.dumps(rows,indent=2))
with zipfile.ZipFile(ROOT/'RESULTS.zip','w',zipfile.ZIP_DEFLATED)as archive:
    archive.write(ROOT/'RESULT.json','RESULT.json')
    for p in ROOT.glob('*/*'):
        if p.is_file()and p.suffix in('.jpg','.png','.json','.txt'):archive.write(p,p.relative_to(ROOT))
print(json.dumps([dict(clip=r['clip_id'],state=r['state'])for r in rows]))
