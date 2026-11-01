"""Hash-bound full decode/state evidence for retired T19. Never auto-admits media.

Runs on the storage host. Original per-video metadata is used, not rebuilt configs.
Each video gets a dense motion sheet, full-frame context and frame-level diagnostics.
"""
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault('OMP_NUM_THREADS', '1')
import cv2
import numpy as np
from PIL import Image, ImageDraw


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def project(points, camera, w, h):
    eye = np.array(camera['position']); forward = np.array(camera['look_at']) - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0., 0., 1.]); right /= np.linalg.norm(right)
    up = np.cross(right, forward); q = np.asarray(points) - eye
    depth = q @ forward; focal = h / (2 * np.tan(np.deg2rad(camera['fov_deg']) / 2))
    return np.stack([w / 2 + focal * (q @ right) / np.maximum(depth, .0001),
                     h / 2 - focal * (q @ up) / np.maximum(depth, .0001)], axis=-1), depth


def tile(rgb, label, size=(280, 180)):
    im = Image.fromarray(rgb); im.thumbnail(size)
    out = Image.new('RGB', (size[0], size[1] + 21), '#eeeeee')
    out.paste(im, ((size[0] - im.width) // 2, 21 + (size[1] - im.height) // 2))
    ImageDraw.Draw(out).text((3, 3), label, fill='black'); return out


def audit_group(task):
    rows, output = task; root = Path(output); sid = rows[0]['native_sample_id']
    target = root / 'groups' / sid; target.mkdir(parents=True, exist_ok=True)
    receipt = target / 'result.json'
    if receipt.exists():
        result = json.loads(receipt.read_text())
        if {r['video_sha256'] for r in result['videos']} == {r['sha256'] for r in rows}: return result
    cv2.setNumThreads(1); result = {'sample': sid, 'videos': [], 'admission': 'NOT_DECIDED'}
    overview = []
    for row in sorted(rows, key=lambda r: r['camera']):
        video = Path(row['local_source']); camera = row['camera']
        metadata = video.parent.parent / 'metadata' / (sid + '__cam01.json.gz')
        d = json.load(gzip.open(metadata, 'rt')); frames = d['frames']
        pos = np.array([[o['position'] for o in f['objects']] for f in frames])
        vel = np.array([[o['velocity'] for o in f['objects']] for f in frames])
        contact = []
        for i, f in enumerate(frames):
            hits = [c for c in f.get('contacts', []) if str(c.get('entity_a', '')).startswith('t19_') and str(c.get('entity_b', '')).startswith('t19_')]
            if hits: contact.append((i, max(float(c.get('penetration_m', 0)) for c in hits)))
        peak = max(contact, key=lambda x: x[1]) if contact else None
        selected = set([0, 20, 23, *range(24, 42), 45, 60, 90, 120, 150, 180, 209])
        if contact:
            selected.update(max(0, min(len(frames)-1, i)) for f in [contact[0][0], peak[0]] for i in range(f-2, f+3))
        selected = sorted(i for i in selected if i < len(frames))
        w, h = d['render']['resolution']; cam = d['render']['fixed_view']
        projected, depth = project(pos.reshape(-1, 3), cam, w, h)
        visible = projected[(depth > 0) & (projected[:, 0] >= 0) & (projected[:, 0] < w) & (projected[:, 1] >= 0) & (projected[:, 1] < h)]
        if len(visible):
            x0, y0 = np.maximum([0,0], np.floor(visible.min(axis=0) - 65)).astype(int)
            x1, y1 = np.minimum([w,h], np.ceil(visible.max(axis=0) + 65)).astype(int)
        else: x0,y0,x1,y1=0,0,w,h
        cap = cv2.VideoCapture(str(video)); saved = {}; n = 0; previous = None; pixel_diffs=[]
        first_small=None; motion_mask=np.zeros((180,320),dtype=np.uint8)
        while True:
            ok, bgr = cap.read()
            if not ok: break
            small = cv2.resize(bgr, (160, 90))
            motion_small=cv2.resize(bgr,(320,180))
            if first_small is None:first_small=motion_small.copy()
            motion_mask |= (cv2.absdiff(motion_small,first_small).max(axis=2)>30).astype(np.uint8)
            if previous is not None: pixel_diffs.append(float(np.mean(cv2.absdiff(small, previous))))
            previous = small
            if n in selected: saved[n] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            n += 1
        cap.release()
        # All three cameras share the saved physics, but only cam01 camera pose
        # is saved in this batch. A motion-union crop avoids fabricating poses.
        if camera!='cam01':
            yy,xx=np.where(motion_mask>0)
            if len(xx):
                x0=max(0,int(xx.min()*w/320)-65);x1=min(w,int((xx.max()+1)*w/320)+65)
                y0=max(0,int(yy.min()*h/180)-65);y1=min(h,int((yy.max()+1)*h/180)+65)
            else:x0,y0,x1,y1=0,0,w,h
        sheet = Image.new('RGB', (7*280, ((len(selected)+6)//7)*201), 'white')
        for j,i in enumerate(selected):
            if i in saved: sheet.paste(tile(saved[i][y0:y1,x0:x1], f'{camera} f{i} {i/30:.3f}s'), ((j%7)*280,(j//7)*201))
        sheet_path=target/(camera+'_dense.jpg');sheet.save(sheet_path,quality=91)
        picks=[0,24,27,32,60,min(209,n-1)]
        overview_row=[]
        for i in picks:
            if i not in saved:
                c=cv2.VideoCapture(str(video));c.set(cv2.CAP_PROP_POS_FRAMES,i);ok,bgr=c.read();c.release()
                if ok:saved[i]=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            if i in saved:overview_row.append(tile(saved[i][y0:y1,x0:x1],f'{camera} f{i}'))
        overview.append(overview_row)
        context=Image.new('RGB',(3*420,257),'white')
        for j,i in enumerate([0,32,min(209,n-1)]):
            if i in saved:context.paste(tile(saved[i],f'{camera} FULL f{i}',(420,236)),(j*420,0))
        context_path=target/(camera+'_context.jpg');context.save(context_path,quality=91)
        actual=sha(video)
        result['videos'].append({'video_id':row['video_id'],'video_sha256':actual,'expected_sha256':row['sha256'],
            'hash_matches':actual==row['sha256'],'video_path':str(video),'metadata_path':str(metadata),
            'metadata_sha256':sha(metadata),'decoded_frames':n,'state_frames':len(frames),
            'all_state_finite':bool(np.isfinite(pos).all() and np.isfinite(vel).all()),
            'actors':[o['name'] for o in frames[0]['objects']],
            'max_saved_position_step_m':float(np.linalg.norm(np.diff(pos,axis=0),axis=2).max()),
            'pair_contact_frames':len(contact),'pair_contact_peak':peak,
            'pixel_difference_max':max(pixel_diffs,default=0),'pixel_difference_mean':float(np.mean(pixel_diffs)),
            'roi':[int(x0),int(y0),int(x1),int(y1)],'dense_sheet':str(sheet_path),
            'dense_sheet_sha256':sha(sheet_path),'context_sheet':str(context_path),
            'inspected_by_reviewer':False,'quality_decision':'PENDING_REVIEW'})
    board=Image.new('RGB',(6*280,3*201+25),'white');ImageDraw.Draw(board).text((4,5),sid,fill='black')
    for c,tiles in enumerate(overview):
        for j,t in enumerate(tiles):board.paste(t,(j*280,25+c*201))
    board.save(target/'overview.jpg',quality=92)
    receipt.write_text(json.dumps(result,indent=2));return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--output',required=True);ap.add_argument('--workers',type=int,default=12);args=ap.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=open(root/'audit.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    groups={}
    for r in map(json.loads,Path(args.manifest).read_text().splitlines()):groups.setdefault(r['native_sample_id'],[]).append(r)
    assert all(len(rows)==3 for rows in groups.values())
    started=time.time();results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        future={pool.submit(audit_group,(rows,str(root))):sid for sid,rows in sorted(groups.items())}
        for f in concurrent.futures.as_completed(future):
            try:results.append(f.result())
            except Exception as exc:results.append({'sample':future[f],'error':repr(exc),'admission':'NOT_DECIDED'})
            (root/'progress.json').write_text(json.dumps({'groups_completed':len(results),'groups_total':len(groups),'errors':sum('error' in r for r in results),'elapsed_s':time.time()-started,'pid':os.getpid()}))
    (root/'results.json').write_text(json.dumps(results));(root/'COMPLETE.json').write_text(json.dumps({'groups':len(results),'videos':sum(len(r.get('videos',[])) for r in results),'errors':sum('error' in r for r in results),'quality_admission':'REQUIRES_REVIEWER_ADJUDICATION'}))


if __name__=='__main__':main()
