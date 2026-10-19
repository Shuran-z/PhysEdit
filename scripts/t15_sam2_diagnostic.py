"""First-frame prompted SAM2 propagation; no later corrections or truth geometry."""
import hashlib,json,os,sys,time
from pathlib import Path
import cv2,numpy as np

ROOT=Path(sys.argv[1])
REPO='/data1/zhangshuran/ScenePhysInv/third_party/sam2_source'
CKPT='/data1/zhangshuran/ScenePhysInv/third_party/worldbench_eval_code/ckpt/sam2.1_hiera_small.pt'
sys.path.insert(0,REPO)
import torch
from sam2.build_sam import build_sam2_video_predictor
torch.set_num_threads(2);cv2.setNumThreads(1)
ROOT.mkdir(exist_ok=True)
receipt=dict(model='SAM2.1 hiera small',repo=REPO,checkpoint=CKPT,checkpoint_sha256=hashlib.sha256(Path(CKPT).read_bytes()).hexdigest(),
    torch=torch.__version__,cv2=cv2.__version__,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    initial_box=[465,92,555,125],positive_point=[510,108],init='assistant selected first-frame bbox + center point; no later prompts',frame_range=[0,123])
(ROOT/'tracking_receipt.json').write_text(json.dumps(receipt,indent=2))
predictor=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_s.yaml',CKPT,device='cuda')
for sid in ('clip03','clip06'):
    start=time.time();folder=ROOT/sid;folder.mkdir(exist_ok=True);cache=folder/'frames';cache.mkdir(exist_ok=True)
    video=ROOT/'media'/f'{sid}.mp4';cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);images=[]
    for i in range(124):
        ok,f=cap.read();assert ok
        images.append(f);cv2.imwrite(str(cache/f'{i:05d}.jpg'),f,[cv2.IMWRITE_JPEG_QUALITY,95])
    cap.release();records=[];masks=[]
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        state=predictor.init_state(video_path=str(cache),offload_video_to_cpu=True)
        predictor.add_new_points_or_box(state,frame_idx=0,obj_id=1,box=np.array(receipt['initial_box'],dtype=np.float32),
            points=np.array([receipt['positive_point']],dtype=np.float32),labels=np.array([1],dtype=np.int32))
        for idx,ids,logits in predictor.propagate_in_video(state):
            mask=(logits[0,0]>0).cpu().numpy();ys,xs=np.nonzero(mask)
            b=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1] if len(xs) else None
            records.append(dict(frame=int(idx),time_s=idx/fps,bbox_xyxy=b,area=int(mask.sum())))
            masks.append(mask)
        predictor.reset_state(state)
    np.savez_compressed(folder/'masks.npz',masks=np.stack(masks))
    (folder/'tracks.json').write_text(json.dumps(dict(sample_id=sid,fps=fps,video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),frames=records,elapsed_s=time.time()-start),indent=2))
    writer=cv2.VideoWriter(str(folder/'overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(854,480))
    previews=[]
    for f,m,r in zip(images,masks,records):
        overlay=f.copy();overlay[m]=(overlay[m]*.55+np.array([0,255,0])*.45).astype(np.uint8)
        if r['bbox_xyxy']:
            x1,y1,x2,y2=r['bbox_xyxy'];cv2.rectangle(overlay,(x1,y1),(x2,y2),(0,0,255),1)
        writer.write(overlay)
        if r['frame'] in (0,49,74,98,117,123):
            crop=cv2.resize(overlay[40:240,430:630],(400,400));cv2.putText(crop,f"{sid} f{r['frame']}",(8,22),0,.6,(0,0,255),2);previews.append(crop)
    writer.release()
    sheet=np.concatenate([np.concatenate(previews[i:i+3],axis=1) for i in (0,3)],axis=0)
    cv2.imwrite(str(folder/'preview.jpg'),sheet)
    print(sid,'frames',len(records),'nonempty',sum(r['area']>0 for r in records),'final',records[-1],flush=True)
