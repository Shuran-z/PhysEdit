"""Decode every original native frame into numbered audit sheets, CPU only."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101')
jobs=json.loads((ROOT/'VISUAL_JOBS.json').read_text());out=[]
for j in jobs:
    video=Path(j['video_path']);assert hashlib.sha256(video.read_bytes()).hexdigest()==j['video_sha256']
    dest=ROOT/'full_frame_review'/j['clip_id'];dest.mkdir(parents=True,exist_ok=True)
    # All210 frames, no temporal subsampling. Numbers identify native frame index.
    size=(640,360);count=0;sheets=[];sheet=None;draw=None
    proc=subprocess.Popen(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(video),'-vf','scale=640:360','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    while True:
        raw=proc.stdout.read(size[0]*size[1]*3)
        if not raw:break
        assert len(raw)==size[0]*size[1]*3
        k=count%24
        if k==0:sheet=Image.new('RGB',(2560,2256));draw=ImageDraw.Draw(sheet)
        x=(k%4)*640;y=(k//4)*376
        sheet.paste(Image.frombytes('RGB',size,raw),(x,y));draw.text((x+5,y+360),str(count),fill='white')
        count+=1
        if count%24==0:
            p=dest/('%03d_%03d.jpg'%(count-24,count-1));sheet.save(p,quality=93);sheets.append(dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),first_frame=count-24,last_frame=count-1));sheet=None
    if sheet is not None:
        p=dest/('%03d_%03d.jpg'%((count//24)*24,count-1));sheet.save(p,quality=93);sheets.append(dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),first_frame=(count//24)*24,last_frame=count-1))
    stderr=proc.stderr.read().decode();assert proc.wait()==0 and count==j['native_frames']
    out.append(dict(clip_id=j['clip_id'],video_sha256=j['video_sha256'],native_frames=count,all_frames_decoded=True,temporal_subsampling=False,sheets=sheets,decoder='/usr/bin/ffmpeg',stderr=stderr))
    (ROOT/'FULL_FRAME_EXTRACTION.json').write_text(json.dumps(out,indent=2))
with zipfile.ZipFile(ROOT/'FULL_FRAMES.zip','w',zipfile.ZIP_DEFLATED)as z:
    z.write(ROOT/'FULL_FRAME_EXTRACTION.json','FULL_FRAME_EXTRACTION.json')
    for r in out:
        for sheet in r['sheets']:z.write(sheet['file'],Path(sheet['file']).relative_to(ROOT))
print(json.dumps([dict(clip_id=r['clip_id'],frames=r['native_frames'],sheets=len(r['sheets']))for r in out]))
