"""Verify pinned generated media for admitted contact cases; never label events."""
import concurrent.futures
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
os.environ.update(HTTPS_PROXY='http://127.0.0.1:17891',HTTP_PROXY='http://127.0.0.1:17891')
from huggingface_hub import hf_hub_download

ROOT=Path(os.environ.get('CORE100_MEDIA_ROOT','/data2/liyuhan/core100_reference_admission_continue_20261101'))
tasks=json.loads(gzip.decompress((ROOT/os.environ.get('CORE100_MEDIA_TASKS','TASKS_12_13.json.gz')).read_bytes()))
horizon=float(os.environ.get('CORE100_MEDIA_REFERENCE_HORIZON','5'))
jobs=[t for t in tasks if t['state']=='resolved' and t['payload']['window_s']+1e-6>=horizon and t['payload']['duration_s']+1e-6>=horizon]
ledger=ROOT/'MODEL_MEDIA_VERIFICATION.json'
previous=json.loads(ledger.read_text())['rows']if ledger.exists()else[]
completed={x['video_sha256']:x for x in previous if x['status']=='verified'}

def verify(task):
    p=task['payload'];remote=p['remote_media'];identity=p['video_sha256']
    if identity in completed:return completed[identity]
    row=dict(task_id=task['id'],clip_id=p['clip_id'],model=p['model'],video_sha256=identity,
             repo=remote['repository'],revision=remote['revision'],path=remote['path'])
    try:
        path=Path(hf_hub_download(repo_id=remote['repository'],filename=remote['path'],
                                 revision=remote['revision'],repo_type='dataset'))
        assert hashlib.sha256(path.read_bytes()).hexdigest()==identity,'video_hash_mismatch'
        assert path.stat().st_size==remote['size'],'byte_size_mismatch'
        probe=subprocess.run(['/usr/bin/ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(path)],
                             capture_output=True,check=True,timeout=30)
        stream=next(x for x in json.loads(probe.stdout)['streams']if x['codec_type']=='video')
        decode=subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-threads','1','-hwaccel','none',
                               '-i',str(path),'-f','null','-'],capture_output=True,timeout=60)
        assert decode.returncode==0,'strict_decode_failed'
        row.update(status='verified',sha256=identity,size=path.stat().st_size,frames=int(stream['nb_read_frames']),
                   fps=float(Fraction(stream['avg_frame_rate'])),width=stream['width'],height=stream['height'],
                   full_native_decode=True,registered_frames=p['frames'],registered_fps=p['fps'],
                   local_cache_path=str(path))
    except Exception as error:row.update(status='verification_failed',error_type=type(error).__name__)
    return row

rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
    for row in pool.map(verify,jobs):
        rows.append(row)
        record=dict(schema='core100-additional-native-media-verification-v1',expected=len(jobs),rows=rows,
                    decoder='/usr/bin/ffmpeg',decoder_version=subprocess.check_output(['/usr/bin/ffmpeg','-version']).decode().splitlines()[0],
                    no_event_labels_or_task_payloads_modified=True)
        tmp=ledger.with_suffix('.tmp');tmp.write_text(json.dumps(record,indent=2));tmp.replace(ledger)
print(json.dumps(dict(expected=len(jobs),verified=sum(r['status']=='verified' for r in rows),failed=sum(r['status']!='verified' for r in rows))))
