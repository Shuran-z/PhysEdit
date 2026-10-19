"""Local Qwen adapter. Separate process/call for quality and registered events."""
import argparse,hashlib,json,os,time
from pathlib import Path

QUALITY='''Inspect video measurement quality ONLY. Identify the specified target through all frames. Check target identity continuity and whether support geometry is interpretable. Fusion, identity replacement, disintegration or severe geometry collapse preventing measurement is unmeasurable. Ordinary occlusion, rotation, leaving view, or clearly observable wrong physics is not by itself unmeasurable. Boxes/crops are not proof of identity. Do not infer falling or landing. Return JSON {"quality":{"status":"measurable|unmeasurable|uncertain","failure":"none|fusion|identity_loss|severe_corruption|uncertain","target_integrity":"intact|corrupted|uncertain","support_integrity":"intact|corrupted|uncertain","confidence":0.0,"evidence_times_s":[0.0],"reason":"specific visual evidence"}}. Select single enum values. Cite actual supplied timestamps, at least two for corruption. Self confidence is not a calibrated probability.'''
EVENTS='''Observe ONLY the specified events and target in this generated video. No reference answers are supplied. Return JSON {"events":{"REGISTERED_EVENT_NAME":{"label":"yes|no|not_observed|uncertain","confidence":0.0,"evidence_times_s":[0.0],"reason":"specific visual evidence","contradictions":[]}}}. Include every registered event name. Confidence is confidence in the observation, not probability of an event. Use timestamps actually supplied. Record conflicting visual evidence in contradictions; never suppress it to raise confidence. Unclear support/contact is uncertain. No only means absent within the declared window. Not seeing landing does not prove it will never occur. Do not infer identity loss merely from leaving view. Landing and departure are separate events; follow each supplied definition. Never invent future frames. No scores or quality verdict.'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('manifest','output','model'):p.add_argument('--'+arg,required=True)
    p.add_argument('--stage',choices=['quality','events'],required=True)
    p.add_argument('--device-map',default='auto');p.add_argument('--max-memory-json')
    p.add_argument('--frames',type=int,default=13);p.add_argument('--max-new-tokens',type=int,default=1600)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    if a.frames<2:raise ValueError('at least two frames')
    import cv2,numpy as np,torch
    from PIL import Image
    from transformers import AutoProcessor,AutoModelForMultimodalLM
    from .boundary_triage import parse_with_closing_brace_repair
    from .boundary import digest
    from .boundary_window import select_frames
    kwargs={}
    if a.max_memory_json:kwargs['max_memory']={int(k) if k.isdigit() else k:v for k,v in json.loads(a.max_memory_json).items()}
    model=AutoModelForMultimodalLM.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.bfloat16,device_map=a.device_map,**kwargs).eval()
    processor=AutoProcessor.from_pretrained(a.model,local_files_only=True)
    prompt=QUALITY if a.stage=='quality' else EVENTS
    receipt={'stage':a.stage,'model':a.model,'source_sha256':digest(__file__),'manifest_sha256':digest(a.manifest),
             'prompt':prompt,'frames':a.frames,'max_new_tokens':a.max_new_tokens,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'torch':torch.__version__}
    out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    with out.open('x',encoding='utf-8') as stream:
        for line in Path(a.manifest).read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            j=json.loads(line);start=time.time();r={'sample_id':j['sample_id'],'video_sha256':j['video_sha256']}
            try:
                if digest(j['video'])!=j['video_sha256']:raise ValueError('video hash mismatch')
                cap=cv2.VideoCapture(j['video']);fps=cap.get(5);n=int(cap.get(7))
                if fps<=0 or j['window_s']>(n-1)/fps+1e-6:raise ValueError('video does not cover horizon')
                end=min(n-1,int(j['window_s']*fps+1e-6));ids=sorted(set(np.linspace(0,end,a.frames).round().astype(int).tolist()))
                boxes={}
                if j.get('generated_track'):
                    if digest(j['generated_track'])!=j['generated_track_sha256']:raise ValueError('tracking changed')
                    tr=json.loads(Path(j['generated_track']).read_text(encoding='utf-8'))
                    if tr.get('video_sha256')!=j['video_sha256']:raise ValueError('wrong tracking video')
                    ids,_=select_frames(tr['frames'],end);boxes={x['frame']:x['bbox_xyxy'] for x in tr['frames']}
                content=[{'type':'text','text':prompt+'\nTarget: '+j['target']}];images=[];times=[];hashes=[]
                if a.stage=='events':content.append({'type':'text','text':'Registered definitions: '+json.dumps(j['events'])})
                for idx in ids:
                    cap.set(1,idx);ok,f=cap.read()
                    if not ok:raise ValueError('decode failure')
                    original=f.copy()
                    times.append(idx/fps);f=cv2.cvtColor(cv2.resize(f,(768,432)),cv2.COLOR_BGR2RGB)
                    images.append(Image.fromarray(f));hashes.append(hashlib.sha256(f.tobytes()).hexdigest())
                    content.extend([{'type':'text','text':f'Time {idx/fps:.6f} seconds'},{'type':'image','image':images[-1]}])
                    if j.get('roi'):
                        x1,y1,x2,y2=j['roi']
                        if x2>original.shape[1] or y2>original.shape[0]:raise ValueError('ROI outside frame')
                        crop=original[y1:y2,x1:x2].copy();box=boxes.get(idx)
                        if box:
                            bx1,by1,bx2,by2=box;cv2.rectangle(crop,(bx1-x1,by1-y1),(bx2-x1,by2-y1),(0,0,255),1)
                        crop=cv2.cvtColor(cv2.resize(crop,(512,512)),cv2.COLOR_BGR2RGB)
                        images.append(Image.fromarray(crop));hashes.append(hashlib.sha256(crop.tobytes()).hexdigest())
                        content.extend([{'type':'text','text':f'SAME time {idx/fps:.6f} seconds, enlarged crop; red box is only a tracker hint'},{'type':'image','image':images[-1]}])
                cap.release()
                text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
                batch=processor(text=[text],images=images,return_tensors='pt').to(model.device)
                with torch.inference_mode():generated=model.generate(**batch,max_new_tokens=a.max_new_tokens,do_sample=False)
                raw=processor.batch_decode(generated[:,batch['input_ids'].shape[1]:],skip_special_tokens=True)[0];r['raw']=raw
                d,repair=parse_with_closing_brace_repair(raw)
                expected='quality' if a.stage=='quality' else 'events'
                if not isinstance(d,dict) or not isinstance(d.get(expected),dict):raise ValueError('missing task output')
                # Validate cited timestamps against actual supplied frames, not just horizon.
                records=[d['quality']] if a.stage=='quality' else list(d['events'].values())
                for record in records:
                    ev=record.get('evidence_times_s',[])
                    if not isinstance(ev,list) or any(type(t) not in (int,float) or not any(abs(t-s)<=1e-5 for s in times) for t in ev):raise ValueError('evidence timestamp not supplied')
                r.update(status='ok',**{expected:d[expected]},format_repair=repair,frame_indices=ids,times_s=times,image_sha256=hashes)
            except Exception as exc:r.update(status='evaluator_failure',error=f'{type(exc).__name__}: {exc}')
            r['elapsed_s']=time.time()-start;stream.write(json.dumps(r,ensure_ascii=False)+'\n');stream.flush()

if __name__=='__main__':main()
