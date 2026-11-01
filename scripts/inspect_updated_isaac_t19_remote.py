"""Read-only fetch and before/after pixel inspection of updated T19 HF media."""
import concurrent.futures
import hashlib
import json
import logging
import os
from pathlib import Path
import time

os.environ['NO_PROXY']='.amazonaws.com';os.environ['HF_HUB_DISABLE_XET']='1';logging.disable(logging.CRITICAL)
from huggingface_hub import HfApi,hf_hub_download,get_token
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029');OUT=ROOT/'updated_media_review';OUT.mkdir(exist_ok=True)
import fcntl
lock=open(OUT/'fetch.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
(OUT/'ACTIVE_FETCH.json').write_text(json.dumps({'pid':os.getpid()}))
comparison=json.loads((ROOT/'current960_media_comparison.json').read_text())
revision=comparison['revision'];changed=[r for r in comparison['checks'] if not r['same_bytes']]
import gzip
manifest=ROOT/'isaac_admission/metadata/releases/72000_release_candidate_20261029/videos.jsonl.gz'
rows={r['video_id']:r for r in map(json.loads,gzip.open(manifest,'rt'))}
selected=changed[:3]+[r for r in changed if '__bg02_' in r['path'] or '__bg04_' in r['path']]
selected += [r for r in changed if '/T19__repair__' in r['path']][:3]
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
if args.all:selected=changed
else:assert len(selected)==12


def inspect(entry):
    cv2.setNumThreads(1)
    vid=entry['video_id'];cached=OUT/(vid+'.json')
    if cached.exists():
        result=json.loads(cached.read_text())
        if result['current_sha256']==entry['current_sha256'] and Path(result['new_cached_path']).is_file():return result
    for attempt in range(5):
        try:
            new=Path(hf_hub_download('phy2/phydataset',entry['path'],repo_type='dataset',revision=revision,token=get_token()));break
        except Exception:
            if attempt==4:raise
            time.sleep(2)
    assert hashlib.sha256(new.read_bytes()).hexdigest()==entry['current_sha256']
    old=Path(rows[vid]['local_source']);assert hashlib.sha256(old.read_bytes()).hexdigest()==entry['inventory_sha256']
    picks=[0,1,4,7,14,30,209];frames=[];sizes=[];means=[];decoded=[];fps=[]
    for path in [old,new]:
        cap=cv2.VideoCapture(str(path));fps.append(cap.get(cv2.CAP_PROP_FPS));saved={};n=0;mean=[]
        while True:
            ok,bgr=cap.read()
            if not ok:break
            if n in picks:saved[n]=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            mean.append(float(bgr.mean()));n+=1
        cap.release();frames.append(saved);means.append(float(np.mean(mean)));decoded.append(n);sizes.append([saved[0].shape[1],saved[0].shape[0]])
    board=Image.new('RGB',(7*320,2*202),'white');corr=[];diff=[]
    for j,images in enumerate(frames):
        for k,f in enumerate(picks):
            if f not in images:continue
            rgb=images[f];h,w=rgb.shape[:2];im=Image.fromarray(rgb[int(.32*h):int(.73*h),int(.28*w):int(.72*w)]);im.thumbnail((320,180));board.paste(im,(k*320,j*202+22));ImageDraw.Draw(board).text((k*320,j*202),('OLD' if j==0 else 'UPDATED')+' '+rows[vid]['camera']+' f'+str(f),fill='black')
    for f in picks:
        if f in frames[0] and f in frames[1] and frames[0][f].shape==frames[1][f].shape:
            a=cv2.resize(frames[0][f],(160,90)).astype(float).ravel();b=cv2.resize(frames[1][f],(160,90)).astype(float).ravel();corr.append(float(np.corrcoef(a,b)[0,1]));diff.append(float(np.abs(a-b).mean()))
    sheet=OUT/(vid+'.jpg');board.save(sheet,quality=94)
    r={**entry,'old_path':str(old),'new_cached_path':str(new),'evidence':str(sheet),'evidence_sha256':hashlib.sha256(sheet.read_bytes()).hexdigest(),'decoded_frames_old_new':decoded,'fps_old_new':fps,'resolution_old_new':sizes,'mean_intensity_old_new':means,'sample_pixel_correlations':corr,'sample_pixel_mae':diff,'quality_admission':'NOT_DECIDED'}
    (OUT/(vid+'.json')).write_text(json.dumps(r,indent=2));return r


results=[];failures=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8 if args.all else 4) as pool:
    futures={pool.submit(inspect,x):x for x in selected}
    for future in concurrent.futures.as_completed(futures):
        try:results.append(future.result())
        except Exception as exc:failures.append({'video_id':futures[future]['video_id'],'error':type(exc).__name__})
        progress={'done':len(results),'failed':len(failures),'total':len(selected)}
        (OUT/'progress.json').write_text(json.dumps(progress));print(json.dumps(progress),flush=True)
(OUT/'results.json').write_text(json.dumps(results,indent=2))
(OUT/'fetch_errors.json').write_text(json.dumps(failures,indent=2))
api=HfApi(token=get_token())
try:
    entries=list(api.list_repo_tree('phy2/phydataset',repo_type='dataset',revision=revision,path_in_repo='catalog',recursive=False))
    (OUT/'catalog_listing.json').write_text(json.dumps([x.path for x in entries],indent=2))
except Exception as exc:(OUT/'catalog_listing_error.json').write_text(json.dumps({'error':type(exc).__name__}))
